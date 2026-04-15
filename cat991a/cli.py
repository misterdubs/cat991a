"""cat991a — CAT control CLI for the Yaesu FT-991A transceiver.

Commands
--------
  init            Detect serial ports and save connection settings.

  get frequency   Read the current VFO-A frequency from the radio.
  get mode        Read the current operating mode.

  set frequency   Set the VFO-A frequency.
  set mode        Set the operating mode.

Usage
-----
  cat991a init
  cat991a get frequency
  cat991a get mode
  cat991a set frequency 443.716
  cat991a set mode FM

Run any command with --help for details:
  cat991a get --help
  cat991a set mode --help
"""

import click
from serial.tools import list_ports

from . import config as cfg_mod
from .cat import CATError, MODE_CODES, Radio

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
      cat991a get frequency
      cat991a get mode
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
def get() -> None:
    """Read values from the radio.

    \b
    Available items:
      frequency   Current VFO-A frequency in MHz
      mode        Current operating mode (e.g. FM, USB, CW)
    """


@get.command("frequency", context_settings=CONTEXT_SETTINGS)
@click.pass_context
def get_frequency(ctx: click.Context) -> None:
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

    click.echo(mode)


# ---------------------------------------------------------------------------
# set  (subcommand group)
# ---------------------------------------------------------------------------

@cli.group(context_settings=CONTEXT_SETTINGS)
def set() -> None:
    """Write values to the radio.

    \b
    Available items:
      frequency   Set VFO-A frequency (MHz)
      mode        Set operating mode (e.g. FM, USB, CW)
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
