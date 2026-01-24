#!/usr/bin/env python3
"""
Validate ALL card stats against CDB ground truth.

For every card in the library, verify:
- Level/Rank/Link Rating
- ATK/DEF
- Attribute
- Race/Type
- Card Type (Monster/Spell/Trap)
"""

import json
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sim.ygopro_cdb import (
    _resolve_db_path,
    _load_alias_map,
    _map_attribute,
    _map_race,
    _derive_summon_type,
    _derive_link_rating,
    TYPE_MONSTER,
    TYPE_LINK,
    TYPE_FUSION,
    TYPE_SYNCHRO,
    TYPE_XYZ,
    clear_cache,
)

REPO_ROOT = Path(__file__).parent.parent
VERIFIED_EFFECTS = REPO_ROOT / "config" / "verified_effects.json"
CDB_ALIASES = REPO_ROOT / "config" / "cdb_aliases.json"


def load_verified_effects():
    return json.loads(VERIFIED_EFFECTS.read_text())


def load_cdb_aliases():
    if CDB_ALIASES.exists():
        data = json.loads(CDB_ALIASES.read_text())
        # Filter out _meta key
        return {k: v for k, v in data.items() if not k.startswith("_")}
    return {}


def get_full_cdb_stats(passcode: int) -> dict:
    """Get ALL stats from CDB for a card by passcode."""
    db_path = _resolve_db_path()
    if not db_path:
        return {}

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, type, level, race, attribute, atk, def FROM datas WHERE id = ?",
            (passcode,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {}

        _id, type_bits, level_value, race_bits, attr_bits, atk, def_ = row
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

        result = {
            "passcode": _id,
            "card_type": card_type,
            "attribute": _map_attribute(attr_bits),
            "race": _map_race(race_bits),
            "atk": atk,
            "def": def_,
        }

        if summon_type:
            result["summon_type"] = summon_type

        if summon_type == "link":
            result["link_rating"] = _derive_link_rating(level_value)
        elif summon_type == "xyz":
            # For Xyz, level field stores rank
            result["rank"] = level_value & 0xFF
        elif card_type == "monster":
            result["level"] = level_value & 0xFF

        return result

    except sqlite3.Error as e:
        return {"error": str(e)}


def validate_all_cards():
    clear_cache()
    effects = load_verified_effects()
    aliases = load_cdb_aliases()

    results = []

    for cid, card_data in effects.items():
        if cid.startswith("_"):
            continue

        name = card_data.get("name", cid)

        # Get passcode from alias map
        passcode = aliases.get(cid)
        if passcode is None:
            # Try using CID directly as passcode
            try:
                passcode = int(cid)
            except ValueError:
                results.append({
                    "cid": cid,
                    "name": name,
                    "status": "ERROR",
                    "reason": "No alias mapping and CID is not a valid passcode"
                })
                continue

        # Get CDB stats
        cdb_stats = get_full_cdb_stats(passcode)

        if not cdb_stats:
            results.append({
                "cid": cid,
                "name": name,
                "passcode": passcode,
                "status": "ERROR",
                "reason": "Not found in CDB"
            })
            continue

        if "error" in cdb_stats:
            results.append({
                "cid": cid,
                "name": name,
                "passcode": passcode,
                "status": "ERROR",
                "reason": cdb_stats["error"]
            })
            continue

        # Compare key stats - only check fields that are defined in JSON
        issues = []

        # Check card type
        json_type = card_data.get("card_type", "").lower()
        cdb_type = cdb_stats.get("card_type", "").lower()
        if json_type and json_type != cdb_type:
            issues.append(f"card_type: JSON={json_type}, CDB={cdb_type}")

        # Check summon type (for Extra Deck monsters)
        json_summon = card_data.get("summon_type", "").lower()
        cdb_summon = cdb_stats.get("summon_type", "").lower()
        if json_summon and json_summon != cdb_summon:
            issues.append(f"summon_type: JSON={json_summon}, CDB={cdb_summon}")

        # Check Link Rating (for Link monsters)
        if cdb_summon == "link":
            json_link = card_data.get("link_rating")
            cdb_link = cdb_stats.get("link_rating")
            if json_link is not None and json_link != cdb_link:
                issues.append(f"link_rating: JSON={json_link}, CDB={cdb_link}")

        # Check Level
        json_level = card_data.get("level")
        cdb_level = cdb_stats.get("level")
        if json_level is not None and cdb_level is not None and json_level != cdb_level:
            issues.append(f"level: JSON={json_level}, CDB={cdb_level}")

        # Check Rank (for Xyz)
        json_rank = card_data.get("rank")
        cdb_rank = cdb_stats.get("rank")
        if json_rank is not None and cdb_rank is not None and json_rank != cdb_rank:
            issues.append(f"rank: JSON={json_rank}, CDB={cdb_rank}")

        # Check Attribute
        json_attr = str(card_data.get("attribute", "")).upper()
        cdb_attr = str(cdb_stats.get("attribute", "")).upper()
        if json_attr and json_attr != cdb_attr:
            issues.append(f"attribute: JSON={json_attr}, CDB={cdb_attr}")

        # Check Race
        json_race = str(card_data.get("race", "")).upper()
        cdb_race = str(cdb_stats.get("race", "")).upper()
        if json_race and json_race != cdb_race:
            issues.append(f"race: JSON={json_race}, CDB={cdb_race}")

        # Check ATK
        json_atk = card_data.get("atk")
        cdb_atk = cdb_stats.get("atk")
        if json_atk is not None and cdb_atk is not None and json_atk != cdb_atk:
            issues.append(f"atk: JSON={json_atk}, CDB={cdb_atk}")

        # Check DEF
        json_def = card_data.get("def")
        cdb_def = cdb_stats.get("def")
        if json_def is not None and cdb_def is not None and json_def != cdb_def:
            issues.append(f"def: JSON={json_def}, CDB={cdb_def}")

        if issues:
            results.append({
                "cid": cid,
                "name": name,
                "passcode": passcode,
                "status": "MISMATCH",
                "issues": issues,
                "cdb_stats": cdb_stats
            })
        else:
            results.append({
                "cid": cid,
                "name": name,
                "passcode": passcode,
                "status": "OK",
                "cdb_stats": cdb_stats
            })

    return results


def print_report(results: list):
    print("=" * 80)
    print("CDB STATS VALIDATION REPORT")
    print("=" * 80)

    ok_count = len([r for r in results if r["status"] == "OK"])
    mismatch_count = len([r for r in results if r["status"] == "MISMATCH"])
    error_count = len([r for r in results if r["status"] == "ERROR"])

    print(f"\nTotal cards: {len(results)}")
    print(f"  OK: {ok_count}")
    print(f"  MISMATCH: {mismatch_count}")
    print(f"  ERROR: {error_count}")

    if mismatch_count > 0:
        print("\n" + "=" * 80)
        print("MISMATCHES (JSON has wrong values):")
        print("=" * 80)
        for r in results:
            if r["status"] == "MISMATCH":
                print(f"\n{r['cid']} - {r['name']} (passcode: {r['passcode']}):")
                for issue in r["issues"]:
                    print(f"  X {issue}")
                print(f"  CDB: {r['cdb_stats']}")

    if error_count > 0:
        print("\n" + "=" * 80)
        print("ERRORS (not found in CDB or missing alias):")
        print("=" * 80)
        for r in results:
            if r["status"] == "ERROR":
                passcode_info = f" (tried passcode: {r.get('passcode', 'N/A')})" if r.get('passcode') else ""
                print(f"  X {r['cid']} - {r['name']}{passcode_info}: {r['reason']}")

    # Print full card list with key stats
    print("\n" + "=" * 80)
    print("ALL CARDS WITH CDB STATS:")
    print("=" * 80)
    print(f"{'CID':<8} {'Passcode':<12} {'Name':<32} {'Type':<8} {'Summon':<8} {'Lv/Lnk':<6} {'Attr':<6} {'Race':<12}")
    print("-" * 100)

    # Sort by CID
    sorted_results = sorted(results, key=lambda r: int(r["cid"]) if r["cid"].isdigit() else 0)

    for r in sorted_results:
        status_marker = "" if r["status"] == "OK" else "[!]"
        if "cdb_stats" in r:
            stats = r["cdb_stats"]
            level_or_link = (
                stats.get("link_rating") or
                stats.get("rank") or
                stats.get("level") or
                "-"
            )
            summon = stats.get("summon_type", "-") or "-"
            print(f"{r['cid']:<8} {r.get('passcode', '?'):<12} {r['name'][:30]:<32} {stats.get('card_type', '?'):<8} {summon:<8} {str(level_or_link):<6} {stats.get('attribute', '?'):<6} {stats.get('race', '?'):<12} {status_marker}")
        else:
            print(f"{r['cid']:<8} {r.get('passcode', '?'):<12} {r['name'][:30]:<32} {'ERROR':<8}")

    # Summary
    print("\n" + "=" * 80)
    if mismatch_count == 0 and error_count == 0:
        print("ALL CARDS VALIDATED SUCCESSFULLY!")
    else:
        print(f"VALIDATION FAILED: {mismatch_count} mismatches, {error_count} errors")
    print("=" * 80)


if __name__ == "__main__":
    results = validate_all_cards()
    print_report(results)
