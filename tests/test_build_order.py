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
    def __init__(
        self,
        frame: int,
        player: FakePlayer,
        ability_name: str,
        repeat: bool = False,
        ability_id: int | None = None,
        ability_link: int | None = None,
        command_index: int | None = None,
    ):
        self.frame = frame
        self.player = player
        self.ability_name = ability_name
        self.flag = {"repeat": repeat}
        self.ability_id = ability_id
        self.ability_link = ability_link
        self.command_index = command_index


class CommandManagerStateEvent:
    def __init__(self, frame: int, player: FakePlayer):
        self.frame = frame
        self.player = player


class PlayerStatsEvent:
    def __init__(self, frame: int, pid: int, food_used: float):
        self.frame = frame
        self.pid = pid
        self.food_used = food_used


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
            BasicCommandEvent(640, player, "UpgradeTerranInfantryWeapons1"),
            BasicCommandEvent(800, player, "UpgradeGroundWeapons2"),
            BasicCommandEvent(960, player, "UpgradesShields3"),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        "  ?   0:10  Stimpack",
        "  ?   0:20  Orbital Command",
        "  ?   0:40  Terran Infantry Weapons Level 1",
        "  ?   0:50  Protoss Ground Weapons Level 2",
        "  ?   1:00  Protoss Shields Level 3",
    ]


def test_extract_build_order_uses_unit_commands_and_reserved_supply() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            PlayerStatsEvent(0, 1, 34),
            BasicCommandEvent(160, player, "BuildHellion"),
            BasicCommandEvent(320, player, "TrainBanshee"),
            BasicCommandEvent(400, player, "TrainMothership"),
            BasicCommandEvent(440, player, "TrainNuke"),
            UnitBornEvent(480, 1, "Hellion"),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        " 34   0:10  Hellion",
        " 36   0:20  Banshee",
        " 39   0:25  Mothership",
        " 47   0:27  Nuke",
    ]


def test_extract_build_order_uses_repeated_unit_commands() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            PlayerStatsEvent(0, 1, 27),
            BasicCommandEvent(160, player, "TrainReaper", repeat=True),
            UnitBornEvent(480, 1, "Reaper"),
            UnitBornEvent(480, 1, "Reaper"),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        " 27   0:10  Reaper",
        " 27   0:10  Reaper",
    ]


def test_extract_build_order_uses_distinct_mixed_reactor_commands() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            PlayerStatsEvent(0, 1, 27),
            BasicCommandEvent(160, player, "TrainReaper"),
            BasicCommandEvent(160, player, "TrainMarine"),
            UnitBornEvent(480, 1, "Marine"),
            UnitBornEvent(480, 1, "Reaper"),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        " 27   0:10  Reaper",
        " 27   0:10  Marine",
    ]


def test_extract_build_order_marks_unresolved_unit_commands() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            PlayerStatsEvent(0, 1, 27),
            BasicCommandEvent(160, player, "TrainDefinitelyUnknown"),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        " 27   0:10  ???",
    ]


def test_extract_build_order_does_not_invent_unrelated_same_frame_units() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            PlayerStatsEvent(0, 1, 27),
            BasicCommandEvent(160, player, "TrainReaper", repeat=True),
            UnitBornEvent(480, 1, "Reaper"),
            UnitBornEvent(480, 1, "Reaper"),
            UnitBornEvent(480, 1, "Hellion"),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        " 27   0:10  Reaper",
        " 27   0:10  Reaper",
    ]


def test_extract_build_order_uses_command_manager_repeats_for_unit_commands() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            PlayerStatsEvent(0, 1, 33),
            BasicCommandEvent(160, player, "TrainMarine"),
            CommandManagerStateEvent(176, player),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        " 33   0:10  Marine",
        " 34   0:11  Marine",
    ]


def test_extract_build_order_names_unresolved_research_commands_from_ability_tables() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            PlayerStatsEvent(0, 1, 37),
            BasicCommandEvent(160, player, "", ability_link=167, command_index=0),
            BasicCommandEvent(320, player, "", ability_link=167, command_index=1),
            BasicCommandEvent(480, player, "", ability_link=168, command_index=6),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        " 37   0:10  Stimpack",
        " 37   0:20  Combat Shield",
        " 37   0:30  Smart Servos",
    ]


def test_extract_build_order_names_unresolved_raven_upgrade_from_ability_tables() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            PlayerStatsEvent(0, 1, 63),
            BasicCommandEvent(160, player, "", ability_id=5425, ability_link=169, command_index=17),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        " 63   0:10  Raven Enhanced Munitions",
    ]


def test_extract_build_order_uses_direct_ability_table_for_newer_upgrade_links() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            PlayerStatsEvent(0, 1, 63),
            BasicCommandEvent(160, player, "", ability_id=22849, ability_link=714, command_index=1),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        " 63   0:10  Terran Vehicle Weapons Level 2",
    ]


def test_extract_build_order_keeps_supply_monotonic_after_unit_completion() -> None:
    player = FakePlayer(1, "Alpha", "Terran")

    items = extract_build_order(
        [
            PlayerStatsEvent(0, 1, 34),
            BasicCommandEvent(160, player, "BuildHellion"),
            PlayerStatsEvent(320, 1, 33),
            UnitBornEvent(320, 1, "Hellion"),
            UnitInitEvent(336, 1, "FactoryTechLab"),
        ],
        PlayerRef(pid=1, name="Alpha"),
    )

    assert [item.format() for item in items] == [
        " 34   0:10  Hellion",
        " 34   0:21  Factory Tech Lab",
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


def test_format_build_order_groups_same_second_duplicates_with_different_supply() -> None:
    text = format_build_order(
        "game.SC2Replay",
        PlayerRef(pid=1, name="Alpha"),
        [
            BuildOrderItem(frame=160, seconds=10, name="Medivac", supply_used=193),
            BuildOrderItem(frame=164, seconds=10, name="Medivac", supply_used=195),
            BuildOrderItem(frame=200, seconds=12, name="Widow Mine", supply_used=201),
            BuildOrderItem(frame=204, seconds=12, name="Widow Mine", supply_used=203),
        ],
    )

    assert "193\t0:10\tMedivac x2" in text
    assert "201\t0:12\tWidow Mine x2" in text


def test_replay_paths_returns_sorted_sc2_replays(tmp_path) -> None:
    second = tmp_path / "b.SC2Replay"
    first = tmp_path / "a.SC2Replay"
    ignored = tmp_path / "notes.txt"
    second.write_bytes(b"")
    first.write_bytes(b"")
    ignored.write_text("not a replay")

    assert replay_paths(tmp_path) == [first, second]
