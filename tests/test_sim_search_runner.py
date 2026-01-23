import subprocess
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]


class TestSimSearchRunner(unittest.TestCase):
    def test_search_combo_runner(self):
        scenario = repo_root / "tests" / "fixtures" / "combo_scenarios" / "fixture_search_combo.json"
        report = repo_root / "reports" / "combos" / "fixture_search_combo.md"
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
        content = report.read_text(encoding="utf-8")
        self.assertIn("Combo Search Report", content)
        self.assertIn("Core Actions", content)
        self.assertIn("Effect Actions", content)
        self.assertIn("Endboard Evaluation", content)

    def test_search_combo_effect_action(self):
        scenario = repo_root / "tests" / "fixtures" / "combo_scenarios" / "fixture_effect_action.json"
        report = repo_root / "reports" / "combos" / "fixture_effect_action.md"
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
        content = report.read_text(encoding="utf-8")
        self.assertIn("Effect Actions", content)
        self.assertIn("Demo Extender", content)


if __name__ == "__main__":
    unittest.main()
