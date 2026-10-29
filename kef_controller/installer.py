"""Installing, updating and removing KEF LSX Controller.

A single executable does everything, like the self-installing programs one
downloads: started from anywhere else than its installation folder, it
offers to install itself, or to update the installed copy; started from
there, it is the application.

The program goes to `Program Files`, which takes an administrator -- asked
for once, through UAC, by a second copy of the executable that does the
privileged part and exits. The application itself never runs elevated.

The account that launched the setup (not elevated):
- asks the running instances to exit, and stops those that do not (the
  versions before 0.3.0 do not know the request);
- after the elevated part: points its "Run with Windows" entry at the
  installed copy, and starts it.

The elevated part:
- copies the executable, through a temporary name, so that an interrupted
  copy never leaves half an executable behind;
- removes the copy placed by hand in `Program Files\\Kef` before 0.3.0;
- registers the program with Windows: "Installed apps" entry and Start
  menu shortcut.
"""

import ctypes
import logging
import os
import shutil
import subprocess
import sys
import time
import winreg
from ctypes import wintypes
from pathlib import Path

from . import __version__, paths, product

log = logging.getLogger("kef_controller")

INSTALL_ARGUMENT = "--install"
UNINSTALL_ARGUMENT = "--uninstall"
SILENT_ARGUMENT = "--silent"
PURGE_ARGUMENT = "--purge"
STARTUP_ARGUMENT = "--startup"
# Processes the elevated part must not stop: the copy that asked for it.
SPARE_ARGUMENT = "--spare-pids"

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\KEFLSXController"
# Always the 64-bit registry: the entry must be where Windows looks for it.
REGISTRY_VIEW = winreg.KEY_WOW64_64KEY

# "Run with Windows" is a per-account choice, made from the tray menu.
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = product.APP_NAME

# Named event every instance listens on: set, it makes the instance quit.
QUIT_EVENT_NAME = "Local\\KEF.LSX.Controller.Quit"

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
STOP_GRACE_S = 8.0
EVENT_MODIFY_STATE = 0x0002


class SetupError(Exception):
    """A step of the installation failed; the message says which."""


# ------------------------------------------------------------------ versions


def installed_version():
    """Version registered with Windows, None if not installed."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY, 0,
                            winreg.KEY_READ | REGISTRY_VIEW) as key:
            value, _kind = winreg.QueryValueEx(key, "DisplayVersion")
    except OSError:
        return None
    return str(value) if paths.installed_exe().exists() else None


# ------------------------------------------------------- Run with Windows


def startup_command():
    """The command the Run entry holds for this very program."""
    if paths.is_frozen():
        return f'"{sys.executable}" {STARTUP_ARGUMENT}'
    script_path = Path(sys.argv[0]).resolve()
    return f'"{sys.executable}" "{script_path}" {STARTUP_ARGUMENT}'


def _startup_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE)
            return value
    except OSError:
        return None


def is_startup_enabled():
    value = _startup_value()
    return value is not None and value.lower() == startup_command().lower()


def set_startup(enabled, command=None):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_WRITE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ,
                                  command or startup_command())
            else:
                winreg.DeleteValue(key, RUN_VALUE)
    except OSError:
        pass


# ------------------------------------------------------------ small helpers


def _powershell(script):
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
    )
    return result.stdout


def _ps_quote(text):
    """A PowerShell single-quoted literal."""
    return "'" + str(text).replace("'", "''") + "'"


def _create_link(link, target):
    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({_ps_quote(link)}); "
        f"$s.TargetPath = {_ps_quote(target)}; "
        f"$s.WorkingDirectory = {_ps_quote(target.parent)}; "
        f"$s.Description = {_ps_quote(product.APP_NAME)}; "
        f"$s.IconLocation = {_ps_quote(str(target) + ',0')}; "
        "$s.Save()"
    )
    _powershell(script)


def start_menu_link():
    program_data = Path(os.environ.get("ProgramData") or r"C:\ProgramData")
    return (program_data / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            / f"{product.APP_NAME}.lnk")


# ------------------------------------------------------ running instances


def _own_pids():
    # A one-file executable is two processes: the bootloader and its child.
    return {os.getpid(), os.getppid()}


def _running_instances(spare):
    """Processes of the application, whatever their version and location,
    and instances run from the sources (`python main.py`)."""
    script = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "($_.Name -like 'KEF*LSX*Controller*.exe') -or "
        "($_.Name -like 'python*' -and $_.CommandLine -like '*Kef LSX Control*main.py*') "
        "} | ForEach-Object { $_.ProcessId }"
    )
    found = [int(pid) for pid in _powershell(script).split() if pid.isdigit()]
    spare = spare | _own_pids()
    return [pid for pid in found if pid not in spare]


def _signal_quit():
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenEventW.restype = wintypes.HANDLE
    event = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, QUIT_EVENT_NAME)
    if event:
        kernel32.SetEvent(event)
        kernel32.CloseHandle(event)


def stop_instances(spare=frozenset()):
    """Ask every instance to exit, then stop those still there."""
    if not _running_instances(spare):
        return
    log.info("Fermeture des instances en cours")
    _signal_quit()
    deadline = time.monotonic() + STOP_GRACE_S
    while time.monotonic() < deadline and _running_instances(spare):
        time.sleep(0.5)
    for pid in _running_instances(spare):
        log.info("Arrêt forcé du processus %s, qui ne s'est pas fermé seul", pid)
        subprocess.run(["taskkill.exe", "/F", "/PID", str(pid)],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
    time.sleep(0.5)


# -------------------------------------------------------- elevated: install


def install(source, spare):
    """The privileged part of an installation or an update."""
    stop_instances(spare)
    target = paths.installed_exe()
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        staging = target.with_name(target.name + ".new")
        shutil.copy2(source, staging)
        # The old executable may take a moment to be released by the
        # processes that were just stopped.
        for _attempt in range(30):
            try:
                os.replace(staging, target)
                break
            except PermissionError:
                time.sleep(0.5)
        else:
            staging.unlink(missing_ok=True)
            raise SetupError(f"{target} is still in use")
    _remove_legacy_copy()
    _register(target)
    _create_link(start_menu_link(), target)
    log.info("%s %s installé dans %s", product.APP_NAME, __version__, target.parent)


def _remove_legacy_copy():
    legacy = paths.legacy_exe()
    if not legacy.exists():
        return
    try:
        legacy.unlink()
        legacy.parent.rmdir()  # only if nothing else lives there
    except OSError:
        pass
    log.info("Ancienne copie supprimée : %s", legacy)


def _register(target):
    """The "Installed apps" entry."""
    command = f'"{target}"'
    values = {
        "DisplayName": (winreg.REG_SZ, product.APP_NAME),
        "DisplayVersion": (winreg.REG_SZ, __version__),
        "Publisher": (winreg.REG_SZ, product.AUTHOR),
        "DisplayIcon": (winreg.REG_SZ, f"{command},0"),
        "InstallLocation": (winreg.REG_SZ, str(target.parent)),
        "UninstallString": (winreg.REG_SZ, f"{command} {UNINSTALL_ARGUMENT}"),
        "QuietUninstallString": (
            winreg.REG_SZ, f"{command} {UNINSTALL_ARGUMENT} {SILENT_ARGUMENT}"),
        "URLInfoAbout": (winreg.REG_SZ, product.REPOSITORY_URL),
        "HelpLink": (winreg.REG_SZ, product.RELEASES_URL),
        "EstimatedSize": (winreg.REG_DWORD, max(1, target.stat().st_size // 1024)),
        "NoModify": (winreg.REG_DWORD, 1),
        "NoRepair": (winreg.REG_DWORD, 1),
    }
    access = winreg.KEY_WRITE | REGISTRY_VIEW
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY, 0, access) as key:
        for name, (kind, value) in values.items():
            winreg.SetValueEx(key, name, 0, kind, value)


# ------------------------------------------------------ elevated: uninstall


def uninstall(spare):
    """The privileged part of a removal.

    The executable cannot delete itself while it runs: a detached helper
    removes the folder once every process has let go of it.
    """
    stop_instances(spare)
    try:
        winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY, REGISTRY_VIEW)
    except OSError:
        pass
    start_menu_link().unlink(missing_ok=True)
    _remove_later(paths.install_dir())
    log.info("%s désinstallé", product.APP_NAME)


def _remove_later(folder):
    # Retried for ten minutes: the copy that asked for the removal runs
    # from this folder, and keeps its executable busy until its closing
    # message is dismissed.
    script = (
        "Start-Sleep -Seconds 2; "
        "for ($i = 0; $i -lt 600 -and (Test-Path -LiteralPath $d); $i++) { "
        "Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction SilentlyContinue; "
        "Start-Sleep -Seconds 1 }"
    )
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
         "-Command", f"$d = {_ps_quote(folder)}; {script}"],
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        close_fds=True,
    )


# ---------------------------------------------- the launching account's part


def after_install(first_install):
    """Point "Run with Windows" at the installed copy, then start it.

    Turned on at the first installation -- auto USB at boot is the point of
    the application --; on an update, kept only if it was on (whatever
    copy it pointed at), so that a choice to turn it off survives.
    """
    if first_install or _startup_value() is not None:
        set_startup(True, f'"{paths.installed_exe()}" {STARTUP_ARGUMENT}')
    start_installed()


def after_uninstall(purge):
    set_startup(False)
    if purge:
        logging.shutdown()  # releases the log file, which lives in that folder
        shutil.rmtree(paths.config_dir(), ignore_errors=True)


def spare_argument():
    """Arguments telling the elevated copy which processes to leave alone."""
    return [SPARE_ARGUMENT, ",".join(str(pid) for pid in sorted(_own_pids()))]


def parse_spare(argv):
    if SPARE_ARGUMENT not in argv:
        return set()
    index = argv.index(SPARE_ARGUMENT)
    try:
        return {int(pid) for pid in argv[index + 1].split(",") if pid.strip().isdigit()}
    except IndexError:
        return set()


def own_executable():
    return Path(sys.executable)


def start_installed():
    """Start the installed application, as the account that launched setup."""
    subprocess.Popen(
        [str(paths.installed_exe())],
        cwd=str(paths.install_dir()),
        creationflags=DETACHED_PROCESS,
        close_fds=True,
    )
