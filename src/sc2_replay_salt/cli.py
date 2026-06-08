from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from .build_order import BuildOrderItem, BuildOrderOptions, PlayerRef, format_build_order, player_refs, replay_paths, resolve_player
from .defaults import load_defaults, save_defaults
from .replaystats import compare_reference, fetch_reference, format_comparison
from .salt import format_salt_encoding
from .sc2reader_backend import build_order_for_replay, load_replay, replay_players, replay_time_scale


DEFAULT_MAX_MINUTES = 9.0
ALL_PLAYERS = object()


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Print a readable build order from StarCraft II replay files.")
    parser.add_argument("paths", nargs="*", type=Path, help="Replay files or folders containing .SC2Replay files.")
    parser.add_argument("--player", help="Player id or exact player name. Defaults to the remembered player when possible.")
    parser.add_argument("--limit", type=int, help="Maximum number of replays to analyze from a directory.")
    parser.add_argument("--no-prompt", action="store_true", help="Do not ask for a player in interactive terminals.")
    parser.add_argument("--include-starting-state", action="store_true", help="Include units present at frame 0.")
    parser.add_argument("--include-type-changes", action="store_true", help="Include every unit type-change event.")
    parser.add_argument("--include-workers", action="store_true", help="Include worker production.")
    parser.add_argument("--max-minutes", type=float, help=f"Only print events up to this game minute. Defaults to {DEFAULT_MAX_MINUTES:g}.")
    parser.add_argument("--full-game", action="store_true", help="Do not apply the default 9-minute build-order limit.")
    parser.add_argument("--salt", action="store_true", help="Print SALT encoding instead of a readable build order.")
    parser.add_argument("--both", action="store_true", help="Print readable build order and SALT encoding together.")
    parser.add_argument("--salt-title", help="Title to embed in SALT output. Defaults to the replay file name.")
    parser.add_argument("--easy", action="store_true", help="Friendly drag-and-drop mode: write build-order text files next to the replays.")
    parser.add_argument("--compare-replaystats", help="SC2ReplayStats replay URL to compare decoded state against.")
    parser.add_argument("--replaystats-team", type=int, default=0, help="SC2ReplayStats team slot to compare, zero-based.")
    args = parser.parse_args(argv)

    if not args.paths:
        message = "Drop one or more .SC2Replay files onto 'Drop replays here.bat' or pass a replay path."
        print(message, file=sys.stderr if not args.easy else sys.stdout)
        return 2

    defaults = load_defaults()
    try:
        paths = _collect_replay_paths(args.paths)
    except FileNotFoundError as exc:
        print(f"Path does not exist: {exc}", file=sys.stderr)
        return 2

    if args.limit is not None:
        paths = paths[: args.limit]
    if not paths:
        print("No .SC2Replay files found.", file=sys.stderr)
        return 2

    exit_code = 0
    max_seconds = _max_seconds(args.max_minutes, args.full_game)
    options = BuildOrderOptions(
        include_starting_state=args.include_starting_state,
        include_type_changes=args.include_type_changes,
        include_workers=args.include_workers,
        max_seconds=max_seconds,
    )
    for index, path in enumerate(paths):
        if index and not args.easy:
            print("\n" + "=" * 72 + "\n")
        try:
            player_selector = args.player or _player_selector(
                path,
                args.no_prompt,
                defaults,
                all_on_no_prompt=args.easy,
            )
            if args.easy and player_selector is ALL_PLAYERS:
                _write_easy_outputs_for_all_players(path, options, args.salt_title, defaults)
                continue
            if player_selector is ALL_PLAYERS:
                player_selector = None
            replay, player, items = build_order_for_replay(path, player_selector, options)
            replay_name = str(getattr(replay, "filename", None) or path.name)
            salt_title = args.salt_title or Path(replay_name).stem
            if args.easy or args.both:
                output = format_combined_output(replay_name, player, items, salt_title)
            elif args.salt:
                output = format_salt_encoding(items, salt_title)
            else:
                output = format_build_order(replay_name, player, items)

            _remember_player(defaults, player.name)
            if args.easy:
                output_path = _easy_output_path(path)
                output_path.write_text(output + "\n", encoding="utf-8")
                print(f"Wrote {output_path}")
            else:
                print(output)
            if args.compare_replaystats:
                reference = fetch_reference(
                    args.compare_replaystats,
                    session_id=os.getenv("SC2REPLAYSTATS_PHPSESSID"),
                )
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


def format_combined_output(
    replay_name: str,
    player: PlayerRef,
    items: Sequence[BuildOrderItem],
    salt_title: str,
) -> str:
    return f"{format_build_order(replay_name, player, items)}\n\nSALT:\n{format_salt_encoding(items, salt_title)}"


def _collect_replay_paths(paths: Sequence[Path]) -> list[Path]:
    replay_files: list[Path] = []
    for path in paths:
        replay_files.extend(replay_paths(path))
    return replay_files


def _write_easy_outputs_for_all_players(
    path: Path,
    options: BuildOrderOptions,
    salt_title: str | None,
    defaults: dict[str, object],
) -> None:
    replay = load_replay(path)
    refs = player_refs(replay_players(replay))
    for ref in refs:
        replay, player, items = build_order_for_replay(path, str(ref.pid), options)
        replay_name = str(getattr(replay, "filename", None) or path.name)
        output = format_combined_output(replay_name, player, items, salt_title or Path(replay_name).stem)
        output_path = _easy_output_path(path, player)
        output_path.write_text(output + "\n", encoding="utf-8")
        print(f"Wrote {output_path}")


def _max_seconds(max_minutes: float | None, full_game: bool) -> float | None:
    if full_game:
        return None
    return (max_minutes if max_minutes is not None else DEFAULT_MAX_MINUTES) * 60


def _player_selector(
    path: Path,
    no_prompt: bool,
    defaults: dict[str, object],
    all_on_no_prompt: bool = False,
) -> str | object | None:
    remembered = _remembered_player(defaults)
    replay = load_replay(path)
    refs = player_refs(replay_players(replay))
    if remembered:
        for ref in refs:
            if ref.name.casefold() == remembered.casefold() or str(ref.pid) == remembered:
                return remembered

    if no_prompt or not sys.stdin.isatty():
        if all_on_no_prompt and len(refs) > 1:
            return ALL_PLAYERS
        return None

    if len(refs) <= 1:
        return None

    print(f"{path.name} has multiple players:")
    for ref in refs:
        print(f"  {ref.label}")
    try:
        choice = input("Analyze player id/name [default first; remembered next time]: ").strip()
    except EOFError:
        return ALL_PLAYERS
    if not choice:
        return None
    resolve_player(refs, choice)
    return choice


def _remembered_player(defaults: dict[str, object]) -> str | None:
    player = defaults.get("player")
    return player if isinstance(player, str) and player.strip() else None


def _remember_player(defaults: dict[str, object], player: str) -> None:
    if defaults.get("player") == player:
        return
    defaults["player"] = player
    try:
        save_defaults(defaults)
    except OSError:
        pass


def _easy_output_path(path: Path, player: PlayerRef | None = None) -> Path:
    player_suffix = f" - {_safe_filename_part(player.name)}" if player is not None else ""
    return path.with_name(f"{path.stem}{player_suffix} build order.txt")


def _safe_filename_part(value: str) -> str:
    return "".join(character if character not in '<>:"/\\|?*' else "_" for character in value).strip() or "player"
