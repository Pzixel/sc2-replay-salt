from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


TRACKED_EVENT_TYPES = {
    "UnitBornEvent": "born",
    "UnitInitEvent": "started",
}

COMMAND_PREFIXES = ("Research", "UpgradeTo", "Morph")
UNIT_COMMAND_PREFIXES = ("Train", "Build", "WarpIn")

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
        pid = _int_or_none(getattr(player, "pid", None))
        refs.append(
            PlayerRef(
                pid=pid if pid is not None else index,
                name=str(getattr(player, "name", f"Player {index}")),
                race=_str_or_none(getattr(player, "play_race", None) or getattr(player, "race", None)),
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
    items: list[BuildOrderItem] = []
    for event in sorted(event_list, key=_event_frame):
        event_type = type(event).__name__
        is_command = event_type.endswith("CommandEvent")
        is_type_change = event_type == "UnitTypeChangeEvent" and options.include_type_changes
        if event_type not in TRACKED_EVENT_TYPES and not is_command and not is_type_change:
            continue
        if _event_player_id(event) != player.pid:
            continue

        name = _command_name(event) if is_command else _event_name(event)
        if not name:
            continue

        frame = _event_frame(event)
        seconds = _event_seconds(event, frame) * options.display_time_scale
        food_cost = UNIT_FOOD_COSTS.get(name, 0.0)
        is_worker = name in WORKER_NAMES
        is_unit_command = is_command and food_cost > 0 and not is_worker
        if event_type == "UnitBornEvent" and has_command_events and food_cost > 0:
            if not is_worker:
                reserved_supply = max(0.0, reserved_supply - food_cost)
            continue
        if not options.include_starting_state and frame == 0:
            if is_unit_command:
                reserved_supply += food_cost
            continue
        if options.max_seconds is not None and seconds > options.max_seconds:
            if is_unit_command:
                reserved_supply += food_cost
            continue
        if _is_noise_name(name, options):
            if is_unit_command:
                reserved_supply += food_cost
            continue

        supply_used = _supply_at(supply_timeline, frame)
        if supply_used is not None:
            supply_used += int(reserved_supply)

        items.append(
            BuildOrderItem(
                frame=frame,
                seconds=seconds,
                name=_friendly_name(name),
                supply_used=supply_used,
            )
        )
        if is_unit_command:
            reserved_supply += food_cost

    return sorted(items, key=lambda item: (item.frame, item.name))


def format_build_order(replay_name: str, player: PlayerRef, items: Sequence[BuildOrderItem]) -> str:
    lines = [f"{replay_name}", f"Player: {player.label}", ""]
    lines.extend(_format_grouped_items(items))
    if not items:
        lines.append("(no build-order events found)")
    return "\n".join(lines)


def _event_player_id(event: object) -> int | None:
    event_player = getattr(event, "player", None)
    value = _int_or_none(getattr(event_player, "pid", None))
    if value is not None:
        return value

    for attr in ("control_pid", "upkeep_pid", "pid"):
        value = _int_or_none(getattr(event, attr, None))
        if value is not None:
            return value

    for owner_attr in ("unit_controller", "unit_upkeeper", "unit"):
        owner = getattr(event, owner_attr, None)
        value = _int_or_none(getattr(owner, "pid", None))
        if value is not None:
            return value
        nested_owner = getattr(owner, "owner", None)
        value = _int_or_none(getattr(nested_owner, "pid", None))
        if value is not None:
            return value

    return None


def _event_name(event: object) -> str | None:
    for attr in ("unit_type_name", "upgrade_type_name"):
        value = _str_or_none(getattr(event, attr, None))
        if value:
            return value

    unit = getattr(event, "unit", None)
    if unit is not None:
        value = _unit_name_at_frame(unit, _event_frame(event))
        if value:
            return value
        for attr in ("name", "type_name", "unit_type_name"):
            value = _str_or_none(getattr(unit, attr, None))
            if value:
                return value
        unit_type = getattr(unit, "type", None)
        value = _str_or_none(getattr(unit_type, "name", None))
        if value:
            return value

    value = _str_or_none(getattr(event, "name", None))
    if value:
        return value

    upgrade = getattr(event, "upgrade_type", None)
    return _str_or_none(getattr(upgrade, "name", None))


def _command_name(event: object) -> str | None:
    ability_name = _str_or_none(getattr(event, "ability_name", None))
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


def _is_noise_name(name: str, options: BuildOrderOptions) -> bool:
    if name in NOISE_NAMES or any(name.startswith(prefix) for prefix in NOISE_NAME_PREFIXES):
        return True
    return not options.include_workers and name in WORKER_NAMES


def _unit_name_at_frame(unit: object, frame: int) -> str | None:
    type_history = getattr(unit, "type_history", None)
    if not type_history:
        return None

    current_name: str | None = None
    for type_frame, unit_type in type_history.items():
        if type_frame > frame:
            break
        current_name = _str_or_none(getattr(unit_type, "name", None))
    return current_name


def _event_frame(event: object) -> int:
    value = _int_or_none(getattr(event, "frame", None))
    if value is not None:
        return value
    value = _int_or_none(getattr(event, "frames", None))
    return value if value is not None else 0


def _event_seconds(event: object, frame: int) -> float:
    value = getattr(event, "second", None)
    if isinstance(value, (int, float)):
        return float(value)
    return frame / 16


def _supply_timeline(events: Sequence[object], pid: int) -> list[tuple[int, int]]:
    timeline: list[tuple[int, int]] = []
    for event in events:
        if type(event).__name__ != "PlayerStatsEvent":
            continue
        if _int_or_none(getattr(event, "pid", None)) != pid:
            continue
        food_used = getattr(event, "food_used", None)
        if isinstance(food_used, (int, float)):
            timeline.append((_event_frame(event), int(food_used)))
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


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
