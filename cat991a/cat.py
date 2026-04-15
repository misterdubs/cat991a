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

    def get_status(self) -> dict:
        """Return a snapshot of key radio state over a single connection.

        Queries frequency and mode in one session to avoid the overhead of
        opening the serial port twice.

        Returns:
            Dict with keys ``frequency_mhz`` (float) and ``mode`` (str).
        """
        return {
            "frequency_mhz": self.get_frequency(),
            "mode": self.get_mode(),
        }
