import subprocess
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]


class TestScriptedComboRunner(unittest.TestCase):
    def test_scripted_combo_report(self):
        scenario = repo_root / "tests" / "fixtures" / "combo_scenarios" / "fixture_combo.json"
        report = repo_root / "reports" / "scripted_combo_fixture_combo.md"
        if report.exists():
            report.unlink()
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "combos" / "run_scripted_combo.py"),
                "--scenario",
                str(scenario),
            ],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(report.exists())

        data = report.read_text(encoding="utf-8")
        self.assertIn("Scripted Combo Report", data)


if __name__ == "__main__":
    unittest.main()
