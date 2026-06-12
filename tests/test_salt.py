from __future__ import annotations

from sc2_replay_salt.build_order import BuildOrderItem
from sc2_replay_salt.salt import format_salt_encoding


def _item(supply: int, seconds: int, name: str) -> BuildOrderItem:
    return BuildOrderItem(frame=seconds * 16, seconds=seconds, name=name, supply_used=supply)


def test_format_salt_encoding_matches_spawningtool_sample_records() -> None:
    items = [
        _item(14, 17, "Supply Depot"),
        _item(15, 39, "Barracks"),
        _item(16, 43, "Refinery"),
        _item(19, 87, "Marine"),
        _item(19, 88, "Orbital Command"),
        _item(20, 102, "Command Center"),
        _item(20, 106, "Barracks Reactor"),
        _item(21, 117, "Supply Depot"),
        _item(22, 141, "Barracks"),
        _item(22, 141, "Barracks"),
        _item(23, 144, "Marine"),
        _item(23, 144, "Marine"),
        _item(26, 162, "Marine"),
        _item(26, 162, "Marine"),
        _item(29, 175, "Orbital Command"),
        _item(30, 180, "Marine"),
        _item(30, 180, "Marine"),
        _item(32, 191, "Barracks Tech Lab"),
        _item(32, 191, "Barracks Tech Lab"),
        _item(33, 201, "Supply Depot"),
        _item(33, 206, "Marine"),
        _item(37, 211, "Concussive Shells"),
        _item(37, 211, "Stimpack"),
        _item(37, 212, "Marine"),
        _item(37, 212, "Marine"),
        _item(41, 226, "Refinery"),
        _item(43, 231, "Marauder"),
        _item(43, 231, "Marauder"),
        _item(49, 242, "Engineering Bay"),
        _item(53, 253, "Combat Shield"),
        _item(63, 283, "Factory"),
        _item(65, 289, "Missile Turret"),
        _item(65, 293, "Terran Infantry Weapons Level 1"),
        _item(65, 298, "Command Center"),
        _item(78, 325, "Refinery"),
        _item(78, 325, "Refinery"),
        _item(78, 328, "Starport"),
        _item(78, 328, "Factory Reactor"),
        _item(78, 341, "Marauder"),
        _item(78, 341, "Marauder"),
        _item(86, 347, "Barracks"),
        _item(86, 347, "Barracks"),
        _item(85, 364, "Marauder"),
        _item(85, 364, "Marauder"),
        _item(91, 376, "Medivac"),
        _item(91, 376, "Medivac"),
    ]

    assert (
        format_salt_encoding(items, "158142|spawningtool.com||")
        == '$158142|spawningtool.com||~* 0 /+ F !, J ,/!:!%/!;" 0!I #0!M )1!X /2"4 !2"4 '
        '!3"7!%3"7!%6"I!%6"I!%9"V" :"[!%:"[!%<#* 0<#* 0=#4 /=#9!%A#>#/'
        'A#>#+A#?!%A#?!%E#M ,G#R!$G#R!$M$! $Q$,#0[$J %]$P (]$T#"]$Y #'
        'j%8 ,j%8 ,j%; .j%; *j%H!$j%H!$r%N !r%N !q&#!$q&#!$w&/!&w&/!&'
    )


def test_format_salt_encoding_applies_salt_limits() -> None:
    items = [
        _item(13, 1, "SCV"),
        _item(14, 17, "Supply Depot"),
        _item(21, 117, "Supply Depot"),
        _item(33, 201, "Supply Depot"),
        _item(41, 226, "Supply Depot"),
        *[_item(20 + index, 30 + index, "Marine") for index in range(11)],
        _item(99, 400, "Barracks"),
        _item(30, 60, "Not A SALT Thing"),
        _item(31, 61, "???"),
    ]

    encoding = format_salt_encoding(items, "Limits")
    payload = encoding.split("~", 1)[1]

    assert encoding.startswith("$Limits~")
    assert len(payload) == 13 * 5
    assert payload.count(" /") == 3


def test_format_salt_encoding_includes_interference_matrix() -> None:
    encoding = format_salt_encoding([_item(63, 257, "Interference Matrix")], "Raven")

    assert encoding == "$Raven~[$0#,"


def test_format_salt_encoding_includes_raven_enhanced_munitions() -> None:
    encoding = format_salt_encoding([_item(63, 257, "Raven Enhanced Munitions")], "Raven")

    assert encoding == "$Raven~[$0#,"
