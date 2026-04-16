"""Unit tests for cat991a.cli — uses Click's test runner, no radio required."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from cat991a.cli import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_CONFIG = {
    "port": "/dev/fake",
    "baudrate": 38400,
    "bytesize": 8,
    "stopbits": 2,
    "parity": "N",
    "timeout": 2,
}


def make_mock_radio(*, frequency_mhz=443.716, mode="FM", shift="+",
                    ctcss_mode="ENC", ctcss_tone_hz=88.5):
    """Return a mock Radio context manager with sensible defaults."""
    radio = MagicMock()
    radio.get_frequency.return_value = frequency_mhz
    radio.get_mode.return_value = mode
    radio.get_shift.return_value = shift
    radio.get_ctcss_mode.return_value = ctcss_mode
    radio.get_ctcss_tone.return_value = ctcss_tone_hz
    radio.get_status.return_value = {
        "frequency_mhz": frequency_mhz,
        "mode": mode,
        "shift": shift,
        "ctcss_mode": ctcss_mode,
        "ctcss_tone_hz": ctcss_tone_hz,
    }
    return radio


# ---------------------------------------------------------------------------
# Error handling — missing config
# ---------------------------------------------------------------------------

def test_get_frequency_no_config():
    """A helpful error pointing to `init` is shown when config is missing."""
    runner = CliRunner()
    with patch("cat991a.cli.cfg_mod.require",
               side_effect=RuntimeError("No configuration found. Run `cat991a init` first.")):
        result = runner.invoke(cli, ["get", "frequency"])
    assert result.exit_code != 0
    assert "init" in result.output


# ---------------------------------------------------------------------------
# Click Choice validation — bad values are rejected before reaching the radio
# ---------------------------------------------------------------------------

def test_set_mode_invalid_choice():
    runner = CliRunner()
    result = runner.invoke(cli, ["set", "mode", "BADMODE"])
    assert result.exit_code != 0
    assert "Invalid value" in result.output


def test_set_shift_invalid_choice():
    runner = CliRunner()
    result = runner.invoke(cli, ["set", "shift", "SIDEWAYS"])
    assert result.exit_code != 0
    assert "Invalid value" in result.output


def test_set_ctcss_mode_invalid_choice():
    runner = CliRunner()
    result = runner.invoke(cli, ["set", "ctcss-mode", "BADMODE"])
    assert result.exit_code != 0
    assert "Invalid value" in result.output


def test_set_ctcss_tone_invalid():
    """A tone that doesn't match any standard frequency shows a clear error."""
    runner = CliRunner()
    with patch("cat991a.cli.cfg_mod.require", return_value=FAKE_CONFIG), \
         patch("cat991a.cli.Radio") as MockRadio:
        MockRadio.from_config.return_value.__enter__.return_value.set_ctcss_tone \
            .side_effect = ValueError("99.9 Hz is not a standard CTCSS tone")
        result = runner.invoke(cli, ["set", "ctcss-tone", "99.9"])
    assert result.exit_code != 0
    assert "standard CTCSS tone" in result.output


# ---------------------------------------------------------------------------
# get frequency — output format
# ---------------------------------------------------------------------------

def test_get_frequency_default_mhz():
    runner = CliRunner()
    radio = make_mock_radio(frequency_mhz=443.716)
    with patch("cat991a.cli.cfg_mod.require", return_value=FAKE_CONFIG), \
         patch("cat991a.cli.Radio") as MockRadio:
        MockRadio.from_config.return_value.__enter__.return_value = radio
        result = runner.invoke(cli, ["get", "frequency"])
    assert result.exit_code == 0
    assert "443.716000 MHz" in result.output


def test_get_frequency_hz_flag():
    runner = CliRunner()
    radio = make_mock_radio(frequency_mhz=443.716)
    with patch("cat991a.cli.cfg_mod.require", return_value=FAKE_CONFIG), \
         patch("cat991a.cli.Radio") as MockRadio:
        MockRadio.from_config.return_value.__enter__.return_value = radio
        result = runner.invoke(cli, ["get", "frequency", "--hz"])
    assert result.exit_code == 0
    assert "443716000 Hz" in result.output


def test_get_frequency_json_mhz():
    runner = CliRunner()
    radio = make_mock_radio(frequency_mhz=443.716)
    with patch("cat991a.cli.cfg_mod.require", return_value=FAKE_CONFIG), \
         patch("cat991a.cli.Radio") as MockRadio:
        MockRadio.from_config.return_value.__enter__.return_value = radio
        result = runner.invoke(cli, ["get", "--json", "frequency"])
    assert result.exit_code == 0
    assert '"frequency_mhz"' in result.output


def test_get_frequency_json_hz_flag():
    runner = CliRunner()
    radio = make_mock_radio(frequency_mhz=443.716)
    with patch("cat991a.cli.cfg_mod.require", return_value=FAKE_CONFIG), \
         patch("cat991a.cli.Radio") as MockRadio:
        MockRadio.from_config.return_value.__enter__.return_value = radio
        result = runner.invoke(cli, ["get", "--json", "frequency", "--hz"])
    assert result.exit_code == 0
    assert '"frequency_hz"' in result.output
    assert "443716000" in result.output


# ---------------------------------------------------------------------------
# get status — output format
# ---------------------------------------------------------------------------

def test_get_status_plain():
    runner = CliRunner()
    radio = make_mock_radio()
    with patch("cat991a.cli.cfg_mod.require", return_value=FAKE_CONFIG), \
         patch("cat991a.cli.Radio") as MockRadio:
        MockRadio.from_config.return_value.__enter__.return_value = radio
        result = runner.invoke(cli, ["get", "status"])
    assert result.exit_code == 0
    assert "443.716000 MHz" in result.output
    assert "FM" in result.output
    assert "ENC (88.5 Hz)" in result.output


def test_get_status_ctcss_off():
    """When CTCSS is OFF the tone frequency is not shown."""
    runner = CliRunner()
    radio = make_mock_radio(ctcss_mode="OFF")
    with patch("cat991a.cli.cfg_mod.require", return_value=FAKE_CONFIG), \
         patch("cat991a.cli.Radio") as MockRadio:
        MockRadio.from_config.return_value.__enter__.return_value = radio
        result = runner.invoke(cli, ["get", "status"])
    assert result.exit_code == 0
    assert "CTCSS:      OFF" in result.output


def test_get_status_json():
    runner = CliRunner()
    radio = make_mock_radio()
    with patch("cat991a.cli.cfg_mod.require", return_value=FAKE_CONFIG), \
         patch("cat991a.cli.Radio") as MockRadio:
        MockRadio.from_config.return_value.__enter__.return_value = radio
        result = runner.invoke(cli, ["get", "--json", "status"])
    assert result.exit_code == 0
    assert '"frequency_mhz"' in result.output
    assert '"mode"' in result.output
    assert '"shift"' in result.output
