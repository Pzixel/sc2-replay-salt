from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .build_order import BuildOrderItem, BuildOrderOptions, PlayerRef, extract_build_order, resolve_player


def load_replay(path: Path) -> object:
    try:
        import sc2reader
    except ImportError as exc:
        raise RuntimeError("Install dependencies with `python -m pip install -e .`.") from exc

    return sc2reader.load_replay(str(path), load_level=4)


def replay_players(replay: object) -> list[object]:
    return list(getattr(replay, "players", None) or getattr(replay, "people", None) or [])


def replay_events(replay: object) -> list[object]:
    tracker_events = list(getattr(replay, "tracker_events", None) or [])
    game_events = list(getattr(replay, "game_events", None) or [])
    if tracker_events or game_events:
        return tracker_events + game_events
    return list(getattr(replay, "events", None) or [])


def build_order_for_replay(
    path: Path,
    player_selector: str | None,
    options: BuildOrderOptions | None = None,
) -> tuple[object, PlayerRef, list[BuildOrderItem]]:
    replay = load_replay(path)
    options = _with_replay_time_scale(options or BuildOrderOptions(), replay)
    player = resolve_player(replay_players(replay), player_selector)
    items = extract_build_order(replay_events(replay), player, options)
    return replay, player, items


def _with_replay_time_scale(options: BuildOrderOptions, replay: object) -> BuildOrderOptions:
    return replace(options, display_time_scale=replay_time_scale(replay))


def replay_time_scale(replay: object) -> float:
    speed = str(getattr(replay, "speed", "") or "").casefold()
    if speed == "faster":
        return 1 / 1.4
    if speed == "fast":
        return 1 / 1.2
    if speed == "slow":
        return 1 / 0.8
    if speed == "slower":
        return 1 / 0.6
    return 1.0
