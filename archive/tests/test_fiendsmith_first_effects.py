import subprocess
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]


class TestFiendsmithFirstEffects(unittest.TestCase):
    def test_kyrie_in_gy_search(self):
        scenario = repo_root / "tests" / "fixtures" / "combo_scenarios" / "fixture_kyrie_in_gy.json"
        report = repo_root / "reports" / "combos" / "fixture_kyrie_in_gy.md"
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
        self.assertIn("Fiendsmith Kyrie in GY", content)
        self.assertIn("summary: S=0 A=0 B=1", content)


if __name__ == "__main__":
    unittest.main()
