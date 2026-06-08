@echo off
setlocal
set "ROOT=%~dp0"
set "LOG=%ROOT%drop-log.txt"
set "PYTHONPATH=%ROOT%src;%PYTHONPATH%"
echo Running sc2-replay-salt...>"%LOG%"
echo.>>"%LOG%"
echo Working on your replay file. This can take a moment...

if exist "%ROOT%.venv\Scripts\python.exe" (
    "%ROOT%.venv\Scripts\python.exe" -m sc2_replay_salt --easy --no-prompt %* >>"%LOG%" 2>>&1
) else (
    where py >nul 2>nul
    if %ERRORLEVEL%==0 (
    py -3 -m sc2_replay_salt --easy --no-prompt %* >>"%LOG%" 2>>&1
    ) else (
    python -m sc2_replay_salt --easy --no-prompt %* >>"%LOG%" 2>>&1
    )
)

echo.
type "%LOG%"
echo.
