from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Iterable, Sequence

from .event_helpers import (
    event_frame,
    event_player_id,
    event_seconds,
    int_or_none,
    str_or_none,
    unit_name_at_frame,
)


TRACKED_EVENT_TYPES = {
    "UnitBornEvent": "born",
    "UnitInitEvent": "started",
}

COMMAND_PREFIXES = ("Research", "UpgradeTo", "Morph")
UNIT_COMMAND_PREFIXES = ("Train", "Build", "WarpIn")
COMMAND_MANAGER_REPEAT_FRAME_WINDOW = 32

NOISE_NAME_PREFIXES = (
    "Beacon",
    "RewardDance",
    "Spray",
)

NOISE_NAMES = {
    "BroodlingEscort",
    "Changeling",
    "GhostAlternate",
    "KD8Charge",
    "Larva",
    "LocustMP",
    "MULE",
}

WORKER_NAMES = {
    "Drone",
    "Probe",
    "SCV",
}

UNIT_FOOD_COSTS = {
    "Adept": 2.0,
    "Archon": 4.0,
    "Baneling": 0.5,
    "Banshee": 3.0,
    "Battlecruiser": 6.0,
    "BroodLord": 4.0,
    "Carrier": 6.0,
    "Colossus": 6.0,
    "Corruptor": 2.0,
    "Cyclone": 3.0,
    "DarkTemplar": 2.0,
    "Drone": 1.0,
    "Ghost": 2.0,
    "Hellion": 2.0,
    "HighTemplar": 2.0,
    "Hydralisk": 2.0,
    "Immortal": 4.0,
    "Infestor": 2.0,
    "Liberator": 3.0,
    "Marauder": 2.0,
    "Marine": 1.0,
    "Medivac": 2.0,
    "Mutalisk": 2.0,
    "Observer": 1.0,
    "Oracle": 3.0,
    "Overlord": 0.0,
    "Overseer": 0.0,
    "Phoenix": 2.0,
    "Probe": 1.0,
    "Queen": 2.0,
    "Ravager": 3.0,
    "Raven": 2.0,
    "Reaper": 1.0,
    "Roach": 2.0,
    "SCV": 1.0,
    "Sentry": 2.0,
    "SiegeTank": 3.0,
    "Stalker": 2.0,
    "SwarmHostMP": 3.0,
    "Tempest": 5.0,
    "Thor": 6.0,
    "Ultralisk": 6.0,
    "VikingFighter": 2.0,
    "Viper": 3.0,
    "VoidRay": 4.0,
    "WarpPrism": 2.0,
    "WidowMine": 2.0,
    "Zealot": 2.0,
    "Zergling": 0.5,
}


@dataclass(frozen=True)
class PlayerRef:
    pid: int
    name: str
    race: str | None = None

    @property
    def label(self) -> str:
        race = f", {self.race}" if self.race else ""
        return f"{self.pid}: {self.name}{race}"


@dataclass(frozen=True)
class BuildOrderItem:
    frame: int
    seconds: float
    name: str
    supply_used: int | None = None

    @property
    def time_label(self) -> str:
        total_seconds = int(self.seconds)
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}:{seconds:02d}"

    def format(self) -> str:
        supply = str(self.supply_used) if self.supply_used is not None else "?"
        return f"{supply:>3}  {self.time_label:>5}  {self.name}"


@dataclass(frozen=True)
class BuildOrderOptions:
    include_starting_state: bool = False
    include_type_changes: bool = False
    include_workers: bool = False
    max_seconds: float | None = None
    display_time_scale: float = 1.0


def replay_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("*.SC2Replay"))
    raise FileNotFoundError(path)


def player_refs(players: Sequence[object]) -> list[PlayerRef]:
    refs: list[PlayerRef] = []
    for index, player in enumerate(players, start=1):
        pid = int_or_none(getattr(player, "pid", None))
        refs.append(
            PlayerRef(
                pid=pid if pid is not None else index,
                name=str(getattr(player, "name", f"Player {index}")),
                race=str_or_none(getattr(player, "play_race", None) or getattr(player, "race", None)),
            )
        )
    return refs


def resolve_player(players: Sequence[object], selector: str | None) -> PlayerRef:
    refs = player_refs(players)
    if not refs:
        raise ValueError("Replay does not contain any players.")
    if selector is None:
        return refs[0]

    normalized = selector.casefold()
    for ref in refs:
        if str(ref.pid) == selector or ref.name.casefold() == normalized:
            return ref

    available = ", ".join(ref.label for ref in refs)
    raise ValueError(f"Unknown player '{selector}'. Available players: {available}")


def extract_build_order(
    events: Iterable[object],
    player: PlayerRef,
    options: BuildOrderOptions | None = None,
) -> list[BuildOrderItem]:
    options = options or BuildOrderOptions()
    event_list = list(events)
    supply_timeline = _supply_timeline(event_list, player.pid)
    has_command_events = any(type(event).__name__.endswith("CommandEvent") for event in event_list)
    reserved_supply = 0.0
    current_frame: int | None = None
    frame_start_reserved_supply = 0.0
    last_supply_used: int | None = None
    last_repeatable_unit_command: BuildOrderItem | None = None
    last_repeatable_unit_command_frame: int | None = None
    ignore_manager_repeat = False
    items: list[BuildOrderItem] = []
    pending_unit_commands: dict[str, list[BuildOrderItem]] = {}
    for event in sorted(event_list, key=event_frame):
        frame = event_frame(event)
        if frame != current_frame:
            current_frame = frame
            frame_start_reserved_supply = reserved_supply

        event_type = type(event).__name__
        is_command = event_type.endswith("CommandEvent")
        is_command_manager_state = event_type == "CommandManagerStateEvent"
        is_type_change = event_type == "UnitTypeChangeEvent" and options.include_type_changes
        if event_type not in TRACKED_EVENT_TYPES and not is_command and not is_type_change and not is_command_manager_state:
            continue
        if event_player_id(event) != player.pid:
            continue

        if is_command_manager_state:
            if (
                last_repeatable_unit_command is None
                or last_repeatable_unit_command_frame is None
                or ignore_manager_repeat
                or frame - last_repeatable_unit_command_frame > COMMAND_MANAGER_REPEAT_FRAME_WINDOW
            ):
                continue

            supply_used = _supply_at(supply_timeline, frame)
            if supply_used is not None:
                supply_used += int(frame_start_reserved_supply)
                supply_used = _monotonic_supply(supply_used, last_supply_used)

            item = BuildOrderItem(
                frame=frame,
                seconds=event_seconds(event, frame, options.display_time_scale),
                name=last_repeatable_unit_command.name,
                supply_used=supply_used,
            )
            items.append(item)
            pending_unit_commands.setdefault(_compact_name(item.name), []).append(item)
            food_cost = UNIT_FOOD_COSTS.get(_compact_name(item.name), 0.0)
            reserved_supply += food_cost
            last_supply_used = item.supply_used
            last_repeatable_unit_command = item
            last_repeatable_unit_command_frame = frame
            ignore_manager_repeat = True
            continue

        name = _command_name(event) if is_command else _event_name(event)
        if not name:
            continue

        seconds = event_seconds(event, frame, options.display_time_scale)
        food_cost = UNIT_FOOD_COSTS.get(name, 0.0)
        is_worker = name in WORKER_NAMES
        is_unit_command = is_command and food_cost > 0 and not is_worker
        if event_type == "UnitBornEvent" and has_command_events and food_cost > 0:
            if is_worker:
                continue

            pending_items = pending_unit_commands.get(name)
            if pending_items:
                pending_items.pop(0)
                reserved_supply = max(0.0, reserved_supply - food_cost)
            continue
        if _should_skip_item(name, frame, seconds, options):
            if is_unit_command:
                reserved_supply += food_cost
                last_repeatable_unit_command = None
                last_repeatable_unit_command_frame = None
                ignore_manager_repeat = False
            continue

        supply_used = _supply_at(supply_timeline, frame)
        if supply_used is not None:
            supply_used += int(frame_start_reserved_supply)
            supply_used = _monotonic_supply(supply_used, last_supply_used)

        quantity = _command_quantity(event) if is_unit_command else 1
        command_items = [
            BuildOrderItem(
                frame=frame,
                seconds=seconds,
                name=_friendly_name(name),
                supply_used=supply_used,
            )
            for _ in range(quantity)
        ]
        items.extend(command_items)
        if is_unit_command:
            pending_unit_commands.setdefault(name, []).extend(command_items)
            reserved_supply += food_cost
            last_repeatable_unit_command = command_items[-1]
            last_repeatable_unit_command_frame = frame
            ignore_manager_repeat = quantity > 1
        elif is_command:
            last_repeatable_unit_command = None
            last_repeatable_unit_command_frame = None
            ignore_manager_repeat = False

        if command_items:
            last_supply_used = command_items[-1].supply_used

    return sorted(items, key=lambda item: (item.frame, item.seconds))


def format_build_order(replay_name: str, player: PlayerRef, items: Sequence[BuildOrderItem]) -> str:
    lines = [f"{replay_name}", f"Player: {player.label}", ""]
    lines.extend(_format_grouped_items(items))
    if not items:
        lines.append("(no build-order events found)")
    return "\n".join(lines)


def _command_quantity(event: object) -> int:
    flags = getattr(event, "flag", None)
    if isinstance(flags, dict) and flags.get("repeat"):
        return 2
    return 1


def _monotonic_supply(supply_used: int | None, last_supply_used: int | None) -> int | None:
    if supply_used is None or last_supply_used is None:
        return supply_used
    return max(supply_used, last_supply_used)


def _compact_name(name: str) -> str:
    return "".join(name.split())


def _event_name(event: object) -> str | None:
    for attr in ("unit_type_name", "upgrade_type_name"):
        value = str_or_none(getattr(event, attr, None))
        if value:
            return value

    unit = getattr(event, "unit", None)
    if unit is not None:
        value = unit_name_at_frame(unit, event_frame(event))
        if value:
            return value
        for attr in ("name", "type_name", "unit_type_name"):
            value = str_or_none(getattr(unit, attr, None))
            if value:
                return value
        unit_type = getattr(unit, "type", None)
        value = str_or_none(getattr(unit_type, "name", None))
        if value:
            return value

    value = str_or_none(getattr(event, "name", None))
    if value:
        return value

    upgrade = getattr(event, "upgrade_type", None)
    return str_or_none(getattr(upgrade, "name", None))


def _command_name(event: object) -> str | None:
    ability_name = str_or_none(getattr(event, "ability_name", None))
    if not ability_name:
        ability_name = _fallback_ability_name(event)
    if not ability_name:
        return None

    for prefix in COMMAND_PREFIXES:
        if ability_name.startswith(prefix):
            return ability_name[len(prefix) :]
    for prefix in UNIT_COMMAND_PREFIXES:
        if ability_name.startswith(prefix):
            name = ability_name[len(prefix) :]
            if name in UNIT_FOOD_COSTS:
                return name
    return None


def _fallback_ability_name(event: object) -> str | None:
    ability_id = int_or_none(getattr(event, "ability_id", None))
    ability_link = int_or_none(getattr(event, "ability_link", None))
    command_index = int_or_none(getattr(event, "command_index", None))
    if ability_link is None and ability_id is not None:
        ability_link = ability_id >> 5
    if command_index is None and ability_id is not None:
        command_index = ability_id & 0x1F
    if ability_link is None or command_index is None:
        return None
    return _ability_command_lookup().get((ability_link, command_index))


@lru_cache(maxsize=1)
def _ability_command_lookup() -> dict[tuple[int, int], str]:
    data_path = resources.files("sc2reader").joinpath("data")
    command_by_group_and_index = _command_by_group_and_index(data_path.joinpath("ability_lookup.csv"))
    group_by_link = _latest_ability_group_by_link(data_path.joinpath("LotV"))
    lookup: dict[tuple[int, int], str] = {}
    for ability_link, group_name in group_by_link.items():
        group_commands = command_by_group_and_index.get(group_name, {})
        for command_index in range(32):
            command_name = group_commands.get(command_index)
            if command_name == group_name:
                command_name = None
            lookup_name = group_commands.get(command_index + 1) or command_name
            if lookup_name and lookup_name != group_name:
                lookup[(ability_link, command_index)] = lookup_name
    return lookup


def _command_by_group_and_index(path: object) -> dict[str, dict[int, str]]:
    result: dict[str, dict[int, str]] = {}
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            if not row:
                continue
            result[row[0]] = {index: value for index, value in enumerate(row) if value}
    return result


def _latest_ability_group_by_link(directory: object) -> dict[int, str]:
    latest_build_by_link: dict[int, int] = {}
    group_by_link: dict[int, str] = {}
    for path in directory.iterdir():
        if not path.name.endswith("_abilities.csv"):
            continue
        build_text = path.name.split("_", 1)[0]
        if not build_text.isdigit():
            continue
        build = int(build_text)
        with path.open(newline="") as handle:
            for row in csv.reader(handle):
                if len(row) < 2 or not row[0].isdigit() or not row[1]:
                    continue
                ability_link = int(row[0])
                if build >= latest_build_by_link.get(ability_link, -1):
                    latest_build_by_link[ability_link] = build
                    group_by_link[ability_link] = row[1]
    return group_by_link


def _is_noise_name(name: str, options: BuildOrderOptions) -> bool:
    if name in NOISE_NAMES or any(name.startswith(prefix) for prefix in NOISE_NAME_PREFIXES):
        return True
    return not options.include_workers and name in WORKER_NAMES


def _should_skip_item(name: str, frame: int, seconds: float, options: BuildOrderOptions) -> bool:
    if not options.include_starting_state and frame == 0:
        return True
    if options.max_seconds is not None and seconds > options.max_seconds:
        return True
    return _is_noise_name(name, options)


def _supply_timeline(events: Sequence[object], pid: int) -> list[tuple[int, int]]:
    timeline: list[tuple[int, int]] = []
    for event in events:
        if type(event).__name__ != "PlayerStatsEvent":
            continue
        if int_or_none(getattr(event, "pid", None)) != pid:
            continue
        food_used = getattr(event, "food_used", None)
        if isinstance(food_used, (int, float)):
            timeline.append((event_frame(event), int(food_used)))
    return sorted(timeline)


def _supply_at(timeline: Sequence[tuple[int, int]], frame: int) -> int | None:
    supply: int | None = None
    for stat_frame, stat_supply in timeline:
        if stat_frame > frame:
            break
        supply = stat_supply
    return supply


def _format_grouped_items(items: Sequence[BuildOrderItem]) -> list[str]:
    grouped: dict[tuple[int | None, int], list[str]] = {}
    for item in items:
        grouped.setdefault((item.supply_used, int(item.seconds)), []).append(item.name)

    lines: list[str] = []
    for (supply, seconds), names in grouped.items():
        supply_label = str(supply) if supply is not None else "?"
        minutes, second = divmod(seconds, 60)
        lines.append(f"{supply_label:>3}\t{minutes}:{second:02d}\t{_summarize_names(names)}")
    return lines


def _summarize_names(names: Sequence[str]) -> str:
    parts: list[str] = []
    for name in dict.fromkeys(names):
        count = names.count(name)
        parts.append(f"{name} x{count}" if count > 1 else name)
    return ", ".join(parts)


def _friendly_name(name: str) -> str:
    normalized = name
    for suffix in ("Lowered", "Flying"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    if normalized == "TechLab":
        normalized = "Tech Lab"
    return _split_camel_case(normalized)


def _split_camel_case(value: str) -> str:
    if value.isupper():
        return value

    words: list[str] = []
    start = 0
    for index in range(1, len(value)):
        previous = value[index - 1]
        current = value[index]
        next_char = value[index + 1] if index + 1 < len(value) else ""
        starts_word = current.isupper() and (
            previous.islower() or previous.isdigit() or (previous.isupper() and next_char.islower())
        )
        if starts_word:
            words.append(value[start:index])
            start = index
    words.append(value[start:])
    return " ".join(words)
