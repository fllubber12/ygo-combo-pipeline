#!/usr/bin/env python3
"""Run a deterministic combo search over a scenario."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "src"))

from combos.endboard_evaluator import evaluate_endboard  # noqa: E402
from sim.actions import Action  # noqa: E402
from sim.convert import game_state_to_endboard_snapshot  # noqa: E402
from sim.effects.types import EffectAction  # noqa: E402
from sim.search import search_best_line  # noqa: E402
from sim.state import GameState  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic combo search.")
    parser.add_argument("--scenario", required=True, help="Path to scenario JSON.")
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--beam-width", type=int, default=None)
    return parser.parse_args()


def load_scenario(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_report(name: str, result, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot = game_state_to_endboard_snapshot(result.final_state)
    lines = []
    lines.append(f"# Combo Search Report: {name}")
    lines.append("")
    core_actions = [action for action in result.actions if isinstance(action, Action)]
    effect_actions = [action for action in result.actions if isinstance(action, EffectAction)]

    lines.append("## Core Actions")
    if core_actions:
        for idx, action in enumerate(core_actions, start=1):
            lines.append(f"{idx}. {action.describe()}")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Effect Actions")
    if effect_actions:
        for idx, action in enumerate(effect_actions, start=1):
            lines.append(f"{idx}. {action.describe()}")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Final Snapshot")
    lines.append("```json")
    lines.append(json.dumps(snapshot, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Endboard Evaluation")
    lines.append(f"- rank_key: {result.evaluation['rank_key']}")
    lines.append(f"- summary: {result.evaluation['summary']}")
    lines.append("- achieved:")
    if result.evaluation["achieved"]:
        for item in result.evaluation["achieved"]:
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
    name = scenario.get("name", scenario_path.stem)

    state = GameState.from_snapshot(scenario.get("state", {}))
    search_cfg = scenario.get("search", {})

    max_depth = args.max_depth if args.max_depth is not None else int(search_cfg.get("max_depth", 2))
    beam_width = args.beam_width if args.beam_width is not None else int(search_cfg.get("beam_width", 10))
    allowed_actions = search_cfg.get("allowed_actions")
    prefer_longest = bool(search_cfg.get("prefer_longest", False))

    result = search_best_line(
        state,
        max_depth=max_depth,
        beam_width=beam_width,
        allowed_actions=allowed_actions,
        prefer_longest=prefer_longest,
    )

    out_path = repo_root / "reports" / "combos" / f"{name}.md"
    write_report(name, result, out_path)

    evaluation = evaluate_endboard(game_state_to_endboard_snapshot(result.final_state))
    print(f"Combo search report: {out_path}")
    print(f"Endboard: {evaluation['summary']}")


if __name__ == "__main__":
    main()
