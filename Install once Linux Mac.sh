#!/bin/sh
set -u

ROOT=$(CDPATH= cd "$(dirname "$0")" && pwd -P) || exit 1
LOG="$ROOT/install-log.txt"
VENV_PY="$ROOT/.venv/bin/python"

printf '%s\n\n' 'Setup log for sc2-replay-salt' >"$LOG"
printf '%s\n' 'Setting up sc2-replay-salt...'

fail() {
    printf '\n%s\n' 'Setup failed, but the details were saved to install-log.txt.'
    printf '%s\n' 'Run sh "./Install once.sh" again. If it still fails, send install-log.txt.'
    exit 1
}

PY=
if [ -x "$VENV_PY" ]; then
    PY=$VENV_PY
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    {
        printf '%s\n' 'Python was not found.'
        printf '%s\n' 'Install Python 3.10 or newer, then run this script again.'
    } >>"$LOG"
    fail
fi

if [ ! -x "$VENV_PY" ]; then
    printf '%s\n' 'Creating the private Python environment...'
    "$PY" -m venv "$ROOT/.venv" >>"$LOG" 2>&1 || fail
fi

printf '%s\n' 'Updating the installer tools...'
"$VENV_PY" -m pip --disable-pip-version-check install --upgrade pip setuptools wheel >>"$LOG" 2>&1 || fail

printf '%s\n' 'Installing the replay reader...'
"$VENV_PY" -m pip --disable-pip-version-check install --no-build-isolation -e "$ROOT/." >>"$LOG" 2>&1 || fail

printf '\n%s\n' 'Ready. You can now run sh "./Drop replays here.sh" with .SC2Replay files.'
