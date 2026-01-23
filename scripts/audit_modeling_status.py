#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sim.effects.registry import EFFECT_REGISTRY  # noqa: E402
from sim.effects.inert_effects import INERT_EFFECT_CIDS, InertEffect  # noqa: E402

DECKLIST_PATH = REPO_ROOT / "decklists" / "library.ydk"

ALLOWED_STUB_CIDS: set[str] = set()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit modeled vs stubbed effects.")
    parser.add_argument("--fail", action="store_true", help="Exit nonzero on stubs/missing.")
    return parser.parse_args()


def parse_decklist(path: Path) -> list[str]:
    cids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith("!"):
            continue
        cids.append(stripped)
    return cids


def main() -> int:
    args = parse_args()

    if not DECKLIST_PATH.exists():
        print(f"Missing decklist: {DECKLIST_PATH}", file=sys.stderr)
        return 1

    decklist_cids = sorted(set(parse_decklist(DECKLIST_PATH)), key=lambda x: int(x))

    modeled = 0
    stubbed = []
    missing = []
    for cid in decklist_cids:
        effect = EFFECT_REGISTRY.get(cid)
        if effect is None:
            missing.append(cid)
            continue
        if isinstance(effect, InertEffect):
            if cid not in ALLOWED_STUB_CIDS:
                stubbed.append(cid)
            continue
        modeled += 1

    print(f"Decklist CIDs: {len(decklist_cids)}")
    print(f"Modeled count: {modeled}")
    print(f"Stub count (excluding allowed): {len(stubbed)}")
    print(f"Missing count: {len(missing)}")

    print("Stub CIDs (excluding allowed):")
    if stubbed:
        for cid in stubbed:
            name = INERT_EFFECT_CIDS.get(cid, "Unknown")
            print(f"  {cid} {name}")
    else:
        print("  (none)")

    print("Missing CIDs:")
    if missing:
        for cid in missing:
            print(f"  {cid}")
    else:
        print("  (none)")

    if args.fail and (stubbed or missing):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
