#!/bin/sh
set -u

ROOT=$(CDPATH= cd "$(dirname "$0")" && pwd -P) || exit 1
LOG="$ROOT/drop-log.txt"
VENV_PY="$ROOT/.venv/bin/python"

PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH

printf '%s\n\n' 'Running sc2-replay-salt...' >"$LOG"
printf '%s\n' 'Working on your replay file. This can take a moment...'

if [ -x "$VENV_PY" ]; then
    PY=$VENV_PY
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    {
        printf '%s\n' 'Python was not found.'
        printf '%s\n' 'Install Python 3.10 or newer, then run sh "./Install once.sh".'
    } >>"$LOG"
    PY=
fi

if [ -n "$PY" ]; then
    "$PY" -m sc2_replay_salt --easy --no-prompt "$@" >>"$LOG" 2>&1
    STATUS=$?
else
    STATUS=1
fi

printf '\n'
cat "$LOG"
printf '\n'
exit "$STATUS"
