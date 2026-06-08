# sc2-replay-salt

Decode StarCraft II replay files and print a readable build order for a selected player.

## Easiest Use

For a normal Windows workflow:

1. Double-click `Install once.bat`. If Python is missing, it downloads and installs Python 3.12 from python.org first.
2. Drag one or more `.SC2Replay` files onto `Drop replays here.bat`.
3. Open the `build order.txt` file created next to each replay.

The drop script writes both the readable build order and the SALT import string. It writes one file per player so the user still gets a result. By default it extracts roughly the first 9 minutes, which is usually the useful practice window for a build order.

## Setup

Recommended:

```powershell
python -m pip install -e .[dev]
```

This installs the project into whichever `python` PowerShell is currently using. After that, run the tool with `python -m sc2_replay_salt`; this works even when Python's `Scripts` directory is not on `PATH`.

Optional virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

If PowerShell blocks activation scripts, run the venv's Python directly:

```powershell
.\.venv\Scripts\python -m pip install -e .[dev]
```

Local replay paths and the optional SC2ReplayStats session cookie live in `.env`, which is ignored by git.

## Usage

Use a real replay path. `C:\path\to\game.SC2Replay` is only a placeholder.

Analyze one replay:

```powershell
python -m sc2_replay_salt "C:\Users\pzixel\Documents\StarCraft II\Accounts\12345\7890\Replays\Multiplayer\Winter Madness LE (13).SC2Replay"
```

Analyze every replay in a folder:

```powershell
python -m sc2_replay_salt "C:\Users\pzixel\Documents\StarCraft II\Accounts\12345\7890\Replays\Multiplayer"
```

If you installed into `.venv` but did not activate it, use the venv Python explicitly:

```powershell
.\.venv\Scripts\python -m sc2_replay_salt "C:\path\to\game.SC2Replay"
```

`sc2-build-order` is also installed as a console script, but it only works when Python's `Scripts` directory is on `PATH`. If PowerShell says it is not recognized, keep using `python -m sc2_replay_salt`, or run the script by full path:

```powershell
.\.venv\Scripts\sc2-build-order "C:\path\to\game.SC2Replay"
```

Output is a three-column build-order table:

```text
supply  time   units/buildings/upgrades
```

Choose a player by id or name:

```powershell
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --player 2
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --player SomeName
```

If a replay has multiple players and the terminal is interactive, the tool asks which player to analyze. The selected player is remembered in your user profile and reused when that player appears in future replays. In non-interactive usage it falls back to the remembered player when possible, otherwise the first player.

Print the readable table and SALT import string together:

```powershell
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --player 2 --both
```

Print only a SALT import string:

```powershell
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --player 2 --salt
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --player 2 --salt --salt-title "TvZ Hellion Banshee"
```

SALT output follows the compact v4 format used by Spawning Tool. It omits workers, keeps only the first three supply providers, keeps only the first ten of any other item, and skips items that cannot fit the single-character SALT supply range.

By default the table omits starting-state units, worker production, temporary spell units, cosmetics, and type-change completion events. Useful flags:

```powershell
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --max-minutes 8
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --full-game
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --include-workers
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --include-starting-state
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --include-type-changes
```

## SC2ReplayStats validation

To compare decoded unit/building/upgrade state against an SC2ReplayStats replay page, put `SC2REPLAYSTATS_PHPSESSID` in `.env` and pass the replay URL explicitly:

```powershell
python -m sc2_replay_salt "C:\path\to\game.SC2Replay" --player 1 --max-minutes 3 --compare-replaystats https://sc2replaystats.com/replay/12345 --replaystats-team 0
```

The comparator uses the SC2ReplayStats embedded `units_alive`, `buildings`, and `upgrades` timelines. `--replaystats-team` is zero-based and normally maps to player order on the replay page.

## Tests

```powershell
python -m pytest
```
