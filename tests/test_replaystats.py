from __future__ import annotations

from dataclasses import dataclass

from sc2_replay_salt.build_order import PlayerRef
from sc2_replay_salt.replaystats import compare_reference, format_comparison, parse_reference


@dataclass
class FakePlayer:
    pid: int


class UnitBornEvent:
    def __init__(self, second: int, unit_id: int, control_pid: int, unit_type_name: str):
        self.second = second
        self.frame = second * 16
        self.unit_id = unit_id
        self.control_pid = control_pid
        self.unit_type_name = unit_type_name


class UnitInitEvent(UnitBornEvent):
    pass


class UnitDoneEvent(UnitBornEvent):
    def __init__(self, second: int, unit_id: int, control_pid: int, unit_type_name: str):
        super().__init__(second, unit_id, control_pid, "")
        self.name = "UnitDoneEvent"
        self.unit = FakeUnit(unit_type_name)


@dataclass
class FakeUnit:
    name: str


class FakeUnitType:
    def __init__(self, name: str):
        self.name = name


class UnitDiedEvent:
    def __init__(self, second: int, unit_id: int):
        self.second = second
        self.frame = second * 16
        self.unit_id = unit_id


class UpgradeCompleteEvent:
    def __init__(self, second: int, pid: int, upgrade_type_name: str):
        self.second = second
        self.frame = second * 16
        self.pid = pid
        self.upgrade_type_name = upgrade_type_name


def test_parse_reference_extracts_embedded_timelines() -> None:
    page = """
    <script>
    var units_alive = jQuery.parseJSON('{"0":[{"scv":12},{"probe":12}]}');
    var buildings = jQuery.parseJSON('{"0":[{"Alive":{"commandcenter":1},"Killed":[]},{"Alive":{"nexus":1},"Killed":[]}]}');
    var upgrades = jQuery.parseJSON('{"0":[[],[]]}');
    </script>
    """

    reference = parse_reference(page)

    assert reference.units_alive[0][0]["scv"] == 12
    assert reference.buildings[0][1]["Alive"]["nexus"] == 1


def test_compare_reference_matches_local_tracker_state() -> None:
    page = """
    <script>
    var units_alive = jQuery.parseJSON('{"0":[{},{}],"7":[{"marine":1},{}],"14":[{},{}]}');
    var buildings = jQuery.parseJSON('{"0":[{"Alive":{},"Killed":[]},{}],"7":[{"Alive":{},"Killed":[]},{}],"14":[{"Alive":{},"Killed":[]}]}');
    var upgrades = jQuery.parseJSON('{"0":[[],[]],"7":[[],[]],"14":[{"stimpack":1},[]]}');
    </script>
    """

    result = compare_reference(
        [
            UnitBornEvent(7, 1, 1, "Marine"),
            UnitDiedEvent(14, 1),
            UpgradeCompleteEvent(14, 1, "Stimpack"),
        ],
        PlayerRef(pid=1, name="Alpha"),
        parse_reference(page),
        team_index=0,
    )

    assert result.matched
    assert "matched 3 samples" in format_comparison(result)


def test_compare_reference_ignores_cosmetic_upgrades() -> None:
    page = """
    <script>
    var units_alive = jQuery.parseJSON('{"0":[{},{}]}');
    var buildings = jQuery.parseJSON('{"0":[{"Alive":{},"Killed":[]},{}]}');
    var upgrades = jQuery.parseJSON('{"0":[[],[]]}');
    </script>
    """

    result = compare_reference(
        [UpgradeCompleteEvent(0, 1, "RewardDanceGhost"), UpgradeCompleteEvent(0, 1, "SprayTerran")],
        PlayerRef(pid=1, name="Alpha"),
        parse_reference(page),
        team_index=0,
    )

    assert result.matched


def test_compare_reference_uses_unit_done_for_building_state() -> None:
    page = """
    <script>
    var units_alive = jQuery.parseJSON('{"0":[{},{}],"7":[{},{}],"14":[{},{}]}');
    var buildings = jQuery.parseJSON('{"0":[{"Alive":{},"Killed":[]},{}],"7":[{"Alive":{},"Killed":[]},{}],"14":[{"Alive":{"supplydepot":1},"Killed":[]}]}');
    var upgrades = jQuery.parseJSON('{"0":[[],[]],"7":[[],[]],"14":[[],[]]}');
    </script>
    """

    result = compare_reference(
        [
            UnitInitEvent(7, 1, 1, "SupplyDepot"),
            UnitDoneEvent(14, 1, 1, "SupplyDepotLowered"),
        ],
        PlayerRef(pid=1, name="Alpha"),
        parse_reference(page),
        team_index=0,
    )

    assert result.matched


def test_compare_reference_carries_addon_init_name_to_done_event() -> None:
    page = """
    <script>
    var units_alive = jQuery.parseJSON('{"0":[{},{}],"7":[{},{}],"14":[{},{}]}');
    var buildings = jQuery.parseJSON('{"0":[{"Alive":{},"Killed":[]},{}],"7":[{"Alive":{},"Killed":[]},{}],"14":[{"Alive":{"barracksreactor":1},"Killed":[]}]}');
    var upgrades = jQuery.parseJSON('{"0":[[],[]],"7":[[],[]],"14":[[],[]]}');
    </script>
    """

    result = compare_reference(
        [
            UnitInitEvent(7, 1, 1, "BarracksReactor"),
            UnitDoneEvent(14, 1, 1, "Reactor"),
        ],
        PlayerRef(pid=1, name="Alpha"),
        parse_reference(page),
        team_index=0,
    )

    assert result.matched


def test_compare_reference_ignores_death_for_uncounted_pending_unit() -> None:
    page = """
    <script>
    var units_alive = jQuery.parseJSON('{"0":[{},{}],"7":[{},{}]}');
    var buildings = jQuery.parseJSON('{"0":[{"Alive":{},"Killed":[]},{}],"7":[{"Alive":{},"Killed":[]}]}');
    var upgrades = jQuery.parseJSON('{"0":[[],[]],"7":[[],[]]}');
    </script>
    """

    result = compare_reference(
        [
            UnitInitEvent(1, 1, 1, "BarracksReactor"),
            UnitDiedEvent(7, 1),
        ],
        PlayerRef(pid=1, name="Alpha"),
        parse_reference(page),
        team_index=0,
    )

    assert result.matched


def test_compare_reference_uses_done_event_unit_name() -> None:
    page = """
    <script>
    var units_alive = jQuery.parseJSON('{"0":[{},{}],"14":[{},{}]}');
    var buildings = jQuery.parseJSON('{"0":[{"Alive":{},"Killed":[]},{}],"14":[{"Alive":{"orbitalcommand":1},"Killed":[]}]}');
    var upgrades = jQuery.parseJSON('{"0":[[],[]],"14":[[],[]]}');
    </script>
    """
    done = UnitDoneEvent(14, 1, 1, "OrbitalCommand")
    done.unit.type_history = {0: FakeUnitType("CommandCenter"), 400: FakeUnitType("OrbitalCommand")}

    result = compare_reference(
        [done],
        PlayerRef(pid=1, name="Alpha"),
        parse_reference(page),
        team_index=0,
    )

    assert result.matched


def test_compare_reference_applies_time_scale() -> None:
    page = """
    <script>
    var units_alive = jQuery.parseJSON('{"0":[{},{}],"7":[{"marine":1},{}]}');
    var buildings = jQuery.parseJSON('{"0":[{"Alive":{},"Killed":[]},{}],"7":[{"Alive":{},"Killed":[]}]}');
    var upgrades = jQuery.parseJSON('{"0":[[],[]],"7":[[],[]]}');
    </script>
    """

    result = compare_reference(
        [UnitBornEvent(10, 1, 1, "Marine")],
        PlayerRef(pid=1, name="Alpha"),
        parse_reference(page),
        team_index=0,
        time_scale=0.7,
    )

    assert result.matched


def test_compare_reference_reports_differences() -> None:
    page = """
    <script>
    var units_alive = jQuery.parseJSON('{"0":[{"marine":1},{}]}');
    var buildings = jQuery.parseJSON('{"0":[{"Alive":{},"Killed":[]},{}]}');
    var upgrades = jQuery.parseJSON('{"0":[[],[]]}');
    </script>
    """

    result = compare_reference([], PlayerRef(pid=1, name="Alpha"), parse_reference(page), team_index=0)

    assert not result.matched
    assert "marine: local=0, reference=1" in format_comparison(result)
