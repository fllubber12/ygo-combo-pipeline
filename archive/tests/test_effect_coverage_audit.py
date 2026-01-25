import subprocess
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]


class TestEffectCoverageAudit(unittest.TestCase):
    def test_effect_coverage_audit(self):
        result = subprocess.run(
            [sys.executable, str(repo_root / "scripts" / "audit_effect_coverage.py")],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            self.fail(
                "Effect coverage audit failed.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )


if __name__ == "__main__":
    unittest.main()
