from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONFIG_ENV = "SC2_REPLAY_SALT_CONFIG"


def config_path() -> Path:
    override = os.getenv(CONFIG_ENV)
    if override:
        return Path(override)

    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "sc2-replay-salt" / "defaults.json"
    return Path.home() / ".sc2-replay-salt" / "defaults.json"


def load_defaults() -> dict[str, Any]:
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_defaults(defaults: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(defaults, indent=2, sort_keys=True), encoding="utf-8")
