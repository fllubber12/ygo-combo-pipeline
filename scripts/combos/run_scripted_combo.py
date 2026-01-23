#!/usr/bin/env python3
"""Run a scripted combo scenario with state edits."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "src"))

from combos.endboard_evaluator import evaluate_endboard  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a scripted combo scenario.")
    parser.add_argument("--scenario", required=True, help="Path to scenario JSON.")
    return parser.parse_args()


def load_scenario(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_name(name: str) -> str:
    value = name.strip()
    value = value.replace("\u2019", "'")
    value = value.replace("\u2010", "-")
    value = value.replace("\u2011", "-")
    value = value.replace("\u2013", "-")
    return value.lower()


def move_card(snapshot: dict, card: str, source: str, target: str) -> None:
    zones = snapshot.get("zones", {})
    if source not in zones or target not in zones:
        raise ValueError(f"Unknown zone in move: {source} -> {target}")

    source_list = zones[source]
    target_list = zones[target]

    card_norm = normalize_name(card)
    index = None
    for i, value in enumerate(source_list):
        if normalize_name(str(value)) == card_norm:
            index = i
            break
    if index is None:
        raise ValueError(f"Card '{card}' not found in {source}")

    item = source_list.pop(index)
    target_list.append(item)


def run_scenario(scenario: dict) -> dict:
    name = scenario.get("name", "scenario")
    snapshot = scenario.get("starting_snapshot")
    actions = scenario.get("actions", [])

    if not snapshot or "zones" not in snapshot:
        raise ValueError("Scenario missing starting_snapshot.zones")

    log = []
    for step, action in enumerate(actions, start=1):
        action_type = action.get("action")
        if action_type != "move":
            raise ValueError(f"Unsupported action type: {action_type}")
        card = action.get("card")
        source = action.get("from")
        target = action.get("to")
        if not card or not source or not target:
            raise ValueError(f"Incomplete action at step {step}")
        move_card(snapshot, card, source, target)
        log.append(f"{step}. move '{card}' {source} -> {target}")

    evaluation = evaluate_endboard(snapshot)

    return {
        "name": name,
        "log": log,
        "final_snapshot": snapshot,
        "evaluation": evaluation,
    }


def write_report(result: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# Scripted Combo Report: {result['name']}")
    lines.append("")
    lines.append("## Action Log")
    if result["log"]:
        for entry in result["log"]:
            lines.append(f"- {entry}")
    else:
        lines.append("- (no actions)")
    lines.append("")
    lines.append("## Final Snapshot")
    lines.append("```json")
    lines.append(json.dumps(result["final_snapshot"], indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Endboard Evaluation")
    lines.append(f"- rank_key: {result['evaluation']['rank_key']}")
    lines.append(f"- summary: {result['evaluation']['summary']}")
    lines.append("- achieved:")
    if result["evaluation"]["achieved"]:
        for item in result["evaluation"]["achieved"]:
            lines.append(
                f"  - {item['bucket']} {item['kind']} {item['name']} (zone={item['zone']})"
            )
    else:
        lines.append("  - (none)")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    scenario_path = Path(args.scenario)
    if not scenario_path.exists():
        raise SystemExit(f"Missing scenario file: {scenario_path}")

    scenario = load_scenario(scenario_path)
    result = run_scenario(scenario)

    name = scenario.get("name", scenario_path.stem)
    report_path = repo_root / "reports" / f"scripted_combo_{name}.md"
    write_report(result, report_path)

    print(f"Scripted combo report: {report_path}")


if __name__ == "__main__":
    main()
