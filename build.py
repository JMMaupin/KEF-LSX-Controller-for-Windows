"""Build the Windows executable: dist\\KEF-LSX-Controller-<version>.exe.

Run through build.cmd, which prepares a dedicated virtual environment with
pinned PyInstaller and dependencies.

One file, so that installing or updating is running one file: started
from anywhere but its installation folder, it offers to install itself.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from kef_controller import __version__, product  # noqa: E402

BUILD = ROOT / "build"
DIST = ROOT / "dist"
VENV = ".venv-build"  # the environment build.cmd prepares
ICON = ROOT / "Kef-LSX-HP.ico"


def exe_stem():
    return f"KEF-LSX-Controller-{__version__}"


def version_resource():
    """The "Details" tab of the file's properties."""
    numbers = ([int(part) for part in __version__.split(".")] + [0, 0, 0, 0])[:4]
    fields = {
        "CompanyName": product.AUTHOR,
        "FileDescription": product.APP_NAME,
        "FileVersion": __version__,
        "InternalName": "KEFLSXController",
        "LegalCopyright": product.AUTHOR,
        "OriginalFilename": product.EXE_NAME,
        "ProductName": product.APP_NAME,
        "ProductVersion": __version__,
    }
    strings = ",\n".join(f"          StringStruct('{k}', '{v}')" for k, v in fields.items())
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tuple(numbers)}, prodvers={tuple(numbers)},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
{strings}
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    path = BUILD / "version_info.txt"
    path.write_text(text, encoding="utf-8")
    return path


def check_environment():
    """Refuses to build with any Python other than build.cmd's environment:
    the same sources must always give the same executable."""
    expected = (ROOT / VENV).resolve()
    if Path(sys.prefix).resolve() != expected:
        raise SystemExit(f"Run build.cmd: {sys.executable} is not the Python of {expected}")


def main():
    check_environment()
    import PyInstaller.__main__

    BUILD.mkdir(exist_ok=True)
    PyInstaller.__main__.run([
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", exe_stem(),
        "--icon", str(ICON),
        "--version-file", str(version_resource()),
        "--add-data", f"{ICON};.",
        "--collect-data", "customtkinter",
        "--hidden-import", "pystray._win32",
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "pyinstaller"),
        "--specpath", str(BUILD),
        str(ROOT / "main.py"),
    ])
    exe = DIST / f"{exe_stem()}.exe"
    print(f"\nBuilt {exe} ({exe.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
