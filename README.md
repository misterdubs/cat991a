# cat991a

A command-line CAT control tool for the Yaesu FT-991A transceiver, written in Python.

> **Work in progress.** Commands and behavior may change as development continues.

> **macOS only.** This tool has only been tested on macOS. It may work on Linux or Windows, but that has not been verified.

---

## Requirements

### USB Driver

The FT-991A uses a Silicon Labs CP210x USB-to-UART bridge. macOS requires the VCP driver from Silicon Labs before the radio will appear as a serial port:

**[Download CP210x VCP Driver for macOS](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)**

Install the driver, then connect the radio via USB. The port will appear as something like `/dev/cu.usbserial-XXXX` or `/dev/cu.SLAB_USBtoUART`.

### Python

Python 3.9 or newer is required.

---

## Installation

```bash
git clone https://github.com/misterdubs/cat991a.git
cd cat991a
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Setup

Run `init` once to detect serial ports and save your connection settings:

```bash
cat991a init
```

You will be prompted to select a serial port and baud rate. Match the baud rate to what is configured on the radio under **MENU > CAT RATE**. The default is 38400.

Settings are saved to `~/.cat991a/config.json`.

---

## Usage

```
cat991a [OPTIONS] COMMAND [ARGS]...

Options:
  --version   Show the version and exit.
  --debug     Print raw CAT bytes to stderr for troubleshooting.
  -h, --help  Show this message and exit.
```

### get — read values from the radio

| Command | Description |
|---|---|
| `cat991a get frequency` | Read the current VFO-A frequency |
| `cat991a get mode` | Read the current operating mode |

```bash
$ cat991a get frequency
443.716000 MHz

$ cat991a get mode
FM
```

### set — write values to the radio

| Command | Description |
|---|---|
| `cat991a set frequency <MHz>` | Set VFO-A to a frequency in MHz |
| `cat991a set mode <mode>` | Set the operating mode |

```bash
$ cat991a set frequency 146.520
Frequency set to 146.520000 MHz

$ cat991a set mode USB
Mode set to USB
```

**Valid modes:** `LSB`, `USB`, `CW`, `CW-R`, `AM`, `AM-N`, `FM`, `FM-N`, `RTTY-LSB`, `RTTY-USB`, `DATA-LSB`, `DATA-USB`, `DATA-FM`, `C4FM`

### Getting help

```bash
cat991a -h
cat991a get -h
cat991a set -h
cat991a set frequency -h
cat991a set mode -h
```

---

## Troubleshooting

**Radio not found / no ports listed**
- Confirm the Silicon Labs VCP driver is installed (see Requirements above).
- Try unplugging and reconnecting the USB cable.
- Make sure the radio is powered on.

**`?` response from radio**
- Run the command again with `--debug` to see the raw bytes being exchanged.
- Make sure the radio is in VFO mode (not memory mode).
- Confirm the baud rate in `~/.cat991a/config.json` matches **MENU > CAT RATE** on the radio.
- On VHF/UHF, frequency changes must stay within the current band. Use `set frequency` to move to a frequency on the same band first if switching bands.

---

## Implemented CAT commands

| CLI command | CAT command | Description |
|---|---|---|
| `get frequency` | `FA` | VFO-A frequency (Hz) |
| `set frequency` | `FA` | VFO-A frequency (Hz) |
| `get mode` | `MD0` | VFO-A operating mode |
| `set mode` | `MD0` | VFO-A operating mode |

---

## License

MIT
