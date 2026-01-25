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


class TestFiendsmithInParadiseEffects(unittest.TestCase):
    def test_paradise_gy_send_rextremende_fixture(self):
        scenario = repo_root / "tests" / "fixtures" / "combo_scenarios" / (
            "fixture_paradise_gy_send_rextremende.json"
        )
        report = repo_root / "reports" / "combos" / (
            "fixture_paradise_gy_send_rextremende.md"
        )
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

        snapshot = load_snapshot(report)
        self.assertIn("Fiendsmith in Paradise", snapshot["zones"]["banished"])
        self.assertIn("Fiendsmith's Rextremende", snapshot["zones"]["gy"])
        self.assertNotIn("Fiendsmith's Rextremende", snapshot["zones"]["extra"])


if __name__ == "__main__":
    unittest.main()
