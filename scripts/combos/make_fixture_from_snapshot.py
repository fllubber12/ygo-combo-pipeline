#!/usr/bin/env python3
"""Build a combo_scenario fixture from a batch final_snapshot JSON payload."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a combo_scenario fixture from a batch snapshot JSON.")
    parser.add_argument("snapshot_path", help="Path to *_final_snapshot.json")
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output fixture path. Defaults to tests/fixtures/combo_scenarios/fixture_from_batch_<stem>.json",
    )
    parser.add_argument("--name", default=None, help="Optional fixture name override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot_path = Path(args.snapshot_path)
    if not snapshot_path.exists():
        raise SystemExit(f"Missing snapshot: {snapshot_path}")

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    state_snapshot = payload.get("final_state_snapshot") or payload.get("final_snapshot")
    if not isinstance(state_snapshot, dict):
        raise SystemExit("Snapshot payload missing final_state_snapshot.")

    zones = state_snapshot.get("zones", {})
    if "field_zones" not in zones:
        raise SystemExit("final_state_snapshot does not include field_zones; cannot build fixture.")

    stem = snapshot_path.stem
    fixture_name = args.name or f"fixture_from_batch_{stem}"

    if args.out:
        out_path = Path(args.out)
    else:
        repo_root = Path(__file__).resolve().parents[2]
        out_path = repo_root / "tests" / "fixtures" / "combo_scenarios" / f"{fixture_name}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    fixture = {
        "name": fixture_name,
        "state": state_snapshot,
        "search": {
            "max_depth": 0,
            "beam_width": 10,
            "allowed_actions": [],
        },
    }

    out_path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote fixture: {out_path}")


if __name__ == "__main__":
    main()
