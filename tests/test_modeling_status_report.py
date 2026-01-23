import subprocess
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]


class TestModelingStatusReport(unittest.TestCase):
    def test_modeling_status_report(self):
        result = subprocess.run(
            [sys.executable, str(repo_root / "scripts" / "audit_modeling_status.py")],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            self.fail(
                "Modeling status report failed.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )


if __name__ == "__main__":
    unittest.main()
