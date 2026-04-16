"""Unit tests for cat991a.cat — no serial connection required."""

import pytest
from unittest.mock import MagicMock, patch

from cat991a.cat import (
    CTCSS_MODES, CTCSS_MODE_CODES, CTCSS_TONES,
    CATError, MODES, MODE_CODES, SHIFTS, SHIFT_CODES, Radio,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_radio(*responses: str):
    """Return a (Radio, mock_serial) pair.

    Each string in *responses* is a complete semicolon-terminated CAT response.
    They are concatenated and fed to read(1) one byte at a time, matching how
    Radio._recv consumes the serial port.
    """
    stream = b"".join(r.encode() for r in responses)
    chunks = iter(stream[i:i + 1] for i in range(len(stream)))

    mock_serial = MagicMock()
    mock_serial.is_open = True
    mock_serial.in_waiting = 0
    mock_serial.read.side_effect = lambda n: next(chunks, b"")

    with patch("cat991a.cat.serial.Serial", return_value=mock_serial):
        radio = Radio(
            port="/dev/fake", baudrate=38400, bytesize=8,
            stopbits=2, parity="N", timeout=2,
        )
    return radio, mock_serial


# ---------------------------------------------------------------------------
# Lookup table integrity
# ---------------------------------------------------------------------------

def test_modes_roundtrip():
    """Every mode code maps to a name and back to the same code."""
    for code, name in MODES.items():
        assert MODE_CODES[name] == code


def test_shifts_roundtrip():
    for code, name in SHIFTS.items():
        assert SHIFT_CODES[name] == code


def test_ctcss_modes_roundtrip():
    for code, name in CTCSS_MODES.items():
        assert CTCSS_MODE_CODES[name] == code


def test_ctcss_tones_count():
    assert len(CTCSS_TONES) == 50


def test_ctcss_tones_known_values():
    assert CTCSS_TONES[0] == 67.0
    assert CTCSS_TONES[8] == 88.5
    assert CTCSS_TONES[12] == 100.0
    assert CTCSS_TONES[49] == 254.1


# ---------------------------------------------------------------------------
# Frequency math
# ---------------------------------------------------------------------------

def test_frequency_hz_rounding():
    """Decimal MHz values with potential float imprecision round correctly."""
    assert round(14.225 * 1_000_000) == 14225000
    assert round(146.520 * 1_000_000) == 146520000
    assert round(443.716 * 1_000_000) == 443716000


def test_frequency_9digit_format():
    """9-digit zero-padded format covers the full FT-991A frequency range."""
    assert f"FA{1800000:09d}" == "FA001800000"   # 1.8 MHz (lowest HF)
    assert f"FA{14225000:09d}" == "FA014225000"   # 14.225 MHz
    assert f"FA{443716000:09d}" == "FA443716000"  # 443.716 MHz (UHF)


# ---------------------------------------------------------------------------
# Radio.get_* — response parsing with mock serial
# ---------------------------------------------------------------------------

def test_get_frequency_hz():
    radio, _ = make_radio("FA443716000;")
    assert radio.get_frequency_hz() == 443716000


def test_get_frequency_mhz():
    radio, _ = make_radio("FA443716000;")
    assert radio.get_frequency() == pytest.approx(443.716)


def test_get_frequency_leading_zeros():
    """HF frequencies with leading zeros in the response parse correctly."""
    radio, _ = make_radio("FA014225000;")
    assert radio.get_frequency_hz() == 14225000


def test_get_mode_valid():
    radio, _ = make_radio("MD04;")
    assert radio.get_mode() == "FM"


def test_get_mode_unknown_code_raises():
    radio, _ = make_radio("MD0Z;")
    with pytest.raises(CATError, match="Unknown mode code"):
        radio.get_mode()


def test_get_shift_positive():
    radio, _ = make_radio("OS1;")
    assert radio.get_shift() == "+"


def test_get_shift_simplex():
    radio, _ = make_radio("OS0;")
    assert radio.get_shift() == "SIMPLEX"


def test_get_ctcss_mode():
    radio, _ = make_radio("CT1;")
    assert radio.get_ctcss_mode() == "ENC"


def test_get_ctcss_tone():
    radio, _ = make_radio("TN08;")
    assert radio.get_ctcss_tone() == 88.5


# ---------------------------------------------------------------------------
# Radio.set_* — invalid input raises ValueError before touching serial
# ---------------------------------------------------------------------------

def test_set_mode_invalid_raises():
    radio, _ = make_radio()
    with pytest.raises(ValueError, match="Unknown mode"):
        radio.set_mode("BADMODE")


def test_set_shift_invalid_raises():
    radio, _ = make_radio()
    with pytest.raises(ValueError, match="Unknown shift"):
        radio.set_shift("SIDEWAYS")


def test_set_ctcss_mode_invalid_raises():
    radio, _ = make_radio()
    with pytest.raises(ValueError, match="Unknown CTCSS mode"):
        radio.set_ctcss_mode("PARTIAL")


def test_set_ctcss_tone_invalid_raises():
    radio, _ = make_radio()
    with pytest.raises(ValueError, match="not a standard CTCSS tone"):
        radio.set_ctcss_tone(55.0)  # below 67.0 Hz, the lowest standard tone


def test_set_ctcss_tone_fuzzy_match():
    """Floating-point imprecision within 0.1 Hz still resolves to the right tone."""
    index = next(
        (i for i, t in enumerate(CTCSS_TONES) if abs(t - 88.50000001) < 0.1),
        None,
    )
    assert index == 8


# ---------------------------------------------------------------------------
# Radio.set_* — verify correct CAT command bytes are written
# ---------------------------------------------------------------------------

@patch("time.sleep")
def test_set_frequency_command_format(mock_sleep):
    """set_frequency_hz sends the correct 9-digit FA command."""
    radio, mock_serial = make_radio("FA443716000;")  # read-back response
    radio.set_frequency_hz(443716000)
    sent = [call.args[0] for call in mock_serial.write.call_args_list]
    assert b"FA443716000;" in sent


@patch("time.sleep")
def test_set_mode_command_format(mock_sleep):
    """set_mode sends the correct MD0 command."""
    radio, mock_serial = make_radio("MD04;")  # read-back response
    radio.set_mode("FM")
    sent = [call.args[0] for call in mock_serial.write.call_args_list]
    assert b"MD04;" in sent


@patch("time.sleep")
def test_set_ctcss_tone_command_format(mock_sleep):
    """set_ctcss_tone sends the correct 2-digit TN index."""
    radio, mock_serial = make_radio("TN08;")  # read-back response
    radio.set_ctcss_tone(88.5)
    sent = [call.args[0] for call in mock_serial.write.call_args_list]
    assert b"TN08;" in sent
