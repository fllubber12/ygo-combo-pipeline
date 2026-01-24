#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sim.effects.registry import EFFECT_REGISTRY  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "combo_scenarios"
DECKLIST_DIR = REPO_ROOT / "decklists"

INERT_CIDS = {
    "DISCARD_1",
    "90001",
    "90002",
    "DUMMY_1",
    "DUMMY_2",
    "DUMMY_3",
    "DUMMY_4",
    "FIENDSMITH_TOKEN",
    "G_LIGHT_FIEND_A",
    "G_LIGHT_FIEND_B",
    "G_LINK_MAT",
    "OPP_CARD_1",
    "INERT_01",
    "INERT_02",
    "INERT_03",
    "RANDOM_CARD",
    # New INERT_MONSTER_* format CIDs
    "INERT_MONSTER_LIGHT_FIEND_4",
    "INERT_MONSTER_DARK_FIEND_6",
}


def collect_cids(obj, out: set[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "cid" and isinstance(value, str):
                out.add(value)
                continue
            collect_cids(value, out)
    elif isinstance(obj, list):
        for item in obj:
            collect_cids(item, out)


def parse_decklist(path: Path) -> set[str]:
    cids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith("!"):
            continue
        cids.add(stripped)
    return cids


def main() -> int:
    if not FIXTURE_DIR.exists():
        print(f"Missing fixture dir: {FIXTURE_DIR}", file=sys.stderr)
        return 1
    if not DECKLIST_DIR.exists():
        print(f"Missing decklist dir: {DECKLIST_DIR}", file=sys.stderr)
        return 1

    fixture_cids: set[str] = set()
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        collect_cids(data, fixture_cids)

    decklist_cids: set[str] = set()
    for path in sorted(DECKLIST_DIR.glob("*.ydk")):
        decklist_cids.update(parse_decklist(path))

    required_cids = fixture_cids | decklist_cids
    registered = set(EFFECT_REGISTRY.keys())
    inert = set(INERT_CIDS)

    # Check for inert patterns (INERT_*, DEMO_*, DUMMY_*, etc.)
    inert_prefixes = ("INERT_", "DEMO_", "DUMMY_", "TEST_", "MOCK_", "OPP_", "G_", "DEAD_", "TOKEN_", "DISCARD_")

    def is_inert(cid: str) -> bool:
        if cid in inert:
            return True
        return any(cid.startswith(prefix) for prefix in inert_prefixes)

    missing = sorted(cid for cid in required_cids if cid not in registered and not is_inert(cid))

    print(f"Registered CIDs ({len(registered)}):")
    for cid in sorted(registered):
        print(f"  {cid}")

    print(f"Inert CIDs ({len(inert)}):")
    for cid in sorted(inert):
        print(f"  {cid}")

    print(f"Fixture CIDs ({len(fixture_cids)}):")
    for cid in sorted(fixture_cids):
        print(f"  {cid}")

    print(f"Decklist CIDs ({len(decklist_cids)}):")
    for cid in sorted(decklist_cids):
        print(f"  {cid}")

    print(f"Missing CIDs ({len(missing)}):")
    for cid in missing:
        print(f"  {cid}")

    if missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
