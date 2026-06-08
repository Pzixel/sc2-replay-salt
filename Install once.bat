@echo off
setlocal
set "ROOT=%~dp0"
set "LOG=%ROOT%install-log.txt"
set "PYTHON_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
set "PYTHON_INSTALLER=%ROOT%python-3.12.10-amd64.exe"

echo Setting up sc2-replay-salt...
echo Setup log for sc2-replay-salt>"%LOG%"
echo.>>"%LOG%"

set "PY="
if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PY=%ROOT%.venv\Scripts\python.exe"
)

if not defined PY (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PY=py -3"
    )
)

if not defined PY (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PY=python"
    )
)

if not defined PY (
    call :install_python
    if errorlevel 1 goto failed
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

:install_python
echo Python was not found. Installing Python 3.12...
echo Downloading Python 3.12 from python.org...
echo Python was not found. Downloading %PYTHON_URL%>>"%LOG%"
call :download_file
if errorlevel 1 exit /b 1

echo Running the Python installer...>>"%LOG%"
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0 SimpleInstall=1 >>"%LOG%" 2>>&1
if errorlevel 1 exit /b 1

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
    call :cleanup_python_installer
    exit /b 0
)

where py >nul 2>nul
if not errorlevel 1 (
    set "PY=py -3.12"
    call :cleanup_python_installer
    exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    call :cleanup_python_installer
    exit /b 0
)

exit /b 1

:download_file
where curl.exe >nul 2>nul
if not errorlevel 1 (
    curl.exe --fail --location --output "%PYTHON_INSTALLER%" "%PYTHON_URL%" >>"%LOG%" 2>>&1
    exit /b %ERRORLEVEL%
)

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'" >>"%LOG%" 2>>&1
exit /b %ERRORLEVEL%

:cleanup_python_installer
if exist "%PYTHON_INSTALLER%" (
    echo Cleaning up downloaded Python installer...
    echo Removing %PYTHON_INSTALLER%>>"%LOG%"
    del /q "%PYTHON_INSTALLER%" >>"%LOG%" 2>>&1
)
exit /b 0

:failed
echo.
echo Setup failed, but the details were saved to install-log.txt.
echo Close this window and run "Install once.bat" again. If it still fails, send install-log.txt.
echo.
pause
exit /b 1
