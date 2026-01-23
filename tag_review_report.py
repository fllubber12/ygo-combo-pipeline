#!/usr/bin/env python3
import runpy
from pathlib import Path

repo_root = Path(__file__).resolve().parent
runpy.run_path(str(repo_root / "scripts" / "qa" / "tag_review_report.py"), run_name="__main__")
