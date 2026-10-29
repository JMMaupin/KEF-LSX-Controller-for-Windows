@echo off
rem Builds dist\KEF-LSX-Controller-<version>.exe.
rem PyInstaller and the dependencies live in a dedicated environment,
rem .venv-build, pinned to exact versions: the system Python is left
rem untouched, and two builds of the same sources give the same executable.
setlocal
cd /d "%~dp0"
set VENV=.venv-build

if not exist "%VENV%\Scripts\python.exe" (
    echo Creating %VENV%...
    python -m venv "%VENV%" || goto :error
)
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check --quiet "pyinstaller==6.22.3" -r requirements.txt || goto :error
"%VENV%\Scripts\python.exe" build.py || goto :error
exit /b 0

:error
echo Build failed.
exit /b 1
