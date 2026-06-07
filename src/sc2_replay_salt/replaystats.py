from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Mapping, Sequence

import requests

from .build_order import PlayerRef

IGNORED_UPGRADE_PREFIXES = ("rewarddance", "spray")
IGNORED_UPGRADES = {"ghostalternate"}


@dataclass(frozen=True)
class ReplayStatsReference:
    units_alive: dict[int, list[dict[str, int]]]
    buildings: dict[int, list[dict[str, dict[str, int] | list[object]]]]
    upgrades: dict[int, list[dict[str, int] | list[object]]]

    @property
    def sample_seconds(self) -> list[int]:
        return sorted(set(self.units_alive) | set(self.buildings) | set(self.upgrades))


@dataclass(frozen=True)
class SampleDifference:
    seconds: int
    bucket: str
    name: str
    local: int
    reference: int


@dataclass(frozen=True)
class ComparisonResult:
    checked_samples: int
    differences: list[SampleDifference]

    @property
    def matched(self) -> bool:
        return not self.differences


def fetch_reference(url: str, session_id: str | None = None) -> ReplayStatsReference:
    cookies = {"PHPSESSID": session_id} if session_id else None
    response = requests.get(url, cookies=cookies, timeout=30)
    response.raise_for_status()
    return parse_reference(response.text)


def parse_reference(page_html: str) -> ReplayStatsReference:
    return ReplayStatsReference(
        units_alive=_loads_timeline(page_html, "units_alive"),
        buildings=_loads_timeline(page_html, "buildings"),
        upgrades=_loads_timeline(page_html, "upgrades"),
    )


def compare_reference(
    events: Sequence[object],
    player: PlayerRef,
    reference: ReplayStatsReference,
    team_index: int,
    max_seconds: int | None = None,
    time_scale: float = 1.0,
) -> ComparisonResult:
    reference_keys = _reference_keys(reference, team_index)
    local_state = _LocalState(reference_keys)
    sorted_events = sorted(events, key=lambda event: _event_seconds(event, time_scale))
    differences: list[SampleDifference] = []
    event_index = 0
    checked_samples = 0

    for seconds in reference.sample_seconds:
        if max_seconds is not None and seconds > max_seconds:
            break

        while event_index < len(sorted_events) and _event_seconds(sorted_events[event_index], time_scale) <= seconds:
            local_state.apply(sorted_events[event_index], player.pid)
            event_index += 1

        checked_samples += 1
        reference_state = _reference_state_at(reference, seconds, team_index)
        for bucket in ("units", "buildings", "upgrades"):
            names = set(local_state.counts[bucket]) | set(reference_state[bucket])
            for name in sorted(names):
                local_count = local_state.counts[bucket].get(name, 0)
                reference_count = reference_state[bucket].get(name, 0)
                if local_count != reference_count:
                    differences.append(
                        SampleDifference(
                            seconds=seconds,
                            bucket=bucket,
                            name=name,
                            local=local_count,
                            reference=reference_count,
                        )
                    )

    return ComparisonResult(checked_samples=checked_samples, differences=differences)


def format_comparison(result: ComparisonResult, limit: int = 25) -> str:
    if result.matched:
        return f"SC2ReplayStats comparison matched {result.checked_samples} samples."

    lines = [
        f"SC2ReplayStats comparison checked {result.checked_samples} samples.",
        f"Differences: {len(result.differences)}",
        "",
    ]
    for difference in result.differences[:limit]:
        lines.append(
            f"{_time_label(difference.seconds)}  {difference.bucket:<9} "
            f"{difference.name}: local={difference.local}, reference={difference.reference}"
        )
    if len(result.differences) > limit:
        lines.append(f"... {len(result.differences) - limit} more")
    return "\n".join(lines)


def _loads_timeline(page_html: str, variable_name: str) -> dict[int, object]:
    pattern = rf"var\s+{re.escape(variable_name)}\s*=\s*jQuery\.parseJSON\('(?P<json>.*?)'\);"
    match = re.search(pattern, page_html, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find SC2ReplayStats `{variable_name}` timeline.")

    raw_json = html.unescape(match.group("json"))
    decoded = json.loads(raw_json)
    return {int(second): value for second, value in decoded.items()}


def _reference_keys(reference: ReplayStatsReference, team_index: int) -> dict[str, set[str]]:
    keys = {"units": set(), "buildings": set(), "upgrades": set()}
    for seconds in reference.sample_seconds:
        state = _reference_state_at(reference, seconds, team_index)
        for bucket, counts in state.items():
            keys[bucket].update(counts)
    return keys


def _reference_state_at(
    reference: ReplayStatsReference,
    seconds: int,
    team_index: int,
) -> dict[str, dict[str, int]]:
    units = _slot_counts(reference.units_alive.get(seconds), team_index)
    buildings_slot = _slot_counts(reference.buildings.get(seconds), team_index)
    buildings_alive = buildings_slot.get("Alive", {}) if isinstance(buildings_slot.get("Alive"), dict) else {}
    upgrades = _slot_counts(reference.upgrades.get(seconds), team_index)
    return {
        "units": _int_counts(units),
        "buildings": _int_counts(buildings_alive),
        "upgrades": _int_counts(upgrades),
    }


def _slot_counts(value: object, team_index: int) -> dict[str, object]:
    if not isinstance(value, list) or team_index >= len(value):
        return {}
    slot = value[team_index]
    return slot if isinstance(slot, dict) else {}


def _int_counts(counts: Mapping[str, object]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in counts.items():
        if isinstance(value, (int, float)):
            normalized[str(key)] = int(value)
    return normalized


class _LocalState:
    def __init__(self, reference_keys: dict[str, set[str]]):
        self.reference_keys = reference_keys
        self.counts: dict[str, dict[str, int]] = {"units": {}, "buildings": {}, "upgrades": {}}
        self.units_by_id: dict[int, tuple[str, str]] = {}
        self.pending_units_by_id: dict[int, tuple[str, str]] = {}

    def apply(self, event: object, player_id: int) -> None:
        event_type = type(event).__name__
        if event_type == "UnitInitEvent":
            self._remember_pending_unit(event, player_id)
        elif event_type == "UnitBornEvent" or event_type == "UnitDoneEvent":
            self._add_unit(event, player_id)
        elif event_type == "UnitTypeChangeEvent":
            self._change_unit(event, player_id)
        elif event_type == "UnitDiedEvent":
            self._remove_unit(event, player_id)
        elif event_type == "UpgradeCompleteEvent" and _event_player_id(event) == player_id:
            name = _normalize_name(getattr(event, "upgrade_type_name", ""))
            if not _is_ignored_upgrade(name):
                self._increment("upgrades", name)

    def _add_unit(self, event: object, player_id: int) -> None:
        if _event_player_id(event) != player_id:
            return
        name = _normalize_name(_event_name(event))
        if not name:
            return
        bucket = self._bucket_for(name)
        unit_id = _unit_id(event)
        if bucket is None and unit_id is not None:
            pending = self.pending_units_by_id.pop(unit_id, None)
            if pending is not None:
                bucket, name = pending
        if bucket is None:
            return
        if unit_id is not None and unit_id in self.units_by_id:
            old_bucket, old_name = self.units_by_id[unit_id]
            if self.counts[old_bucket].get(old_name, 0) == 0 and (
                name == old_name or self.counts[bucket].get(name, 0) > 0
            ):
                self.units_by_id[unit_id] = (bucket, name)
                return
        if unit_id is not None:
            self.units_by_id[unit_id] = (bucket, name)
        self._increment(bucket, name)

    def _remember_pending_unit(self, event: object, player_id: int) -> None:
        if _event_player_id(event) != player_id:
            return
        unit_id = _unit_id(event)
        if unit_id is None:
            return
        name = _normalize_name(_event_name(event))
        bucket = self._bucket_for(name)
        if bucket is not None:
            self.pending_units_by_id[unit_id] = (bucket, name)

    def _change_unit(self, event: object, player_id: int) -> None:
        if _event_player_id(event) != player_id:
            return
        unit_id = _unit_id(event)
        old_had_count = False
        if unit_id is not None and unit_id in self.units_by_id:
            old_bucket, old_name = self.units_by_id[unit_id]
            old_had_count = self.counts[old_bucket].get(old_name, 0) > 0
            self._decrement(old_bucket, old_name)

        name = _normalize_name(_event_name(event))
        bucket = self._bucket_for(name)
        if bucket is None:
            return
        if unit_id is not None:
            self.units_by_id[unit_id] = (bucket, name)
        if not old_had_count and self.counts[bucket].get(name, 0) > 0:
            return
        self._increment(bucket, name)

    def _remove_unit(self, event: object, player_id: int) -> None:
        unit_id = _unit_id(event)
        if unit_id is not None:
            self.pending_units_by_id.pop(unit_id, None)
        tracked = self.units_by_id.pop(unit_id, None) if unit_id is not None else None
        if tracked is None:
            return
        bucket, name = tracked
        self._decrement(bucket, name)

    def _bucket_for(self, name: str) -> str | None:
        if name in self.reference_keys["buildings"]:
            return "buildings"
        if name in self.reference_keys["units"]:
            return "units"
        return None

    def _increment(self, bucket: str, name: str) -> None:
        self.counts[bucket][name] = self.counts[bucket].get(name, 0) + 1

    def _decrement(self, bucket: str, name: str) -> None:
        current = self.counts[bucket].get(name, 0)
        if current <= 1:
            self.counts[bucket].pop(name, None)
        else:
            self.counts[bucket][name] = current - 1


def _event_player_id(event: object) -> int | None:
    event_player = getattr(event, "player", None)
    value = _int_or_none(getattr(event_player, "pid", None))
    if value is not None:
        return value

    for attr in ("control_pid", "upkeep_pid", "pid"):
        value = _int_or_none(getattr(event, attr, None))
        if value is not None:
            return value

    unit = getattr(event, "unit", None)
    owner = getattr(unit, "owner", None)
    return _int_or_none(getattr(owner, "pid", None))


def _event_name(event: object) -> str:
    for attr in ("unit_type_name", "upgrade_type_name"):
        value = getattr(event, attr, None)
        if value:
            return str(value)
    unit = getattr(event, "unit", None)
    if type(event).__name__ != "UnitDoneEvent":
        value = _unit_name_at_event_frame(unit, event)
        if value:
            return value
    for attr in ("name", "type_name", "unit_type_name"):
        value = getattr(unit, attr, None)
        if value:
            return str(value)
    value = getattr(event, "name", None)
    if value:
        return str(value)
    return ""


def _unit_id(event: object) -> int | None:
    value = _int_or_none(getattr(event, "unit_id", None))
    if value is not None:
        return value
    unit = getattr(event, "unit", None)
    return _int_or_none(getattr(unit, "id", None))


def _unit_name_at_event_frame(unit: object, event: object) -> str | None:
    type_history = getattr(unit, "type_history", None)
    if not type_history:
        return None

    frame = _int_or_none(getattr(event, "frame", None)) or 0
    current_name: str | None = None
    for type_frame, unit_type in type_history.items():
        if type_frame > frame:
            break
        name = getattr(unit_type, "name", None)
        if name:
            current_name = str(name)
    return current_name


def _event_seconds(event: object, time_scale: float) -> float:
    value = getattr(event, "second", None)
    if isinstance(value, (int, float)):
        return float(value) * time_scale
    frame = _int_or_none(getattr(event, "frame", None)) or 0
    return frame / 16 * time_scale


def _normalize_name(value: object) -> str:
    normalized = str(value).lower()
    for suffix in ("lowered", "flying"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return re.sub(r"[^a-z0-9]", "", normalized)


def _is_ignored_upgrade(name: str) -> bool:
    return name in IGNORED_UPGRADES or any(name.startswith(prefix) for prefix in IGNORED_UPGRADE_PREFIXES)


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _time_label(seconds: int) -> str:
    minutes, second = divmod(seconds, 60)
    return f"{minutes}:{second:02d}"
