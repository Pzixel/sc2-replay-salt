@echo off
setlocal
set "ROOT=%~dp0"
set "LOG=%ROOT%install-log.txt"

echo Setting up sc2-replay-salt...
echo Setup log for sc2-replay-salt>"%LOG%"
echo.>>"%LOG%"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo Creating the private Python environment...
    %PY% -m venv "%ROOT%.venv" >>"%LOG%" 2>>&1
    if errorlevel 1 goto failed
)

echo Updating the installer tools...
"%ROOT%.venv\Scripts\python.exe" -m pip --disable-pip-version-check install --upgrade pip setuptools wheel >>"%LOG%" 2>>&1
if errorlevel 1 goto failed

echo Installing the replay reader...
"%ROOT%.venv\Scripts\python.exe" -m pip --disable-pip-version-check install --no-build-isolation -e "%ROOT%." >>"%LOG%" 2>>&1
if errorlevel 1 goto failed

echo.
echo Ready. You can now drop .SC2Replay files onto "Drop replays here.bat".
echo.
pause
exit /b 0

:failed
echo.
echo Setup failed, but the details were saved to install-log.txt.
echo Make sure Python 3.10 or newer is installed, then run this file again.
echo.
pause
exit /b 1
