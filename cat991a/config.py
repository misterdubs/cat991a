"""Configuration management for cat991a.

Settings are stored in ~/.cat991a/config.json. Run `cat991a init` to
create or update the configuration.
"""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".cat991a"
CONFIG_FILE = CONFIG_DIR / "config.json"

# FT-991A serial defaults
DEFAULTS: dict = {
    "port": None,
    "baudrate": 38400,
    "bytesize": 8,
    "stopbits": 2,
    "parity": "N",
    "timeout": 2,
}

# Baud rates supported by the FT-991A
VALID_BAUDRATES = [4800, 9600, 19200, 38400]


def load() -> dict:
    """Return the saved configuration, or an empty dict if none exists."""
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open() as fh:
        return json.load(fh)


def save(cfg: dict) -> None:
    """Persist *cfg* to the configuration file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")


def require() -> dict:
    """Return the saved configuration, raising if it hasn't been created yet.

    Raises:
        RuntimeError: when `cat991a init` has not been run.
    """
    cfg = load()
    if not cfg.get("port"):
        raise RuntimeError(
            "No configuration found. Run `cat991a init` first."
        )
    return cfg
