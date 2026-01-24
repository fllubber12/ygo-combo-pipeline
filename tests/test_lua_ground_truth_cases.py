import os
import sys
import subprocess
import unittest


class TestLuaGroundTruthCases(unittest.TestCase):
    @unittest.skipIf(
        not os.environ.get("YGOPRO_SCRIPT_DIR"),
        "YGOPRO_SCRIPT_DIR not set; skipping Lua ground truth cases test.",
    )
    def test_lua_ground_truth_cases_match_python(self):
        cmd = [
            sys.executable,
            "scripts/lua_ground_truth.py",
            "--cases",
            "config/lua_ground_truth_cases.json",
            "--verify-hooks",
            "--verify-activation",
            "--ci",
        ]
        # preserve env; rely on YGOPRO_SCRIPT_DIR existing
        env = dict(os.environ)

        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        if p.returncode != 0:
            # Show full output on failure for fast debugging in CI/local runs
            msg = (
                "Lua ground truth cases mismatch / failure.\n"
                "STDOUT:\n" + (p.stdout or "") + "\n"
                "STDERR:\n" + (p.stderr or "") + "\n"
            )
            self.fail(msg)


if __name__ == "__main__":
    unittest.main()
