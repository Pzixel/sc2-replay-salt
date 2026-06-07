from __future__ import annotations

from dataclasses import dataclass

from sc2_replay_salt.build_order import (
    BuildOrderItem,
    BuildOrderOptions,
    PlayerRef,
    extract_build_order,
    format_build_order,
    replay_paths,
    resolve_player,
)


@dataclass
class FakePlayer:
    pid: int
    name: str
    play_race: str


class UnitInitEvent:
    def __init__(self, frame: int, control_pid: int, unit_type_name: str):
        self.frame = frame
        self.control_pid = control_pid
        self.unit_type_name = unit_type_name


class UnitDoneEvent(UnitInitEvent):
    pass


class UnitBornEvent(UnitInitEvent):
    pass


class UpgradeCompleteEvent:
    def __init__(self, frame: int, pid: int, upgrade_type_name: str):
        self.frame = frame
        self.pid = pid
        self.upgrade_type_name = upgrade_type_name


class BasicCommandEvent:
    def __init__(self, frame: int, player: FakePlayer, ability_name: str):
        self.frame = frame
        self.player = player
        self.ability_name = ability_name


def test_resolve_player_defaults_to_first_player() -> None:
    player = resolve_player([FakePlayer(1, "Alpha", "Terran"), FakePlayer(2, "Beta", "Zerg")], None)

    assert player == PlayerRef(pid=1, name="Alpha", race="Terran")


def test_resolve_player_accepts_id_or_name() -> None:
    players = [FakePlayer(1, "Alpha", "Terran"), FakePlayer(2, "Beta", "Zerg")]

    assert resolve_player(players, "2").name == "Beta"
    assert resolve_player(players, "beta").pid == 2


def test_extract_build_order_filters_player_and_tracker_events() -> None:
    items = extract_build_order(
        [
            UnitInitEvent(160, 1, "Barracks"),
            UnitDoneEvent(400, 1, "Barracks"),
            UnitBornEvent(480, 1, "SCV"),
            UnitBornEvent(480, 2, "Zergling"),
            UnitBornEvent(0, 1, "SCV"),
            UnitBornEvent(640, 1, "MULE"),
            UpgradeCompleteEvent(960, 1, "Stimpack"),
            object(),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        "  ?   0:10  Barracks",
    ]


def test_extract_build_order_can_include_starting_state() -> None:
    items = extract_build_order(
        [UnitBornEvent(0, 1, "CommandCenter")],
        PlayerRef(pid=1, name="Alpha"),
        BuildOrderOptions(include_starting_state=True),
    )

    assert [item.format() for item in items] == ["  ?   0:00  Command Center"]


def test_extract_build_order_filters_type_changes_by_default() -> None:
    class UnitTypeChangeEvent(UnitInitEvent):
        pass

    items = extract_build_order(
        [
            UnitTypeChangeEvent(160, 1, "SiegeTankSieged"),
            UnitTypeChangeEvent(320, 1, "OrbitalCommand"),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert items == []


def test_extract_build_order_can_include_type_changes() -> None:
    class UnitTypeChangeEvent(UnitInitEvent):
        pass

    items = extract_build_order(
        [UnitTypeChangeEvent(320, 1, "OrbitalCommand")],
        PlayerRef(pid=1, name="Alpha"),
        BuildOrderOptions(include_type_changes=True),
    )

    assert [item.format() for item in items] == ["  ?   0:20  Orbital Command"]


def test_extract_build_order_can_include_workers() -> None:
    items = extract_build_order(
        [UnitBornEvent(160, 1, "SCV")],
        PlayerRef(pid=1, name="Alpha"),
        BuildOrderOptions(include_workers=True),
    )

    assert [item.format() for item in items] == ["  ?   0:10  SCV"]


def test_extract_build_order_uses_command_events_for_research_and_morphs() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            BasicCommandEvent(160, player, "ResearchStimpack"),
            BasicCommandEvent(320, player, "UpgradeToOrbitalCommand"),
            BasicCommandEvent(480, player, "BuildSupplyDepot"),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        "  ?   0:10  Stimpack",
        "  ?   0:20  Orbital Command",
    ]


def test_format_build_order_is_readable() -> None:
    text = format_build_order(
        "game.SC2Replay",
        PlayerRef(pid=1, name="Alpha", race="Terran"),
        extract_build_order([UnitInitEvent(160, 1, "SupplyDepot")], PlayerRef(pid=1, name="Alpha")),
    )

    assert "game.SC2Replay" in text
    assert "Player: 1: Alpha, Terran" in text
    assert "?\t0:10\tSupply Depot" in text


def test_format_build_order_groups_duplicate_items() -> None:
    text = format_build_order(
        "game.SC2Replay",
        PlayerRef(pid=1, name="Alpha"),
        [
            BuildOrderItem(frame=160, seconds=10, name="Marine", supply_used=19),
            BuildOrderItem(frame=160, seconds=10, name="Marine", supply_used=19),
            BuildOrderItem(frame=160, seconds=10, name="Stimpack", supply_used=19),
        ],
    )

    assert " 19\t0:10\tMarine x2, Stimpack" in text


def test_replay_paths_returns_sorted_sc2_replays(tmp_path) -> None:
    second = tmp_path / "b.SC2Replay"
    first = tmp_path / "a.SC2Replay"
    ignored = tmp_path / "notes.txt"
    second.write_bytes(b"")
    first.write_bytes(b"")
    ignored.write_text("not a replay")

    assert replay_paths(tmp_path) == [first, second]
