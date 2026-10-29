"""Running a short task with administrator rights.

The application itself never runs elevated: its tray icon, its window and
its settings belong to the signed-in account. Only the installation and
the removal, which write in Program Files and in the machine registry, are
handed to a second copy of the program, started through UAC with a
command-line argument that makes it do that one thing and exit.
"""

import ctypes
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_NOASYNC = 0x00000100
SW_HIDE = 0
WAIT_OBJECT_0 = 0
ERROR_CANCELLED = 1223  # the user declined the UAC prompt


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
shell32.ShellExecuteExW.restype = wintypes.BOOL
shell32.IsUserAnAdmin.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class ElevationCancelled(Exception):
    """The user declined the UAC prompt."""


def is_elevated():
    """True if this process already holds administrator rights."""
    try:
        return bool(shell32.IsUserAnAdmin())
    except OSError:
        return False


def own_command():
    """How to start this program again: the executable and its first arguments.

    Frozen into an exe, the program is the exe itself. From the sources, it
    is the interpreter and `main.py` -- `pythonw.exe` when available, so
    that the elevated copy does not flash a console window.
    """
    if getattr(sys, "frozen", False):
        return sys.executable, []
    interpreter = Path(sys.executable)
    windowless = interpreter.with_name("pythonw.exe")
    if windowless.exists():
        interpreter = windowless
    main = Path(__file__).resolve().parent.parent / "main.py"
    return str(interpreter), [str(main)]


def run_elevated(arguments, timeout_s=300.0):
    """Run this program again, elevated, with these arguments; return its exit code.

    Blocks until the elevated copy exits. Raises ElevationCancelled if the
    user declines, TimeoutError if the copy does not finish in time.
    """
    executable, prefix = own_command()
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    info.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    info.lpVerb = "runas"
    info.lpFile = executable
    info.lpParameters = subprocess.list2cmdline(prefix + list(arguments))
    info.nShow = SW_HIDE
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == ERROR_CANCELLED:
            raise ElevationCancelled()
        raise ctypes.WinError(error)
    try:
        waited = kernel32.WaitForSingleObject(info.hProcess, int(timeout_s * 1000))
        if waited != WAIT_OBJECT_0:
            raise TimeoutError("The elevated task did not finish in time")
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        return int(code.value)
    finally:
        kernel32.CloseHandle(info.hProcess)
