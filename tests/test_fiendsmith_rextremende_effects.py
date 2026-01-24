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


class TestFiendsmithRextremendeEffects(unittest.TestCase):
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

    def test_rextremende_discard_send(self):
        snapshot = self.run_scenario("fixture_rextremende_send_light_fiend")
        self.assertIn("DISCARD_1", snapshot["zones"]["gy"])
        self.assertIn("Fiendsmith Engraver", snapshot["zones"]["gy"])

    def test_rextremende_recover(self):
        snapshot = self.run_scenario("fixture_rextremende_recover_from_gy")
        self.assertIn("Fiendsmith's Tract", snapshot["zones"]["hand"])


if __name__ == "__main__":
    unittest.main()
