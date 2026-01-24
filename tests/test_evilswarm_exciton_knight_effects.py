import json
import subprocess
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))


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


class TestModeledExtraDeckEffects(unittest.TestCase):
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

    def test_exciton_knight_wipe(self):
        snapshot = self.run_scenario("fixture_exciton_knight_wipe")
        self.assertIn("Evilswarm Exciton Knight", snapshot["zones"]["field"])
        self.assertIn("OPP_CARD_1", snapshot["zones"]["gy"])

    def test_caesar_negate_send(self):
        snapshot = self.run_scenario("fixture_caesar_negate_send")
        self.assertIn("D/D/D Wave High King Caesar", snapshot["zones"]["field"])
        self.assertIn("OPP_CARD_1", snapshot["zones"]["gy"])


class TestInertEffects(unittest.TestCase):
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

    def test_inert_fixtures(self):
        cases = []
        for scenario, card_name, zone in cases:
            snapshot = self.run_scenario(scenario)
            self.assertIn(card_name, snapshot["zones"][zone])


if __name__ == "__main__":
    unittest.main()
