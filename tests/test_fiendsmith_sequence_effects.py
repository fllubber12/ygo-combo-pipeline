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


class TestFiendsmithSequenceEffects(unittest.TestCase):
    def test_sequence_shuffle_fuse_and_equip_fixture(self):
        scenario = repo_root / "tests" / "fixtures" / "combo_scenarios" / (
            "fixture_desirae_via_sequence_shuffle_fuse_and_equip.json"
        )
        report = repo_root / "reports" / "combos" / (
            "fixture_desirae_via_sequence_shuffle_fuse_and_equip.md"
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
        self.assertIn("Fiendsmith's Desirae", field_names)
        self.assertNotIn("Fiendsmith's Sequence", field_names)

        equipped_totals = snapshot.get("equipped_link_totals", [])
        desirae_total = None
        for entry in equipped_totals:
            if entry.get("name") == "Fiendsmith's Desirae":
                desirae_total = entry.get("total")
                break
        self.assertIsNotNone(desirae_total)
        self.assertGreaterEqual(int(desirae_total), 2)


if __name__ == "__main__":
    unittest.main()
