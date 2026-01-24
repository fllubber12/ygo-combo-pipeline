import json
import subprocess
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from sim.effects.registry import apply_effect_action, enumerate_effect_actions  # noqa: E402
from sim.state import GameState  # noqa: E402


def load_snapshot(report_path: Path) -> dict:
    content = report_path.read_text(encoding="utf-8")
    start = content.find("```json")
    if start == -1:
        raise AssertionError("Missing JSON block in report.")
    start = content.find("\n", start) + 1
    end = content.find("```", start)
    if end == -1:
        raise AssertionError("Unterminated JSON block in report.")
    return json.loads(content[start:end])


class TestFiendsmithLacrimaEffects(unittest.TestCase):
    def run_scenario(self, scenario_name: str) -> dict:
        scenario = repo_root / "tests" / "fixtures" / "combo_scenarios" / f"{scenario_name}.json"
        report = repo_root / "reports" / "combos" / f"{scenario_name}.md"
        if report.exists():
            report.unlink()
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "combos" / "search_combo.py"),
                "--scenario",
                str(scenario),
            ],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(report.exists())
        return load_snapshot(report)

    def test_lacrima_fusion_recover_ss_fixture(self):
        snapshot = self.run_scenario("fixture_lacrima_fusion_recover_ss")
        self.assertIn("Fiendsmith Engraver", snapshot["zones"]["field"])
        self.assertNotIn("Fiendsmith Engraver", snapshot["zones"]["gy"])

    def test_lacrima_gy_burn_fixture(self):
        fixture = repo_root / "tests" / "fixtures" / "combo_scenarios" / "fixture_lacrima_gy_shuffle_light_fiend.json"
        data = json.loads(fixture.read_text(encoding="utf-8"))
        state = GameState.from_snapshot(data.get("state", {}))
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "lacrima_gy_burn"
        ]
        self.assertTrue(actions)
        new_state = apply_effect_action(state, actions[0])
        self.assertIn("LACRIMA_BURN_1200", new_state.restrictions)
        self.assertTrue(new_state.opt_used.get("20214:e2"))


if __name__ == "__main__":
    unittest.main()
