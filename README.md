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

Use `-h` with any command or subcommand for details:

```bash
cat991a -h
cat991a get -h
cat991a set -h
cat991a set frequency -h
```

---

### get — read values from the radio

All `get` commands accept `--json` for machine-readable output:

```bash
cat991a get --json status
cat991a get --json frequency
```

| Command | Description |
|---|---|
| `cat991a get status` | Frequency, mode, shift, and CTCSS in one query |
| `cat991a get frequency` | VFO-A frequency in MHz |
| `cat991a get mode` | Operating mode |
| `cat991a get shift` | Repeater shift direction |
| `cat991a get ctcss-mode` | CTCSS/tone-squelch mode |
| `cat991a get ctcss-tone` | CTCSS tone frequency in Hz |

```bash
$ cat991a get status
Frequency:  443.716000 MHz
Mode:       FM
Shift:      +
CTCSS:      ENC (88.5 Hz)

$ cat991a get frequency
443.716000 MHz

$ cat991a get mode
FM

$ cat991a get shift
+

$ cat991a get ctcss-mode
ENC

$ cat991a get ctcss-tone
88.5 Hz
```

---

### set — write values to the radio

| Command | Description |
|---|---|
| `cat991a set frequency <MHz>` | Set VFO-A frequency in MHz |
| `cat991a set mode <mode>` | Set operating mode |
| `cat991a set shift <direction>` | Set repeater shift direction |
| `cat991a set ctcss-mode <mode>` | Set CTCSS/tone-squelch mode |
| `cat991a set ctcss-tone <Hz>` | Set CTCSS tone frequency |

```bash
$ cat991a set frequency 443.716
Frequency set to 443.716000 MHz

$ cat991a set mode FM
Mode set to FM

$ cat991a set shift +
Shift set to +

$ cat991a set ctcss-mode ENC
CTCSS mode set to ENC

$ cat991a set ctcss-tone 88.5
CTCSS tone set to 88.5 Hz
```

**Valid modes:** `LSB`, `USB`, `CW`, `CW-R`, `AM`, `AM-N`, `FM`, `FM-N`, `RTTY-LSB`, `RTTY-USB`, `DATA-LSB`, `DATA-USB`, `DATA-FM`, `C4FM`

**Valid shift directions:** `SIMPLEX`, `+`, `-`

**Valid CTCSS modes:** `OFF`, `ENC` (encode only), `TSQL` (tone squelch — encode + decode)

**Valid CTCSS tones (Hz):**
```
 67.0   69.3   71.9   74.4   77.0   79.7   82.5   85.4   88.5   91.5
 94.8   97.4  100.0  103.5  107.2  110.9  114.8  118.8  123.0  127.3
131.8  136.5  141.3  146.2  151.4  156.7  159.8  162.2  165.5  167.9
171.3  173.8  177.3  179.9  183.5  186.2  189.9  192.8  196.6  199.5
203.5  206.5  210.7  218.1  225.7  229.1  233.6  241.8  250.3  254.1
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
- On VHF/UHF, frequency changes must stay within the current band. Use `set frequency` to move within the same band before switching bands.

---

## Implemented CAT commands

| CLI command | CAT command | Description |
|---|---|---|
| `get frequency` / `set frequency` | `FA` | VFO-A frequency (Hz) |
| `get mode` / `set mode` | `MD0` | VFO-A operating mode |
| `get shift` / `set shift` | `OS` | Repeater offset direction |
| `get ctcss-mode` / `set ctcss-mode` | `CT` | CTCSS/tone-squelch mode |
| `get ctcss-tone` / `set ctcss-tone` | `TN` | CTCSS tone number |

---

## License

MIT
