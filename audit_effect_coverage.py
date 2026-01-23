#!/usr/bin/env python3
"""Repo-root wrapper so `python3 audit_effect_coverage.py` works."""
from __future__ import annotations

import runpy
from pathlib import Path

repo_root = Path(__file__).resolve().parent
runpy.run_path(str(repo_root / "scripts" / "audit_effect_coverage.py"), run_name="__main__")
