"""cat991a — CAT control CLI for the Yaesu FT-991A transceiver.

Commands
--------
  init            Detect serial ports and save connection settings.

  get frequency       Read the current VFO-A frequency from the radio.
  get mode            Read the current operating mode.
  get shift           Read the repeater shift direction.
  get ctcss-mode      Read the CTCSS/tone-squelch mode.
  get ctcss-tone      Read the CTCSS tone frequency.
  get status          Read all of the above in a single query.

  set frequency       Set the VFO-A frequency.
  set mode            Set the operating mode.
  set shift           Set the repeater shift direction.
  set ctcss-mode      Set the CTCSS/tone-squelch mode.
  set ctcss-tone      Set the CTCSS tone frequency.

Usage
-----
  cat991a init
  cat991a get status
  cat991a get --json status
  cat991a set frequency 443.716
  cat991a set mode FM

Run any command with -h for details:
  cat991a get -h
  cat991a set mode -h
"""

import json as json_mod

import click
from serial.tools import list_ports

from . import config as cfg_mod
from .cat import (
    CTCSS_MODES, CTCSS_MODE_CODES, CTCSS_TONES,
    CATError, MODE_CODES, SHIFT_CODES, Radio,
)

# Applied to every group and command so that both -h and --help work.
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


# ---------------------------------------------------------------------------
# Root command group
# ---------------------------------------------------------------------------

@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option()
@click.option("--debug", is_flag=True, default=False,
              help="Print raw CAT bytes to stderr for troubleshooting.")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """CAT control for the Yaesu FT-991A transceiver.

    Run `cat991a init` once to configure the serial connection, then use
    the `get` and `set` subcommands to interact with the radio.

    \b
    Examples:
      cat991a init
      cat991a get status
      cat991a get --json status
      cat991a set frequency 443.716
      cat991a set mode FM

    \b
    Get help on any subcommand:
      cat991a get -h
      cat991a set -h
      cat991a set frequency -h
      cat991a set mode -h
    """
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@cli.command(context_settings=CONTEXT_SETTINGS)
def init() -> None:
    """Detect serial ports and save connection settings.

    Scans for available USB/serial ports, prompts you to choose one, then
    asks for baud rate and optional timeout. Settings are written to
    ~/.cat991a/config.json.

    The FT-991A ships with 38400 baud / 8N2 by default. Match whatever
    is configured under MENU > CAT RATE on the radio.
    """
    # --- port selection ---
    ports = sorted(list_ports.comports(), key=lambda p: p.device)
    if not ports:
        raise click.ClickException(
            "No serial ports found. Make sure the USB cable is connected."
        )

    click.echo("\nAvailable serial ports:\n")
    for i, port in enumerate(ports):
        desc = port.description or "unknown"
        click.echo(f"  [{i}] {port.device}  —  {desc}")

    click.echo()
    port_index = click.prompt(
        "Select port number",
        type=click.IntRange(0, len(ports) - 1),
        default=0,
    )
    chosen_port = ports[port_index].device

    # --- baud rate ---
    click.echo(f"\nSupported baud rates: {cfg_mod.VALID_BAUDRATES}")
    baudrate = click.prompt(
        "Baud rate",
        type=click.Choice([str(b) for b in cfg_mod.VALID_BAUDRATES]),
        default="38400",
        show_choices=False,
    )

    # --- timeout ---
    timeout = click.prompt(
        "Read timeout in seconds",
        type=float,
        default=2.0,
    )

    # FT-991A serial framing is fixed: 8 data bits, 2 stop bits, no parity.
    cfg = {
        **cfg_mod.DEFAULTS,
        "port": chosen_port,
        "baudrate": int(baudrate),
        "timeout": timeout,
    }

    cfg_mod.save(cfg)
    click.echo(f"\nConfiguration saved to {cfg_mod.CONFIG_FILE}")
    click.echo(f"  Port:     {cfg['port']}")
    click.echo(f"  Baud:     {cfg['baudrate']}")
    click.echo(f"  Framing:  {cfg['bytesize']}N{cfg['stopbits']}")
    click.echo(f"  Timeout:  {cfg['timeout']}s")


# ---------------------------------------------------------------------------
# get  (subcommand group)
# ---------------------------------------------------------------------------

@cli.group(context_settings=CONTEXT_SETTINGS)
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Output as JSON instead of plain text.")
@click.pass_context
def get(ctx: click.Context, as_json: bool) -> None:
    """Read values from the radio.

    \b
    Available items:
      frequency    Current VFO-A frequency in MHz
      mode         Current operating mode (e.g. FM, USB, CW)
      shift        Repeater shift direction (SIMPLEX, +, -)
      ctcss-mode   CTCSS mode (OFF, ENC, TSQL)
      ctcss-tone   CTCSS tone frequency in Hz
      status       All of the above in one query

    \b
    Add --json to get machine-readable output:
      cat991a get --json status
      cat991a get --json frequency
    """
    ctx.ensure_object(dict)
    ctx.obj["as_json"] = as_json


@get.command("frequency", context_settings=CONTEXT_SETTINGS)
@click.option("--hz", "use_hz", is_flag=True, default=False,
              help="Display frequency in Hz instead of MHz.")
@click.pass_context
def get_frequency(ctx: click.Context, use_hz: bool) -> None:

    """Read the current VFO-A frequency.

    Sends the FA (VFO-A frequency) CAT command and prints the result in MHz.

    Example:
        $ cat991a get frequency
        14.225000 MHz
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            freq_mhz = radio.get_frequency()
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    if ctx.obj.get("as_json"):
        if use_hz:
            click.echo(json_mod.dumps({"frequency_hz": round(freq_mhz * 1_000_000)}))
        else:
            click.echo(json_mod.dumps({"frequency_mhz": freq_mhz}))
    elif use_hz:
        click.echo(f"{round(freq_mhz * 1_000_000)} Hz")
    else:
        click.echo(f"{freq_mhz:.6f} MHz")



@get.command("mode", context_settings=CONTEXT_SETTINGS)
@click.pass_context
def get_mode(ctx: click.Context) -> None:
    """Read the current operating mode.

    Sends the MD0 (VFO-A mode) CAT command and prints the mode name.

    \b
    Example:
        $ cat991a get mode
        FM
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            mode = radio.get_mode()
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    if ctx.obj.get("as_json"):
        click.echo(json_mod.dumps({"mode": mode}))
    else:
        click.echo(mode)


@get.command("status", context_settings=CONTEXT_SETTINGS)
@click.pass_context
def get_status(ctx: click.Context) -> None:
    """Read frequency and mode in a single query.

    Opens one connection and fetches all values, making it faster than
    running get frequency and get mode separately.

    \b
    Examples:
        $ cat991a get status
        Frequency:  443.716000 MHz
        Mode:       FM
        Shift:      +
        CTCSS:      ENC (88.5 Hz)

        $ cat991a get --json status
        {"frequency_mhz": 443.716, "mode": "FM", "shift": "+", ...}
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            status = radio.get_status()
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    if ctx.obj.get("as_json"):
        click.echo(json_mod.dumps(status))
    else:
        ctcss = status["ctcss_mode"]
        if ctcss != "OFF":
            ctcss = f"{ctcss} ({status['ctcss_tone_hz']} Hz)"
        click.echo(f"Frequency:  {status['frequency_mhz']:.6f} MHz")
        click.echo(f"Mode:       {status['mode']}")
        click.echo(f"Shift:      {status['shift']}")
        click.echo(f"CTCSS:      {ctcss}")


@get.command("shift", context_settings=CONTEXT_SETTINGS)
@click.pass_context
def get_shift(ctx: click.Context) -> None:
    """Read the repeater shift direction.

    \b
    Example:
        $ cat991a get shift
        +
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            shift = radio.get_shift()
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    if ctx.obj.get("as_json"):
        click.echo(json_mod.dumps({"shift": shift}))
    else:
        click.echo(shift)


@get.command("ctcss-mode", context_settings=CONTEXT_SETTINGS)
@click.pass_context
def get_ctcss_mode(ctx: click.Context) -> None:
    """Read the CTCSS/tone-squelch mode.

    \b
    OFF    CTCSS disabled
    ENC    Encode only (transmit tone, open on any signal)
    TSQL   Tone squelch (encode + decode)

    \b
    Example:
        $ cat991a get ctcss-mode
        ENC
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            mode = radio.get_ctcss_mode()
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    if ctx.obj.get("as_json"):
        click.echo(json_mod.dumps({"ctcss_mode": mode}))
    else:
        click.echo(mode)


@get.command("ctcss-tone", context_settings=CONTEXT_SETTINGS)
@click.pass_context
def get_ctcss_tone(ctx: click.Context) -> None:
    """Read the CTCSS tone frequency in Hz.

    \b
    Example:
        $ cat991a get ctcss-tone
        88.5 Hz
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            tone = radio.get_ctcss_tone()
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    if ctx.obj.get("as_json"):
        click.echo(json_mod.dumps({"ctcss_tone_hz": tone}))
    else:
        click.echo(f"{tone} Hz")


# ---------------------------------------------------------------------------
# set  (subcommand group)
# ---------------------------------------------------------------------------

@cli.group(context_settings=CONTEXT_SETTINGS)
def set() -> None:
    """Write values to the radio.

    \b
    Available items:
      frequency    Set VFO-A frequency (MHz)
      mode         Set operating mode (e.g. FM, USB, CW)
      shift        Set repeater shift direction (SIMPLEX, +, -)
      ctcss-mode   Set CTCSS mode (OFF, ENC, TSQL)
      ctcss-tone   Set CTCSS tone by frequency in Hz (e.g. 88.5)
    """


@set.command("frequency", context_settings=CONTEXT_SETTINGS)
@click.argument("mhz", type=float)
@click.pass_context
def set_frequency(ctx: click.Context, mhz: float) -> None:
    """Set the VFO-A frequency to MHZ.

    MHZ is the desired frequency in megahertz. Decimal values are accepted.

    \b
    Examples:
        $ cat991a set frequency 443.716
        $ cat991a set frequency 14.225
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            radio.set_frequency(mhz)
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    click.echo(f"Frequency set to {mhz:.6f} MHz")


@set.command("mode", context_settings=CONTEXT_SETTINGS)
@click.argument("mode", metavar="MODE",
                type=click.Choice(sorted(MODE_CODES), case_sensitive=False))
@click.pass_context
def set_mode(ctx: click.Context, mode: str) -> None:
    """Set the operating mode to MODE.

    \b
    Valid modes:
      LSB, USB, CW, CW-R, AM, AM-N, FM, FM-N,
      RTTY-LSB, RTTY-USB, DATA-LSB, DATA-USB, DATA-FM, C4FM

    \b
    Examples:
        $ cat991a set mode FM
        $ cat991a set mode USB
        $ cat991a set mode CW
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            radio.set_mode(mode)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    click.echo(f"Mode set to {mode.upper()}")


@set.command("shift", context_settings=CONTEXT_SETTINGS)
@click.argument("direction", metavar="DIRECTION",
                type=click.Choice(list(SHIFT_CODES), case_sensitive=False))
@click.pass_context
def set_shift(ctx: click.Context, direction: str) -> None:
    """Set the repeater shift direction to DIRECTION.

    \b
    Valid directions:
      SIMPLEX   No offset (simplex operation)
      +         Positive offset
      -         Negative offset

    \b
    Examples:
        $ cat991a set shift +
        $ cat991a set shift SIMPLEX
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            radio.set_shift(direction)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    click.echo(f"Shift set to {direction.upper()}")


@set.command("ctcss-mode", context_settings=CONTEXT_SETTINGS)
@click.argument("mode", metavar="MODE",
                type=click.Choice(list(CTCSS_MODE_CODES), case_sensitive=False))
@click.pass_context
def set_ctcss_mode(ctx: click.Context, mode: str) -> None:
    """Set the CTCSS/tone-squelch mode to MODE.

    \b
    Valid modes:
      OFF    Disable CTCSS
      ENC    Encode only (transmit tone, open on any signal)
      TSQL   Tone squelch (encode + decode)

    \b
    Examples:
        $ cat991a set ctcss-mode ENC
        $ cat991a set ctcss-mode OFF
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            radio.set_ctcss_mode(mode)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    click.echo(f"CTCSS mode set to {mode.upper()}")


@set.command("ctcss-tone", context_settings=CONTEXT_SETTINGS)
@click.argument("hz", metavar="HZ", type=float)
@click.pass_context
def set_ctcss_tone(ctx: click.Context, hz: float) -> None:
    """Set the CTCSS tone to HZ.

    HZ must match one of the 50 standard CTCSS tone frequencies.

    \b
    Common tones:
      67.0  71.9  74.4  77.0  79.7  82.5  85.4  88.5  91.5  94.8
      100.0 103.5 107.2 110.9 114.8 118.8 123.0 127.3 131.8 136.5
      141.3 146.2 151.4 156.7 162.2 167.9 173.8 179.9 186.2 192.8
      203.5 210.7 218.1 225.7 233.6 241.8 250.3

    \b
    Examples:
        $ cat991a set ctcss-tone 88.5
        $ cat991a set ctcss-tone 100.0
    """
    try:
        radio_cfg = cfg_mod.require()
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    debug = ctx.obj.get("debug", False)
    try:
        with Radio.from_config(radio_cfg, debug=debug) as radio:
            radio.set_ctcss_tone(hz)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    except CATError as exc:
        raise click.ClickException(f"CAT error: {exc}")
    except Exception as exc:
        raise click.ClickException(f"Connection error: {exc}")

    click.echo(f"CTCSS tone set to {hz} Hz")
