"""Low-level CAT protocol communication with the FT-991A.

The FT-991A CAT protocol uses ASCII commands terminated by a semicolon (;).
Commands are sent and the radio replies with the same command prefix followed
by the data value and a closing semicolon.

Example:
    Send:    FA;
    Receive: FA014225000;   (14.225 MHz on VFO-A)

Reference: Yaesu FT-991A CAT Operation Reference Manual
"""

import sys
import time

import serial


class CATError(Exception):
    """Raised when the radio returns an error or the connection fails."""


# FT-991A mode codes as defined in the CAT Operation Reference Manual.
# Key: single character returned/accepted by the radio.
# Value: human-readable mode name used by the CLI.
MODES: dict[str, str] = {
    "1": "LSB",
    "2": "USB",
    "3": "CW",
    "4": "FM",
    "5": "AM",
    "6": "RTTY-LSB",
    "7": "CW-R",
    "8": "DATA-LSB",
    "9": "RTTY-USB",
    "A": "DATA-FM",
    "B": "FM-N",
    "C": "DATA-USB",
    "D": "AM-N",
    "E": "C4FM",
}

# Reverse lookup: mode name (upper-cased) → radio code.
MODE_CODES: dict[str, str] = {name: code for code, name in MODES.items()}

# Repeater shift direction codes (OS command).
SHIFTS: dict[str, str] = {
    "0": "SIMPLEX",
    "1": "+",
    "2": "-",
}
SHIFT_CODES: dict[str, str] = {name: code for code, name in SHIFTS.items()}

# CTCSS/tone-squelch mode codes (CT command).
CTCSS_MODES: dict[str, str] = {
    "0": "OFF",
    "1": "ENC",       # encode only (transmit tone, open on any signal)
    "2": "TSQL",      # tone squelch (encode + decode)
}
CTCSS_MODE_CODES: dict[str, str] = {name: code for code, name in CTCSS_MODES.items()}

# Standard CTCSS tone frequencies in Hz, indexed by the 2-digit TN command value.
# Indices 00–49 match the FT-991A tone table.
CTCSS_TONES: list[float] = [
     67.0,  69.3,  71.9,  74.4,  77.0,  79.7,  82.5,  85.4,  88.5,  91.5,
     94.8,  97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,
    131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9,
    171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8, 196.6, 199.5,
    203.5, 206.5, 210.7, 218.1, 225.7, 229.1, 233.6, 241.8, 250.3, 254.1,
]


class Radio:
    """Context-manager wrapper around a serial CAT connection.

    Usage::

        with Radio.from_config(cfg) as radio:
            freq = radio.get_frequency()

        # With debug output (prints raw bytes to stderr):
        with Radio.from_config(cfg, debug=True) as radio:
            radio.set_frequency(146.520)
    """

    def __init__(self, port: str, baudrate: int, bytesize: int,
                 stopbits: int, parity: str, timeout: float,
                 debug: bool = False) -> None:
        self._debug = debug
        self._serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            stopbits=stopbits,
            parity=parity,
            timeout=timeout,
        )
        # Discard any bytes the radio sent before we were ready (e.g. AI mode
        # status packets from a previous session left in the OS buffer).
        self._serial.reset_input_buffer()

    @classmethod
    def from_config(cls, cfg: dict, debug: bool = False) -> "Radio":
        """Construct a Radio from a config dict as returned by config.load()."""
        return cls(
            port=cfg["port"],
            baudrate=cfg["baudrate"],
            bytesize=cfg["bytesize"],
            stopbits=cfg["stopbits"],
            parity=cfg["parity"],
            timeout=cfg.get("timeout", 2),
            debug=debug,
        )

    def __enter__(self) -> "Radio":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        if self._serial.is_open:
            self._serial.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, direction: str, data: bytes) -> None:
        """Print raw bytes to stderr when debug mode is enabled."""
        if self._debug:
            print(f"[CAT {direction}] {data!r}", file=sys.stderr)

    def _send(self, command: str) -> None:
        """Send a CAT command string (semicolon appended automatically)."""
        raw = (command + ";").encode()
        self._log("TX", raw)
        self._serial.write(raw)
        self._serial.flush()

    def _recv(self) -> str:
        """Read one semicolon-terminated response from the radio."""
        buf = b""
        while True:
            byte = self._serial.read(1)
            if not byte:
                raise CATError(
                    f"Timeout waiting for response (partial: {buf!r})"
                )
            buf += byte
            if byte == b";":
                break
        self._log("RX", buf)
        return buf.decode().rstrip(";")

    def command(self, cmd: str) -> str:
        """Send *cmd* and return the response payload (prefix stripped).

        Args:
            cmd: Two-letter CAT command, e.g. ``"FA"``.

        Returns:
            The data portion of the response, e.g. ``"00014225000"``.

        Raises:
            CATError: on timeout or unexpected response.
        """
        self._send(cmd)
        response = self._recv()
        if not response.startswith(cmd):
            raise CATError(
                f"Unexpected response to {cmd!r}: {response!r}"
            )
        return response[len(cmd):]

    def _check_error_response(self, cmd: str) -> None:
        """Read any pending bytes and raise if the radio replied with '?'.

        The FT-991A sends '?;' when it rejects a command. For accepted set
        commands it sends nothing, so we wait briefly and only consume bytes
        that are already waiting — we never block here.

        Raises:
            CATError: if the radio responded with '?'.
        """
        time.sleep(0.1)
        waiting = self._serial.in_waiting
        if waiting == 0:
            return
        response = self._serial.read(waiting)
        self._log("RX", response)
        text = response.decode(errors="replace").strip(";")
        if "?" in text:
            raise CATError(
                f"Radio rejected '{cmd}' with '?' — "
                "possible causes: cross-band frequency jump (try a frequency "
                "on the same band first), AI mode interference, or radio busy"
            )

    # ------------------------------------------------------------------
    # CAT command wrappers
    # ------------------------------------------------------------------

    def get_frequency_hz(self) -> int:
        """Return VFO-A frequency in Hz.

        CAT command: FA (VFO-A frequency in Hz; may omit leading zeros)
        """
        raw = self.command("FA")
        if not raw.isdigit():
            raise CATError(f"Unexpected frequency response: {raw!r}")
        return int(raw)

    def get_frequency(self) -> float:
        """Return VFO-A frequency in MHz."""
        return self.get_frequency_hz() / 1_000_000

    def set_frequency_hz(self, hz: int) -> None:
        """Set VFO-A frequency and verify the radio accepted it.

        Sends the FA set command, checks for an error response, then reads
        back the frequency to confirm the radio changed to the requested value.

        CAT command: FA (send 9-digit zero-padded Hz value)

        Args:
            hz: Frequency in Hz, e.g. 146520000 for 146.520 MHz.

        Raises:
            CATError: if the radio rejects the command or the read-back
                      does not match the requested frequency.
        """
        # Clear any stale bytes (e.g. AI-mode packets) before the exchange.
        self._serial.reset_input_buffer()

        set_cmd = f"FA{hz:09d}"
        self._send(set_cmd)
        self._check_error_response(set_cmd)

        actual_hz = self.get_frequency_hz()
        if actual_hz != hz:
            raise CATError(
                f"Frequency mismatch after set: "
                f"sent {hz} Hz, radio reports {actual_hz} Hz"
            )

    def set_frequency(self, mhz: float) -> None:
        """Set VFO-A frequency from a MHz value."""
        self.set_frequency_hz(round(mhz * 1_000_000))

    def get_mode(self) -> str:
        """Return the current operating mode name (e.g. 'FM', 'USB').

        CAT command: MD0 (query VFO-A mode)
        """
        code = self.command("MD0").upper()
        if code not in MODES:
            raise CATError(f"Unknown mode code from radio: {code!r}")
        return MODES[code]

    def set_mode(self, mode: str) -> None:
        """Set the operating mode and verify the radio accepted it.

        CAT command: MD0 (set VFO-A mode)

        Args:
            mode: Mode name, e.g. ``"FM"`` or ``"USB"``. Case-insensitive.
                  Valid modes: LSB, USB, CW, FM, AM, RTTY-LSB, CW-R,
                  DATA-LSB, RTTY-USB, DATA-FM, FM-N, DATA-USB, AM-N, C4FM.

        Raises:
            ValueError: if *mode* is not a recognised mode name.
            CATError: if the radio rejects the command or the read-back
                      does not match the requested mode.
        """
        key = mode.upper()
        if key not in MODE_CODES:
            valid = ", ".join(sorted(MODE_CODES))
            raise ValueError(f"Unknown mode {mode!r}. Valid modes: {valid}")

        code = MODE_CODES[key]
        self._serial.reset_input_buffer()

        set_cmd = f"MD0{code}"
        self._send(set_cmd)
        self._check_error_response(set_cmd)

        actual = self.get_mode()
        if actual.upper() != key:
            raise CATError(
                f"Mode mismatch after set: sent {mode!r}, radio reports {actual!r}"
            )

    def get_shift(self) -> str:
        """Return the repeater shift direction ('SIMPLEX', '+', or '-').

        CAT command: OS (Offset Shift)
        """
        code = self.command("OS")
        if code not in SHIFTS:
            raise CATError(f"Unknown shift code from radio: {code!r}")
        return SHIFTS[code]

    def set_shift(self, direction: str) -> None:
        """Set the repeater shift direction and verify the radio accepted it.

        CAT command: OS (Offset Shift)

        Args:
            direction: ``'SIMPLEX'``, ``'+'``, or ``'-'``. Case-insensitive.

        Raises:
            ValueError: if *direction* is not recognised.
            CATError: if the radio rejects the command or the read-back
                      does not match.
        """
        key = direction.upper()
        if key not in SHIFT_CODES:
            valid = ", ".join(SHIFT_CODES)
            raise ValueError(f"Unknown shift {direction!r}. Valid: {valid}")

        code = SHIFT_CODES[key]
        self._serial.reset_input_buffer()
        set_cmd = f"OS{code}"
        self._send(set_cmd)
        self._check_error_response(set_cmd)

        actual = self.get_shift()
        if actual.upper() != key:
            raise CATError(
                f"Shift mismatch after set: sent {direction!r}, "
                f"radio reports {actual!r}"
            )

    def get_ctcss_mode(self) -> str:
        """Return the CTCSS/tone-squelch mode ('OFF', 'ENC', or 'TSQL').

        CAT command: CT (CTCSS mode)
        """
        code = self.command("CT")
        if code not in CTCSS_MODES:
            raise CATError(f"Unknown CTCSS mode code from radio: {code!r}")
        return CTCSS_MODES[code]

    def set_ctcss_mode(self, mode: str) -> None:
        """Set the CTCSS mode and verify the radio accepted it.

        CAT command: CT (CTCSS mode)

        Args:
            mode: ``'OFF'``, ``'ENC'`` (encode only), or ``'TSQL'``
                  (encode + decode). Case-insensitive.

        Raises:
            ValueError: if *mode* is not recognised.
            CATError: if the radio rejects the command or the read-back
                      does not match.
        """
        key = mode.upper()
        if key not in CTCSS_MODE_CODES:
            valid = ", ".join(CTCSS_MODE_CODES)
            raise ValueError(f"Unknown CTCSS mode {mode!r}. Valid: {valid}")

        code = CTCSS_MODE_CODES[key]
        self._serial.reset_input_buffer()
        set_cmd = f"CT{code}"
        self._send(set_cmd)
        self._check_error_response(set_cmd)

        actual = self.get_ctcss_mode()
        if actual.upper() != key:
            raise CATError(
                f"CTCSS mode mismatch after set: sent {mode!r}, "
                f"radio reports {actual!r}"
            )

    def get_ctcss_tone(self) -> float:
        """Return the CTCSS tone frequency in Hz (e.g. 88.5).

        CAT command: TN (Tone Number, 2-digit index into CTCSS_TONES)
        """
        raw = self.command("TN")
        if not raw.isdigit() or not (0 <= int(raw) < len(CTCSS_TONES)):
            raise CATError(f"Unexpected tone number from radio: {raw!r}")
        return CTCSS_TONES[int(raw)]

    def set_ctcss_tone(self, hz: float) -> None:
        """Set the CTCSS tone by frequency and verify the radio accepted it.

        CAT command: TN (Tone Number)

        Args:
            hz: CTCSS tone frequency in Hz, e.g. ``88.5``. Must exactly match
                one of the 50 standard tones in ``CTCSS_TONES``.

        Raises:
            ValueError: if *hz* does not match a standard CTCSS tone.
            CATError: if the radio rejects the command or the read-back
                      does not match.
        """
        # Find matching tone within 0.1 Hz tolerance to handle float input.
        index = next(
            (i for i, t in enumerate(CTCSS_TONES) if abs(t - hz) < 0.1),
            None,
        )
        if index is None:
            valid = ", ".join(str(t) for t in CTCSS_TONES)
            raise ValueError(
                f"{hz} Hz is not a standard CTCSS tone. Valid tones: {valid}"
            )

        self._serial.reset_input_buffer()
        set_cmd = f"TN{index:02d}"
        self._send(set_cmd)
        self._check_error_response(set_cmd)

        actual = self.get_ctcss_tone()
        if abs(actual - hz) >= 0.1:
            raise CATError(
                f"CTCSS tone mismatch after set: sent {hz} Hz, "
                f"radio reports {actual} Hz"
            )

    def get_status(self) -> dict:
        """Return a snapshot of key radio state over a single connection.

        Queries all values in one session to avoid reopening the serial port.

        Returns:
            Dict with keys: ``frequency_mhz``, ``mode``, ``shift``,
            ``ctcss_mode``, ``ctcss_tone_hz``.
        """
        return {
            "frequency_mhz": self.get_frequency(),
            "mode": self.get_mode(),
            "shift": self.get_shift(),
            "ctcss_mode": self.get_ctcss_mode(),
            "ctcss_tone_hz": self.get_ctcss_tone(),
        }
