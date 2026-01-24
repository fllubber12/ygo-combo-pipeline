#!/usr/bin/env python3
"""
New Card Integration Script

Enforces the verification protocol for adding new cards.
No card can be used in combo search until it passes all gates.

Usage:
    python3 scripts/add_new_card.py --cid 12345 --passcode 98765432 --name "Card Name"
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
VERIFIED_EFFECTS = REPO_ROOT / "config" / "verified_effects.json"
LUA_DIR = REPO_ROOT / "reports" / "verified_lua"
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "combo_scenarios" / "golden"


def fetch_lua(cid: str, passcode: str) -> Path:
    """Fetch official Lua script from ProjectIgnis."""
    url = f"https://raw.githubusercontent.com/ProjectIgnis/CardScripts/master/official/c{passcode}.lua"
    output_path = LUA_DIR / f"c{passcode}.lua"

    print(f"Fetching Lua from: {url}")
    result = subprocess.run(
        ["curl", "-s", "-f", url],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"ERROR: Could not fetch Lua for passcode {passcode}")
        print("Try finding the correct passcode at https://db.ygoprodeck.com/")
        return None

    LUA_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.stdout)
    print(f"Saved to: {output_path}")
    return output_path


def create_effect_template(cid: str, name: str, lua_path: Path) -> dict:
    """Create a template for verified_effects.json entry."""

    print("\n" + "=" * 60)
    print("LUA SCRIPT CONTENTS:")
    print("=" * 60)
    print(lua_path.read_text()[:3000])  # First 3000 chars
    print("\n... (truncated, see full file at", lua_path, ")")
    print("=" * 60)

    template = {
        "name": name,
        "card_type": "FILL_IN",  # monster, spell, trap
        "source": f"https://github.com/ProjectIgnis/CardScripts/blob/master/official/{lua_path.name}",
        "effects": [
            {
                "id": "e1",
                "location": "FILL_IN",  # hand, field, gy, banished
                "effect_type": "FILL_IN",  # ignition, trigger, quick, continuous
                "cost": "FILL_IN or empty string",
                "condition": "FILL_IN or empty string",
                "action": "FILL_IN - exact effect text",
                "opt": "hard_opt or soft_opt or none",
                "lines": "FILL_IN - lua line numbers"
            }
        ]
    }

    return template


def prompt_user_verification(cid: str, template: dict) -> dict:
    """Require user to fill in and verify the template."""

    print("\n" + "=" * 60)
    print("USER VERIFICATION REQUIRED")
    print("=" * 60)
    print("\nBased on the Lua script above, fill in this template:")
    print(json.dumps(template, indent=2))
    print("\nYou must:")
    print("1. Set card_type (monster/spell/trap)")
    print("2. For EACH effect, fill in: location, effect_type, cost, condition, action, opt, lines")
    print("3. Reference specific Lua line numbers")
    print("\nOnce you've verified the effects, update config/verified_effects.json")
    print(f"Add entry under CID '{cid}'")

    input("\nPress ENTER when you've updated verified_effects.json...")

    # Reload and validate
    if not VERIFIED_EFFECTS.exists():
        print(f"ERROR: {VERIFIED_EFFECTS} does not exist")
        return None

    data = json.loads(VERIFIED_EFFECTS.read_text())
    if cid not in data:
        print(f"ERROR: CID {cid} not found in verified_effects.json")
        return None

    entry = data[cid]

    # Check for FILL_IN placeholders
    entry_str = json.dumps(entry)
    if "FILL_IN" in entry_str:
        print("ERROR: Template still contains FILL_IN placeholders")
        return None

    print(f"Entry for {cid} found and validated")
    return entry


def create_golden_fixture(cid: str, name: str, effect_id: str) -> Path:
    """Create a golden fixture template for an effect."""

    fixture = {
        "name": f"golden_{cid}_{effect_id}",
        "description": f"GOLDEN: {name} {effect_id} - FILL_IN description",
        "lua_reference": "FILL_IN - file and line numbers",
        "test": {
            "effect_id": "FILL_IN",
            "preconditions": ["FILL_IN"],
            "expected_action_count_min": 1,
            "expected_outcome": {"FILL_IN": "values"}
        },
        "state": {
            "zones": {
                "hand": [],
                "deck": [],
                "gy": [],
                "banished": [],
                "extra": [],
                "field_zones": {
                    "mz": [None, None, None, None, None],
                    "emz": [None, None],
                    "stz": [None, None, None, None, None],
                    "fz": [None]
                }
            },
            "phase": "Main Phase 1",
            "opt_used": {},
            "events": [],
            "pending_triggers": [],
            "last_moved_to_gy": []
        }
    }

    output_path = GOLDEN_DIR / f"golden_{cid}_{effect_id}.json"
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(fixture, indent=2))

    print(f"Created golden fixture template: {output_path}")
    print("You must fill in the state and expected_outcome")

    return output_path


def run_validation(cid: str) -> bool:
    """Run validation framework for the new card."""

    print("\nRunning validation framework...")
    result = subprocess.run(
        ["python3", "scripts/validate_effects_comprehensive.py"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT
    )

    # Check if any tests for this CID failed
    output = result.stdout + result.stderr

    cid_failures = [line for line in output.split('\n') if cid in line and 'fail' in line.lower()]

    if cid_failures:
        print(f"Validation failures for CID {cid}:")
        for line in cid_failures:
            print(f"  {line}")
        return False

    print(f"All validation tests pass for CID {cid}")
    return True


def run_tests() -> bool:
    """Run the full test suite."""

    print("\nRunning test suite...")
    result = subprocess.run(
        ["python3", "-m", "unittest", "discover", "-s", "tests"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT
    )

    if result.returncode != 0:
        print("Test failures detected:")
        print(result.stderr)
        return False

    print("All tests pass")
    return True


def register_effect_implementation(cid: str, name: str):
    """Remind user to implement the effect class."""

    class_name = ''.join(word.capitalize() for word in name.replace("'", "").replace("-", " ").split())

    print("\n" + "=" * 60)
    print("IMPLEMENTATION REQUIRED")
    print("=" * 60)
    print(f"""
Now implement the effect class:

1. Create class in src/sim/effects/library_effects.py (or appropriate file):

    class {class_name}Effect(EffectImpl):
        def enumerate_actions(self, state: GameState) -> list[EffectAction]:
            # Implementation based on verified_effects.json
            pass

        def apply(self, state: GameState, action: EffectAction) -> GameState:
            # Implementation based on verified_effects.json
            pass

2. Register in src/sim/effects/registry.py:

    from .library_effects import {class_name}Effect

    # In EFFECT_REGISTRY initialization:
    "{cid}": {class_name}Effect(),

3. Add to decklists/library.ydk if not already present

4. Run tests:
    python3 -m unittest discover -s tests
    python3 scripts/validate_effects_comprehensive.py
""")


def main():
    parser = argparse.ArgumentParser(
        description="Add a new card to the pipeline with verification protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 scripts/add_new_card.py --cid 12345 --passcode 98765432 --name "Card Name"

The script will:
1. Fetch the official Lua script from ProjectIgnis
2. Display the Lua and require you to fill in verified_effects.json
3. Create golden fixture templates for each effect
4. Guide you through implementing the effect class
5. Run validation to ensure correctness
        """
    )
    parser.add_argument("--cid", required=True, help="Internal CID for the card")
    parser.add_argument("--passcode", required=True, help="YGOPro passcode (8-digit number for Lua lookup)")
    parser.add_argument("--name", required=True, help="Card name")
    parser.add_argument("--skip-lua", action="store_true", help="Skip Lua fetch (if already downloaded)")
    args = parser.parse_args()

    print("=" * 60)
    print("NEW CARD INTEGRATION PROTOCOL")
    print("=" * 60)
    print(f"\nCard: {args.name}")
    print(f"CID: {args.cid}")
    print(f"Passcode: {args.passcode}")

    # Step 1: Fetch Lua
    if args.skip_lua:
        lua_path = LUA_DIR / f"c{args.passcode}.lua"
        if not lua_path.exists():
            print(f"ERROR: Lua file not found at {lua_path}")
            sys.exit(1)
        print(f"\nUsing existing Lua: {lua_path}")
    else:
        lua_path = fetch_lua(args.cid, args.passcode)
        if not lua_path:
            sys.exit(1)

    # Step 2: Create template and require user verification
    template = create_effect_template(args.cid, args.name, lua_path)
    entry = prompt_user_verification(args.cid, template)
    if not entry:
        sys.exit(1)

    # Step 3: Create golden fixtures for each effect
    print("\n" + "=" * 60)
    print("CREATING GOLDEN FIXTURES")
    print("=" * 60)
    for effect in entry.get("effects", []):
        create_golden_fixture(args.cid, args.name, effect["id"])

    # Step 4: Prompt for implementation
    register_effect_implementation(args.cid, args.name)

    input("\nPress ENTER when implementation is complete...")

    # Step 5: Run tests
    if not run_tests():
        print("\nCard not ready. Fix test failures and re-run.")
        sys.exit(1)

    # Step 6: Run validation
    if not run_validation(args.cid):
        print("\nCard not ready. Fix validation failures and re-run.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"{args.name} successfully integrated!")
    print("=" * 60)
    print("\nFinal checklist:")
    print("[ ] Lua script verified")
    print("[ ] verified_effects.json entry complete")
    print("[ ] Golden fixtures filled in")
    print("[ ] Effect class implemented and registered")
    print("[ ] All tests pass")
    print("[ ] Validation framework passes")
    print("\nNext: Test in combo search scenarios")


if __name__ == "__main__":
    main()
