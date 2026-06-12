from __future__ import annotations


def event_frame(event: object) -> int:
    value = int_or_none(getattr(event, "frame", None))
    if value is not None:
        return value
    value = int_or_none(getattr(event, "frames", None))
    return value if value is not None else 0


def event_seconds(event: object, frame: int | None = None, time_scale: float = 1.0) -> float:
    value = getattr(event, "second", None)
    if isinstance(value, (int, float)):
        return float(value) * time_scale
    return (event_frame(event) if frame is None else frame) / 16 * time_scale


def event_player_id(event: object) -> int | None:
    event_player = getattr(event, "player", None)
    value = int_or_none(getattr(event_player, "pid", None))
    if value is not None:
        return value

    for attr in ("control_pid", "upkeep_pid", "pid"):
        value = int_or_none(getattr(event, attr, None))
        if value is not None:
            return value

    for owner_attr in ("unit_controller", "unit_upkeeper", "unit"):
        owner = getattr(event, owner_attr, None)
        value = int_or_none(getattr(owner, "pid", None))
        if value is not None:
            return value
        nested_owner = getattr(owner, "owner", None)
        value = int_or_none(getattr(nested_owner, "pid", None))
        if value is not None:
            return value

    return None


def unit_id(event: object) -> int | None:
    value = int_or_none(getattr(event, "unit_id", None))
    if value is not None:
        return value
    unit = getattr(event, "unit", None)
    return int_or_none(getattr(unit, "id", None))


def unit_name_at_frame(unit: object, frame: int) -> str | None:
    type_history = getattr(unit, "type_history", None)
    if not type_history:
        return None

    current_name: str | None = None
    for type_frame, unit_type in type_history.items():
        if type_frame > frame:
            break
        current_name = str_or_none(getattr(unit_type, "name", None))
    return current_name


def int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
