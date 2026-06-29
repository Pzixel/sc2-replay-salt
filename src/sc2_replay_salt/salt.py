from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from .build_order import BuildOrderItem


SALT_VERSION = "$"
SALT_MIN_SUPPLY = 4
SALT_MAX_SUPPLY = 98
SALT_WORKERS = {"Drone", "Probe", "SCV"}
SALT_SUPPLY_PROVIDERS = {"Overlord", "Pylon", "Supply Depot"}
SALT_SUPPLY_PROVIDER_LIMIT = 3
SALT_ITEM_LIMIT = 10

SALT_STRUCTURES = {
    "Armory": 0,
    "Barracks": 1,
    "Bunker": 2,
    "Command Center": 3,
    "Engineering Bay": 4,
    "Factory": 5,
    "Fusion Core": 6,
    "Ghost Academy": 7,
    "Missile Turret": 8,
    "Barracks Reactor": 9,
    "Factory Reactor": 10,
    "Starport Reactor": 11,
    "Refinery": 12,
    "Sensor Tower": 13,
    "Starport": 14,
    "Supply Depot": 15,
    "Barracks Tech Lab": 16,
    "Factory Tech Lab": 17,
    "Starport Tech Lab": 18,
    "Assimilator": 19,
    "Cybernetics Core": 20,
    "Dark Shrine": 21,
    "Fleet Beacon": 22,
    "Forge": 23,
    "Gateway": 24,
    "Nexus": 25,
    "Photon Cannon": 26,
    "Pylon": 27,
    "Robotics Bay": 28,
    "Robotics Facility": 29,
    "Stargate": 30,
    "Templar Archives": 31,
    "Twilight Council": 32,
    "Baneling Nest": 33,
    "Evolution Chamber": 34,
    "Extractor": 35,
    "Hatchery": 36,
    "Hydralisk Den": 37,
    "Infestation Pit": 38,
    "Nydus Canal": 39, # maybe it's not a network but a summoned canal so it should be skipped?
    "Nydus Network": 39,
    "Roach Warren": 40,
    "Spawning Pool": 41,
    "Spine Crawler": 42,
    "Spire": 43,
    "Spore Crawler": 44,
    "Ultralisk Cavern": 45,
    "Creep Tumor": 46,
    "Shield Battery": 47,
    "Lurker Den": 48,
}

SALT_UNITS = {
    "Banshee": 0,
    "Battlecruiser": 1,
    "Ghost": 2,
    "Hellion": 3,
    "Marauder": 4,
    "Marine": 5,
    "Medivac": 6,
    "Raven": 7,
    "Reaper": 8,
    "SCV": 9,
    "Siege Tank": 10,
    "Thor": 11,
    "Viking": 12,
    "Viking Fighter": 12,
    "Archon": 13,
    "Carrier": 14,
    "Colossus": 15,
    "Dark Templar": 16,
    "High Templar": 17,
    "Immortal": 18,
    "Mothership": 19,
    "Observer": 20,
    "Phoenix": 21,
    "Probe": 22,
    "Sentry": 23,
    "Stalker": 24,
    "Void Ray": 25,
    "Zealot": 26,
    "Corruptor": 27,
    "Drone": 28,
    "Hydralisk": 29,
    "Mutalisk": 30,
    "Overlord": 31,
    "Queen": 32,
    "Roach": 33,
    "Ultralisk": 34,
    "Zergling": 35,
    "Infestor": 38,
    "Warp Prism": 39,
    "Battle Hellion": 40,
    "Hellbat": 40,
    "Widow Mine": 42,
    "Cyclone": 43,
    "Oracle": 44,
    "Tempest": 45,
    "Swarm Host": 46,
    "Swarm Host MP": 46,
    "Viper": 47,
    "Adept": 48,
    "Liberator": 49,
}

SALT_MORPHS = {
    "Orbital Command": 0,
    "Planetary Fortress": 1,
    "Warp Gate": 2,
    "Lair": 3,
    "Hive": 4,
    "Greater Spire": 5,
    "Brood Lord": 6,
    "Baneling": 7,
    "Overseer": 8,
    "Ravager": 9,
}

SALT_UPGRADES = {
    "Terran Building Armor": 0,
    "Terran Infantry Armor Level 1": 1,
    "Terran Infantry Armors Level 1": 1,
    "Terran Infantry Weapons Level 1": 2,
    "Terran Ship Plating Level 1": 3,
    "Terran Ship Armors Level 1": 3,
    "Terran Ship Weapons Level 1": 4,
    "Terran Vehicle Plating Level 1": 5,
    "Terran Vehicle Armors Level 1": 5,
    "Terran Vehicle Weapons Level 1": 6,
    "250mm Strike Cannons": 7,
    "Banshee Cloak": 8,
    "Cloaking Field": 8,
    "Personal Cloaking": 9,
    "High Capacity Barrels": 10,
    "Infernal Pre Igniter": 10,
    "Infernal Pre-Igniter": 10,
    "Stimpack": 11,
    "Raven Enhanced Munitions": 12,
    "Interference Matrix": 12,
    "Seeker Missile": 12,
    "Siege Tech": 13,
    "Neosteel Frame": 14,
    "Concussive Shells": 15,
    "Combat Shield": 16,
    "Combat Shields": 16,
    "Reaper Speed": 17,
    "Protoss Ground Armor Level 1": 18,
    "Protoss Ground Armors Level 1": 18,
    "Protoss Ground Weapons Level 1": 19,
    "Protoss Air Armor Level 1": 20,
    "Protoss Air Armors Level 1": 20,
    "Protoss Air Weapons Level 1": 21,
    "Protoss Shields Level 1": 22,
    "Hallucination": 23,
    "Psi Storm": 24,
    "Blink": 25,
    "Blink Tech": 25,
    "Warp Gate": 26,
    "Warp Gate Research": 26,
    "Charge": 27,
    "Zerg Ground Armor Level 1": 28,
    "Zerg Ground Armors Level 1": 28,
    "Zerg Melee Weapons Level 1": 29,
    "Zerg Flyer Armor Level 1": 30,
    "Zerg Flyer Armors Level 1": 30,
    "Zerg Flyer Weapons Level 1": 31,
    "Zerg Missile Weapons Level 1": 32,
    "Grooved Spines": 33,
    "Hydralisk Speed": 33,
    "Pneumatized Carapace": 34,
    "Ventral Sacs": 35,
    "Glial Reconstitution": 36,
    "Tunneling Claws": 38,
    "Chitinous Plating": 40,
    "Adrenal Glands": 41,
    "Metabolic Boost": 42,
    "Burrow": 44,
    "Centrifugal Hooks": 45,
    "Moebius Reactor": 46,
    "Extended Thermal Lance": 47,
    "Khaydarin Amulet": 48,
    "Neural Parasite": 49,
    "Pathogen Glands": 50,
    "Hi-Sec Auto Tracking": 51,
    "Mag-Field Accelerator": 52,
    "Adaptive Talons": 53,
    "Muscular Augments": 54,
    "Hyperflight Rotors": 55,
    "Weapon Refit": 56,
    "Terran Vehicle And Ship Armor Level 1": 57,
    "Terran Vehicle And Ship Armors Level 1": 57,
    "Drilling Claws": 58,
}

SALT_TABLES = (
    SALT_STRUCTURES,
    SALT_UNITS,
    SALT_MORPHS,
    SALT_UPGRADES,
)


class SaltEncodingError(ValueError):
    pass


def format_salt_encoding(items: Sequence[BuildOrderItem], title: str, source: str | None = None) -> str:
    records = [_format_record(item) for item in _salt_items(items, title, source)]
    return f"{SALT_VERSION}{_sanitize_title(title)}~{''.join(records)}"


def _salt_items(items: Sequence[BuildOrderItem], title: str, source: str | None = None) -> list[BuildOrderItem]:
    counts: defaultdict[str, int] = defaultdict(int)
    supply_provider_count = 0
    result: list[BuildOrderItem] = []
    for item in items:
        if item.name in SALT_WORKERS:
            continue
        if item.supply_used is None or item.supply_used < SALT_MIN_SUPPLY or item.supply_used > SALT_MAX_SUPPLY:
            continue
        if _salt_lookup(item.name) is None:
            raise SaltEncodingError(_unencodable_item_message(item, title, source))

        if item.name in SALT_SUPPLY_PROVIDERS:
            supply_provider_count += 1
            if supply_provider_count > SALT_SUPPLY_PROVIDER_LIMIT:
                continue
        else:
            counts[item.name] += 1
            if counts[item.name] > SALT_ITEM_LIMIT:
                continue
        result.append(item)
    return result


def _unencodable_item_message(item: BuildOrderItem, title: str, source: str | None) -> str:
    context = source or title
    return (
        f"Cannot encode build-order item as SALT: {item.name!r}; "
        f"title={title!r}; source={context!r}; supply={item.supply_used}; "
        f"time={item.time_label}; frame={item.frame}; reason=no SALT table entry"
    )


def _format_record(item: BuildOrderItem) -> str:
    lookup = _salt_lookup(item.name)
    if lookup is None or item.supply_used is None:
        raise ValueError(f"Cannot encode '{item.name}' as SALT.")
    item_type, item_id = lookup
    total_seconds = max(0, int(item.seconds) - 1)
    minutes, seconds = divmod(total_seconds, 60)
    return "".join(
        (
            _encode_byte(item.supply_used - SALT_MIN_SUPPLY),
            _encode_byte(minutes),
            _encode_byte(seconds),
            _encode_byte(item_type),
            _encode_byte(item_id),
        )
    )


def _salt_lookup(name: str) -> tuple[int, int] | None:
    normalized = _normalize_name(name)
    lookup = SALT_LOOKUP.get(normalized)
    if lookup is not None:
        return lookup

    for level in ("2", "3"):
        level_suffix = f"level{level}"
        if normalized.endswith(level_suffix):
            return SALT_LOOKUP.get(f"{normalized[:-len(level_suffix)]}level1")
    return None


def _encode_byte(value: int) -> str:
    if value < 0 or value > 94:
        raise ValueError(f"SALT byte out of range: {value}")
    return chr(value + 32)


def _normalize_name(name: str) -> str:
    return "".join(character.casefold() for character in name if character.isalnum())


SALT_LOOKUP = {
    _normalize_name(table_name): (item_type, item_id)
    for item_type, table in enumerate(SALT_TABLES)
    for table_name, item_id in table.items()
}


def _sanitize_title(title: str) -> str:
    return " ".join(title.replace("~", "-").split())
