#!/usr/bin/env python3
"""CLI entrypoint for decklist ingest + normalize + profile."""
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from decklist_pipeline import main  # noqa: E402


if __name__ == "__main__":
    main()
