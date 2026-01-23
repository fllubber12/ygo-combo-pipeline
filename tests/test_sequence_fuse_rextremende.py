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


class TestSequenceFuseRextremende(unittest.TestCase):
    def test_sequence_fuse_rextremende_fixture(self):
        scenario = repo_root / "tests" / "fixtures" / "combo_scenarios" / (
            "fixture_sequence_fuse_desirae_then_fuse_rextremende.json"
        )
        report = repo_root / "reports" / "combos" / (
            "fixture_sequence_fuse_desirae_then_fuse_rextremende.md"
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
        field_names = snapshot["zones"]["field"]
        self.assertIn("Fiendsmith's Rextremende", field_names)
        self.assertNotIn("Fiendsmith's Desirae", field_names)

        extra_names = snapshot["zones"]["extra"]
        self.assertIn("Fiendsmith's Desirae", extra_names)


if __name__ == "__main__":
    unittest.main()
