"""Where the application keeps its files.

- The program is installed for every account in
  `C:\\Program Files\\KEF LSX Controller\\`, read-only for a normal user.
- The settings (speaker IP, auto USB) and the log belong to each account:
  `%APPDATA%\\KefLSXController\\`. The folder name predates the installer
  and is kept so that existing settings are found again.
"""

import os
import sys
from pathlib import Path

from . import product

CONFIG_DIR_NAME = "KefLSXController"


def config_dir():
    appdata = os.environ.get("APPDATA")
    if appdata:
        folder = Path(appdata) / CONFIG_DIR_NAME
        try:
            folder.mkdir(parents=True, exist_ok=True)
            return folder
        except OSError:
            pass
    # Fall back to the .exe / source directory if APPDATA is unavailable.
    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def config_file():
    return config_dir() / "config.json"


def log_file():
    return config_dir() / "kef-controller.log"


def install_dir():
    program_files = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles")
    return Path(program_files or r"C:\Program Files") / product.APP_NAME


def installed_exe():
    return install_dir() / product.EXE_NAME


def legacy_exe():
    """The copy placed by hand before the installer existed (up to 0.2.2)."""
    program_files = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles")
    return Path(program_files or r"C:\Program Files") / "Kef" / product.EXE_NAME


def is_frozen():
    """True when running as the executable, False from the sources."""
    return bool(getattr(sys, "frozen", False))


def running_installed_copy():
    """True if this process is the installed executable itself."""
    if not is_frozen():
        return False
    try:
        return Path(sys.executable).resolve() == installed_exe().resolve()
    except OSError:
        return False
