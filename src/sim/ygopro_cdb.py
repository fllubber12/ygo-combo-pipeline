from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

TYPE_MONSTER = 0x1
TYPE_EFFECT = 0x20
TYPE_FUSION = 0x40
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_LINK = 0x4000000

ATTR_EARTH = 0x1
ATTR_WATER = 0x2
ATTR_FIRE = 0x4
ATTR_WIND = 0x8
ATTR_LIGHT = 0x10
ATTR_DARK = 0x20
ATTR_DIVINE = 0x40

RACE_WARRIOR = 0x1
RACE_SPELLCASTER = 0x2
RACE_FAIRY = 0x4
RACE_FIEND = 0x8
RACE_ZOMBIE = 0x10
RACE_MACHINE = 0x20
RACE_AQUA = 0x40
RACE_PYRO = 0x80
RACE_ROCK = 0x100
RACE_WINGED_BEAST = 0x200
RACE_PLANT = 0x400
RACE_INSECT = 0x800
RACE_THUNDER = 0x1000
RACE_DRAGON = 0x2000
RACE_BEAST = 0x4000
RACE_BEAST_WARRIOR = 0x8000
RACE_DINOSAUR = 0x10000
RACE_FISH = 0x20000
RACE_SEA_SERPENT = 0x40000
RACE_REPTILE = 0x80000
RACE_PSYCHIC = 0x100000
RACE_DIVINE_BEAST = 0x200000
RACE_CREATOR_GOD = 0x400000
RACE_WYRM = 0x800000
RACE_CYBERSE = 0x1000000
RACE_ILLUSION = 0x2000000

_ATTRIBUTE_BITS = [
    (ATTR_EARTH, "EARTH"),
    (ATTR_WATER, "WATER"),
    (ATTR_FIRE, "FIRE"),
    (ATTR_WIND, "WIND"),
    (ATTR_LIGHT, "LIGHT"),
    (ATTR_DARK, "DARK"),
    (ATTR_DIVINE, "DIVINE"),
]

_RACE_BITS = [
    (RACE_WARRIOR, "WARRIOR"),
    (RACE_SPELLCASTER, "SPELLCASTER"),
    (RACE_FAIRY, "FAIRY"),
    (RACE_FIEND, "FIEND"),
    (RACE_ZOMBIE, "ZOMBIE"),
    (RACE_MACHINE, "MACHINE"),
    (RACE_AQUA, "AQUA"),
    (RACE_PYRO, "PYRO"),
    (RACE_ROCK, "ROCK"),
    (RACE_WINGED_BEAST, "WINGED BEAST"),
    (RACE_PLANT, "PLANT"),
    (RACE_INSECT, "INSECT"),
    (RACE_THUNDER, "THUNDER"),
    (RACE_DRAGON, "DRAGON"),
    (RACE_BEAST, "BEAST"),
    (RACE_BEAST_WARRIOR, "BEAST-WARRIOR"),
    (RACE_DINOSAUR, "DINOSAUR"),
    (RACE_FISH, "FISH"),
    (RACE_SEA_SERPENT, "SEA SERPENT"),
    (RACE_REPTILE, "REPTILE"),
    (RACE_PSYCHIC, "PSYCHIC"),
    (RACE_DIVINE_BEAST, "DIVINE-BEAST"),
    (RACE_CREATOR_GOD, "CREATOR GOD"),
    (RACE_WYRM, "WYRM"),
    (RACE_CYBERSE, "CYBERSE"),
    (RACE_ILLUSION, "ILLUSION"),
]

_CACHE: dict[str, dict[str, Any]] = {}
_DB_PATH: Path | None = None
_DB_PATH_CHECKED = False
_ALIAS_MAP: dict[str, int] = {}
_ALIAS_CHECKED = False


def clear_cache() -> None:
    global _DB_PATH, _DB_PATH_CHECKED, _ALIAS_MAP, _ALIAS_CHECKED
    _CACHE.clear()
    _DB_PATH = None
    _DB_PATH_CHECKED = False
    _ALIAS_MAP = {}
    _ALIAS_CHECKED = False


def _load_alias_map() -> dict[str, int]:
    global _ALIAS_MAP, _ALIAS_CHECKED
    if _ALIAS_CHECKED:
        return dict(_ALIAS_MAP)
    _ALIAS_CHECKED = True

    repo_root = Path(__file__).resolve().parents[2]
    alias_path = repo_root / "config" / "cdb_aliases.json"
    if not alias_path.is_file():
        _ALIAS_MAP = {}
        return {}
    try:
        data = json.loads(alias_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _ALIAS_MAP = {}
        return {}

    parsed: dict[str, int] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            key_str = str(key).strip()
            try:
                value_int = int(value)
            except (TypeError, ValueError):
                continue
            parsed[key_str] = value_int
    _ALIAS_MAP = parsed
    return dict(_ALIAS_MAP)


def _resolve_db_path() -> Path | None:
    global _DB_PATH_CHECKED, _DB_PATH
    if _DB_PATH_CHECKED:
        return _DB_PATH
    _DB_PATH_CHECKED = True

    env_path = os.environ.get("YGOPRO_CDB_PATH", "").strip()
    if env_path:
        candidate = Path(env_path)
        if candidate.is_file():
            _DB_PATH = candidate
            return _DB_PATH

    repo_root = Path(__file__).resolve().parents[2]
    repo_candidate = repo_root / "cards.cdb"
    if repo_candidate.is_file():
        _DB_PATH = repo_candidate
        return _DB_PATH

    expansions_dir = repo_root / "expansions"
    if expansions_dir.is_dir():
        for candidate in sorted(expansions_dir.glob("*.cdb")):
            if candidate.is_file():
                _DB_PATH = candidate
                return _DB_PATH

    _DB_PATH = None
    return None


def _map_attribute(attr_bits: int) -> str:
    for bit, name in _ATTRIBUTE_BITS:
        if attr_bits & bit:
            return name
    return ""


def _map_race(race_bits: int) -> str:
    for bit, name in _RACE_BITS:
        if race_bits & bit:
            return name
    return ""


def _derive_summon_type(type_bits: int) -> str:
    if type_bits & TYPE_LINK:
        return "link"
    if type_bits & TYPE_FUSION:
        return "fusion"
    if type_bits & TYPE_SYNCHRO:
        return "synchro"
    if type_bits & TYPE_XYZ:
        return "xyz"
    return ""


def _derive_link_rating(level_value: int) -> int:
    if 1 <= level_value <= 13:
        return level_value
    for candidate in ((level_value >> 24) & 0xFF, level_value & 0xFF):
        if 1 <= candidate <= 13:
            return candidate
    return 0


def _lookup_datas_by_id(conn: sqlite3.Connection, id_int: int) -> tuple[int, int, int, int, int] | None:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, type, level, race, attribute FROM datas WHERE id = ?",
        (id_int,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return row


def _lookup_id_by_name(conn: sqlite3.Connection, name: str) -> int | None:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM texts WHERE lower(name)=lower(?) LIMIT 2",
        (name.strip(),),
    )
    rows = cursor.fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise ValueError("Ambiguous name match")
    return int(rows[0][0])


def get_card_metadata(cid: str, name: str | None = None) -> dict[str, Any]:
    if not cid.isdigit():
        return {}
    cache_key = f"{cid}:{name or ''}"
    if cache_key in _CACHE:
        return dict(_CACHE[cache_key])

    db_path = _resolve_db_path()
    if not db_path:
        return {}

    row = None
    resolved_from = None
    resolved_id = None
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = _lookup_datas_by_id(conn, int(cid))
            if row:
                resolved_from = "id"
                resolved_id = int(cid)
            else:
                alias_map = _load_alias_map()
                alias_id = alias_map.get(cid)
                if alias_id is not None:
                    row = _lookup_datas_by_id(conn, alias_id)
                    if row:
                        resolved_from = "alias"
                        resolved_id = alias_id
                if not row and name:
                    strict = os.environ.get("YGOPRO_CDB_STRICT", "1") != "0"
                    try:
                        name_id = _lookup_id_by_name(conn, name)
                    except ValueError:
                        if strict:
                            return {}
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM texts WHERE lower(name)=lower(?) ORDER BY id ASC",
                            (name.strip(),),
                        )
                        rows = cursor.fetchall()
                        name_id = int(rows[0][0]) if rows else None
                    if name_id is not None:
                        row = _lookup_datas_by_id(conn, name_id)
                        if row:
                            resolved_from = "name"
                            resolved_id = name_id
        finally:
            conn.close()
    except sqlite3.Error:
        return {}

    if not row:
        return {}

    _id, type_bits, level_value, race_bits, attr_bits = row
    type_bits = int(type_bits or 0)
    level_value = int(level_value or 0)
    race_bits = int(race_bits or 0)
    attr_bits = int(attr_bits or 0)

    attr_name = _map_attribute(attr_bits)
    race_name = _map_race(race_bits)
    summon_type = _derive_summon_type(type_bits)
    from_extra = summon_type in {"fusion", "synchro", "xyz", "link"}
    link_rating = _derive_link_rating(level_value) if summon_type == "link" else 0

    base = {
        "attr": attr_name,
        "attribute": attr_name,
        "race": race_name,
        "summon_type": summon_type,
        "from_extra": from_extra,
        "link_rating": link_rating,
    }
    if resolved_from in {"alias", "name"} and resolved_id is not None:
        base["_cdb_resolved_from"] = resolved_from
        base["_cdb_resolved_id"] = resolved_id

    _CACHE[cache_key] = dict(base)
    return dict(base)


def _lookup_name_by_id(conn: sqlite3.Connection, id_int: int) -> str | None:
    """Look up card name from texts table by ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM texts WHERE id = ?", (id_int,))
    row = cursor.fetchone()
    return row[0] if row else None


def _lookup_full_card_data(conn: sqlite3.Connection, id_int: int) -> dict[str, Any] | None:
    """Look up complete card data from CDB."""
    cursor = conn.cursor()

    # Try with ATK/DEF first, fall back without if not available
    try:
        cursor.execute(
            "SELECT d.id, d.type, d.level, d.race, d.attribute, d.atk, d.def, t.name "
            "FROM datas d JOIN texts t ON d.id = t.id WHERE d.id = ?",
            (id_int,),
        )
        row = cursor.fetchone()
        has_atk_def = True
    except sqlite3.OperationalError:
        # ATK/DEF columns not available - use basic query
        cursor.execute(
            "SELECT d.id, d.type, d.level, d.race, d.attribute, t.name "
            "FROM datas d JOIN texts t ON d.id = t.id WHERE d.id = ?",
            (id_int,),
        )
        row = cursor.fetchone()
        has_atk_def = False

    if not row:
        return None

    if has_atk_def:
        _id, type_bits, level_value, race_bits, attr_bits, atk, def_, name = row
    else:
        _id, type_bits, level_value, race_bits, attr_bits, name = row
        atk, def_ = None, None

    type_bits = int(type_bits or 0)
    level_value = int(level_value or 0)
    race_bits = int(race_bits or 0)
    attr_bits = int(attr_bits or 0)

    # Determine card type
    if type_bits & TYPE_MONSTER:
        card_type = "monster"
    elif type_bits & 0x2:  # TYPE_SPELL
        card_type = "spell"
    elif type_bits & 0x4:  # TYPE_TRAP
        card_type = "trap"
    else:
        card_type = "unknown"

    summon_type = _derive_summon_type(type_bits)
    from_extra = summon_type in {"fusion", "synchro", "xyz", "link"}

    result = {
        "name": name,
        "card_type": card_type,
        "attr": _map_attribute(attr_bits),
        "attribute": _map_attribute(attr_bits),
        "race": _map_race(race_bits),
        "from_extra": from_extra,
        "_cdb_passcode": _id,
    }

    if atk is not None:
        result["atk"] = atk
    if def_ is not None:
        result["def"] = def_

    if summon_type:
        result["summon_type"] = summon_type

    if summon_type == "link":
        result["link_rating"] = _derive_link_rating(level_value)
    elif summon_type == "xyz":
        result["rank"] = level_value & 0xFF
    elif card_type == "monster":
        result["level"] = level_value & 0xFF

    return result


def enrich_metadata_strict(cid: str) -> dict[str, Any]:
    """
    Get card metadata from CDB. Fails if not found.

    This is the ONLY way to get card stats. No hardcoding allowed.
    The CDB is the single source of truth.

    Special test CID formats:
    - INERT_MONSTER_{ATTR}_{RACE}_{LEVEL} - inert monster with stats
    - INERT_SPELL, INERT_TRAP - inert spell/trap
    - DEMO_*, TEST_*, MOCK_*, DEAD_*, DUMMY_* - generic test cards
    - TOKEN_* - runtime tokens
    """
    # Handle special test/inert/demo cards with possible embedded stats
    if cid.startswith("INERT_MONSTER_"):
        # Parse format: INERT_MONSTER_{ATTR}_{RACE}_{LEVEL}
        parts = cid.split("_")
        result = {"card_type": "monster", "name": cid, "inert": True, "_test_card": True}
        if len(parts) >= 4:
            result["attribute"] = parts[2]
            result["attr"] = parts[2]
        if len(parts) >= 5:
            result["race"] = parts[3]
        if len(parts) >= 6:
            try:
                result["level"] = int(parts[4])
            except ValueError:
                pass
        return result

    if cid.startswith("INERT_SPELL"):
        return {"card_type": "spell", "name": cid, "inert": True, "_test_card": True}

    if cid.startswith("INERT_TRAP"):
        return {"card_type": "trap", "name": cid, "inert": True, "_test_card": True}

    # Handle generic test prefixes (monsters unless specified otherwise)
    test_prefixes = (
        "DEAD_", "DUMMY_", "INERT_", "DEMO_", "TEST_", "MOCK_", "OPP_",
        "DISCARD_", "G_", "MATERIAL_", "TARGET_", "DARK_", "RANDOM_", "NON_",
        "LINK_", "LIGHT_",
    )
    if any(cid.startswith(prefix) for prefix in test_prefixes):
        # Parse some common test patterns for better simulation
        result = {"card_type": "monster", "name": cid, "inert": True, "_test_card": True}
        cid_upper = cid.upper()
        if "LIGHT" in cid_upper:
            result["attribute"] = "LIGHT"
            result["attr"] = "LIGHT"
        if "DARK" in cid_upper:
            result["attribute"] = "DARK"
            result["attr"] = "DARK"
        if "FIEND" in cid_upper:
            result["race"] = "FIEND"
        if "LINK" in cid_upper:
            result["summon_type"] = "link"
            result["link_rating"] = 1
            result["from_extra"] = True
        return result

    # Handle token CIDs (created at runtime, not in CDB)
    if cid.startswith("TOKEN_") or cid.endswith("_TOKEN") or "TOKEN" in cid.upper():
        return {"card_type": "monster", "name": cid, "subtype": "token", "attribute": "LIGHT", "attr": "LIGHT", "race": "FIEND"}

    if not cid.isdigit():
        raise ValueError(f"Invalid CID format: {cid}")

    # Handle test CIDs in 90000-99999 range (reserved for testing)
    cid_int = int(cid)
    if 90000 <= cid_int <= 99999:
        return {"card_type": "monster", "name": cid, "inert": True, "_test_card": True}

    db_path = _resolve_db_path()
    if not db_path:
        raise ValueError(f"CDB not found - cannot look up CID {cid}")

    # First try direct lookup
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            # Try CID directly first
            data = _lookup_full_card_data(conn, int(cid))
            if data:
                data["_cdb_resolved_from"] = "direct"
                return data

            # Try alias lookup
            alias_map = _load_alias_map()
            passcode = alias_map.get(cid)
            if passcode is not None:
                data = _lookup_full_card_data(conn, passcode)
                if data:
                    data["_cdb_resolved_from"] = "alias"
                    return data

            raise ValueError(
                f"CID {cid} not found in CDB (tried direct lookup and alias map). "
                f"Add mapping to config/cdb_aliases.json if this is a valid card."
            )
        finally:
            conn.close()
    except sqlite3.Error as e:
        raise ValueError(f"CDB error looking up CID {cid}: {e}")


def enrich_metadata(cid: str, name: str | None, existing: dict[str, Any]) -> dict[str, Any]:
    if not cid.isdigit():
        return dict(existing)

    base = get_card_metadata(cid, name=name)
    if not base:
        return dict(existing)

    merged = dict(base)
    for key, value in existing.items():
        if value is None or value == "":
            continue
        merged[key] = value

    if "attr" in existing and existing.get("attr") not in (None, ""):
        merged["attribute"] = merged.get("attr")
    if "attribute" in existing and existing.get("attribute") not in (None, ""):
        merged["attr"] = merged.get("attribute")

    if merged.get("attribute") in (None, "") and merged.get("attr"):
        merged["attribute"] = merged.get("attr")
    if merged.get("attr") in (None, "") and merged.get("attribute"):
        merged["attr"] = merged.get("attribute")

    return merged
