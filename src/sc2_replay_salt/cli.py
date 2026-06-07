from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .build_order import BuildOrderOptions, format_build_order, player_refs, replay_paths, resolve_player
from .replaystats import compare_reference, fetch_reference, format_comparison
from .sc2reader_backend import build_order_for_replay, load_replay, replay_players, replay_time_scale


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Print a readable build order from StarCraft II replay files.")
    parser.add_argument("path", type=Path, help="Replay file or directory containing .SC2Replay files.")
    parser.add_argument("--player", help="Player id or exact player name. Defaults to the first player.")
    parser.add_argument("--limit", type=int, help="Maximum number of replays to analyze from a directory.")
    parser.add_argument("--no-prompt", action="store_true", help="Do not ask for a player in interactive terminals.")
    parser.add_argument("--include-starting-state", action="store_true", help="Include units present at frame 0.")
    parser.add_argument("--include-type-changes", action="store_true", help="Include every unit type-change event.")
    parser.add_argument("--include-workers", action="store_true", help="Include worker production.")
    parser.add_argument("--max-minutes", type=float, help="Only print events up to this game minute.")
    parser.add_argument("--compare-replaystats", help="SC2ReplayStats replay URL to compare decoded state against.")
    parser.add_argument("--replaystats-team", type=int, default=0, help="SC2ReplayStats team slot to compare, zero-based.")
    args = parser.parse_args(argv)

    try:
        paths = replay_paths(args.path)
    except FileNotFoundError:
        print(f"Path does not exist: {args.path}", file=sys.stderr)
        return 2

    if args.limit is not None:
        paths = paths[: args.limit]
    if not paths:
        print(f"No .SC2Replay files found in {args.path}", file=sys.stderr)
        return 2

    exit_code = 0
    options = BuildOrderOptions(
        include_starting_state=args.include_starting_state,
        include_type_changes=args.include_type_changes,
        include_workers=args.include_workers,
        max_seconds=args.max_minutes * 60 if args.max_minutes is not None else None,
    )
    for index, path in enumerate(paths):
        if index:
            print("\n" + "=" * 72 + "\n")
        try:
            player_selector = args.player or _prompt_for_player(path, args.no_prompt)
            replay, player, items = build_order_for_replay(path, player_selector, options)
            replay_name = str(getattr(replay, "filename", None) or path.name)
            print(format_build_order(replay_name, player, items))
            if args.compare_replaystats:
                reference = fetch_reference(
                    args.compare_replaystats,
                    session_id=os.getenv("SC2REPLAYSTATS_PHPSESSID"),
                )
                max_seconds = int(args.max_minutes * 60) if args.max_minutes is not None else None
                result = compare_reference(
                    list(getattr(replay, "tracker_events", None) or []),
                    player,
                    reference,
                    team_index=args.replaystats_team,
                    max_seconds=max_seconds,
                    time_scale=replay_time_scale(replay),
                )
                print("")
                print(format_comparison(result))
        except Exception as exc:
            exit_code = 1
            print(f"{path}: {exc}", file=sys.stderr)

    return exit_code


def _prompt_for_player(path: Path, no_prompt: bool) -> str | None:
    if no_prompt or not sys.stdin.isatty():
        return None

    replay = load_replay(path)
    refs = player_refs(replay_players(replay))
    if len(refs) <= 1:
        return None

    print(f"{path.name} has multiple players:")
    for ref in refs:
        print(f"  {ref.label}")
    choice = input("Analyze player id/name [default first]: ").strip()
    if not choice:
        return None
    resolve_player(refs, choice)
    return choice
