#!/usr/bin/env python3
"""Run all QA checks for the card library."""
import subprocess
import sys
from pathlib import Path


def run_step(name: str, args: list[str], cwd: Path) -> tuple[str, int]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    return name, result.returncode


def fail_summary(summary: list[tuple[str, str]], spot_report: Path, tag_report: Path | None) -> None:
    print("QA Summary:")
    for name, status in summary:
        print(f"- {name}: {status}")
    print(f"- spot_check_report.md: {spot_report}")
    if tag_report:
        print(f"- tag_review_report.md: {tag_report}")
    sys.exit(1)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    spot_check_script = repo_root / "scripts" / "qa" / "generate_spot_check_report.py"
    validate_script = repo_root / "scripts" / "qa" / "validate_card_tags.py"
    tag_review_script = repo_root / "scripts" / "qa" / "tag_review_report.py"
    deck_pipeline_script = repo_root / "scripts" / "deck_pipeline.py"
    spot_report_path = repo_root / "reports" / "spot_check_report.md"
    tag_report_path = repo_root / "tag_review_report.md"

    summary = []

    step_name, code = run_step(
        "Spot-check report",
        [sys.executable, str(spot_check_script)],
        repo_root,
    )
    summary.append((step_name, "PASS" if code == 0 else "FAIL"))
    if code != 0:
        fail_summary(summary, spot_report_path, None)
    if not spot_report_path.exists():
        summary[-1] = (summary[-1][0], "FAIL")
        print("FAIL: spot_check_report.md was not created.")
        fail_summary(summary, spot_report_path, None)

    step_name, code = run_step(
        "Card tags validator",
        [sys.executable, str(validate_script)],
        repo_root,
    )
    summary.append((step_name, "PASS" if code == 0 else "FAIL"))
    if code != 0:
        fail_summary(summary, spot_report_path, None)

    step_name, code = run_step(
        "Deck pipeline tests",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        repo_root,
    )
    summary.append((step_name, "PASS" if code == 0 else "FAIL"))
    if code != 0:
        fail_summary(summary, spot_report_path, None)

    fixture_deck = repo_root / "tests" / "fixtures" / "sample_deck.txt"
    fixture_context = repo_root / "tests" / "fixtures" / "format_context.json"
    step_name, code = run_step(
        "Deck pipeline demo",
        [
            sys.executable,
            str(deck_pipeline_script),
            "--input",
            str(fixture_deck),
            "--deck-name",
            "fixture_deck",
            "--format-context",
            str(fixture_context),
        ],
        repo_root,
    )
    summary.append((step_name, "PASS" if code == 0 else "FAIL"))
    if code != 0:
        fail_summary(summary, spot_report_path, None)

    step_name, code = run_step(
        "Tag review report",
        [sys.executable, str(tag_review_script)],
        repo_root,
    )
    summary.append((step_name, "PASS" if code == 0 else "FAIL"))
    if code != 0:
        fail_summary(summary, spot_report_path, tag_report_path)

    print("QA Summary:")
    for name, status in summary:
        print(f"- {name}: {status}")
    print(f"- spot_check_report.md: {spot_report_path}")
    print(f"- tag_review_report.md: {tag_report_path}")


if __name__ == "__main__":
    main()
