#!/usr/bin/env python3
"""Decklist ingest, normalize, and profile generation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class CardRecord:
    cid: str
    name: str
    card_type: str


class DeckResolutionError(Exception):
    def __init__(self, unresolved: list[dict[str, Any]]):
        super().__init__("Deck contains unresolved card references.")
        self.unresolved = unresolved


def normalize_name(name: str) -> str:
    name = name.strip()
    name = name.replace("\u2019", "'")
    name = name.replace("\u2010", "-")
    name = name.replace("\u2011", "-")
    name = name.replace("\u2013", "-")
    name = re.sub(r"\s+", " ", name)
    return name


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def parse_ydk(text: str) -> dict[str, dict[str, int]]:
    sections = {"main": {}, "extra": {}, "side": {}}
    current = "main"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower == "#main":
            current = "main"
            continue
        if lower == "#extra":
            current = "extra"
            continue
        if lower.startswith("!side"):
            current = "side"
            continue
        if lower.startswith("#"):
            continue
        sections[current][line] = sections[current].get(line, 0) + 1
    return sections


def parse_plain_text(text: str) -> dict[str, dict[str, int]]:
    sections = {"main": {}, "extra": {}, "side": {}}
    current = "main"

    def set_section(value: str) -> bool:
        nonlocal current
        lower = value.lower()
        if lower in {"main", "main deck", "maindeck", "deck", "main:"}:
            current = "main"
            return True
        if lower in {"extra", "extra deck", "extradeck", "extra:"}:
            current = "extra"
            return True
        if lower in {"side", "side deck", "sidedeck", "side:"}:
            current = "side"
            return True
        return False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("//"):
            continue
        if set_section(line):
            continue

        count = 1
        name = line

        match = re.match(r"^(\d+)\s*[xX]?\s+(.+)$", line)
        if match:
            count = int(match.group(1))
            name = match.group(2)
        else:
            match = re.match(r"^[xX](\d+)\s+(.+)$", line)
            if match:
                count = int(match.group(1))
                name = match.group(2)
            else:
                match = re.match(r"^(.+?)\s+[xX](\d+)$", line)
                if match:
                    name = match.group(1)
                    count = int(match.group(2))
                else:
                    match = re.match(r"^(.+?)\s+(\d+)$", line)
                    if match:
                        name = match.group(1)
                        count = int(match.group(2))

        name = name.strip()
        if not name:
            continue
        sections[current][name] = sections[current].get(name, 0) + count

    return sections


def parse_deck_file(path: Path) -> tuple[str, dict[str, dict[str, int]]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".ydk":
        return "ydk", parse_ydk(text)
    return "plain_text", parse_plain_text(text)


def load_card_library(clean_xlsx: Path) -> dict[str, Any]:
    df = pd.read_excel(clean_xlsx)
    by_cid: dict[str, CardRecord] = {}
    by_norm_name: dict[str, list[CardRecord]] = {}
    by_lower_name: dict[str, list[CardRecord]] = {}
    all_records: list[CardRecord] = []

    for _, row in df.iterrows():
        cid_value = row.get("CID")
        if pd.isna(cid_value):
            continue
        cid = str(int(cid_value))
        name = str(row.get("Name (Official formatting)", "")).strip()
        card_type = str(row.get("Card Type (Monster / Spell / Trap)", "")).strip()
        if not cid or not name:
            continue
        record = CardRecord(cid=cid, name=name, card_type=card_type)
        by_cid[cid] = record
        norm = normalize_name(name)
        by_norm_name.setdefault(norm, []).append(record)
        by_lower_name.setdefault(norm.lower(), []).append(record)
        all_records.append(record)

    return {
        "by_cid": by_cid,
        "by_norm_name": by_norm_name,
        "by_lower_name": by_lower_name,
        "records": all_records,
    }


def find_name_candidates(name: str, library: dict[str, Any], limit: int = 5) -> list[dict[str, str]]:
    norm = normalize_name(name).lower()
    matches = []
    for record in library["records"]:
        rec_norm = normalize_name(record.name).lower()
        if norm and (norm in rec_norm or rec_norm in norm):
            matches.append({"cid": record.cid, "name": record.name})
            if len(matches) >= limit:
                break
    return matches


def resolve_identifier(identifier: str, library: dict[str, Any]) -> tuple[CardRecord | None, list[dict[str, str]]]:
    if identifier.isdigit():
        record = library["by_cid"].get(identifier)
        if record:
            return record, []
        return None, []

    norm = normalize_name(identifier)
    candidates = library["by_norm_name"].get(norm, [])
    if len(candidates) == 1:
        return candidates[0], []
    if len(candidates) > 1:
        return None, [{"cid": c.cid, "name": c.name} for c in candidates]

    candidates = library["by_lower_name"].get(norm.lower(), [])
    if len(candidates) == 1:
        return candidates[0], []
    if len(candidates) > 1:
        return None, [{"cid": c.cid, "name": c.name} for c in candidates]

    return None, find_name_candidates(identifier, library)


def normalize_deck(
    deck_name: str,
    format_context: dict[str, Any],
    parsed: dict[str, dict[str, int]],
    library: dict[str, Any],
) -> dict[str, Any]:
    resolved = {"main": {}, "extra": {}, "side": {}}
    unresolved: list[dict[str, Any]] = []

    for section, entries in parsed.items():
        for identifier, count in entries.items():
            record, candidates = resolve_identifier(identifier, library)
            if record is None:
                unresolved.append(
                    {
                        "section": section,
                        "input": identifier,
                        "count": count,
                        "candidates": candidates,
                    }
                )
                continue
            resolved[section][record.cid] = resolved[section].get(record.cid, 0) + count

    if unresolved:
        raise DeckResolutionError(unresolved)

    def build_section(section: str) -> list[dict[str, Any]]:
        items = []
        for cid, count in resolved[section].items():
            record = library["by_cid"][cid]
            items.append({"cid": cid, "name": record.name, "count": count})
        items.sort(key=lambda x: (x["name"].lower(), x["cid"]))
        return items

    return {
        "deck_name": deck_name,
        "format_context": format_context,
        "main": build_section("main"),
        "extra": build_section("extra"),
        "side": build_section("side"),
        "unresolved": [],
    }


def build_manifest(
    deck_name: str,
    input_path: Path,
    deck_format: str,
    parsed: dict[str, dict[str, int]],
) -> dict[str, Any]:
    return {
        "deck_name": deck_name,
        "input_file": str(input_path),
        "input_sha256": sha256_file(input_path),
        "format": deck_format,
        "parsed_counts": {
            "main": sum(parsed["main"].values()),
            "extra": sum(parsed["extra"].values()),
            "side": sum(parsed["side"].values()),
        },
        "created_at": datetime.utcnow().isoformat() + "Z",
    }


def write_manifest(manifest: dict[str, Any], raw_dir: Path, input_path: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.copy2(input_path, raw_dir / input_path.name)


def write_deck_json(deck: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(deck, indent=2), encoding="utf-8")


def generate_deck_profile(
    deck: dict[str, Any],
    library: dict[str, Any],
    clean_xlsx: Path,
    deck_json_path: Path,
    report_path: Path,
    repo_root: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    main_total = sum(card["count"] for card in deck["main"])
    extra_total = sum(card["count"] for card in deck["extra"])
    side_total = sum(card["count"] for card in deck["side"])

    type_counts = {"Monster": 0, "Spell": 0, "Trap": 0, "Unknown": 0}
    for card in deck["main"]:
        record = library["by_cid"].get(card["cid"])
        card_type = record.card_type if record else "Unknown"
        if card_type not in type_counts:
            card_type = "Unknown"
        type_counts[card_type] += card["count"]

    all_cards = deck["main"] + deck["extra"] + deck["side"]
    top_cards = sorted(all_cards, key=lambda x: (-x["count"], x["name"].lower()))[:10]

    card_library_hash = sha256_file(clean_xlsx)
    deck_hash = sha256_file(deck_json_path)
    git_commit = get_git_commit(repo_root)

    lines = []
    lines.append(f"# Deck Profile: {deck['deck_name']}")
    lines.append("")
    lines.append("## Section Counts")
    lines.append(f"- Main: {main_total}")
    lines.append(f"- Extra: {extra_total}")
    lines.append(f"- Side: {side_total}")
    lines.append("")
    lines.append("## Main Deck Type Counts")
    lines.append(f"- Monster: {type_counts['Monster']}")
    lines.append(f"- Spell: {type_counts['Spell']}")
    lines.append(f"- Trap: {type_counts['Trap']}")
    lines.append(f"- Unknown: {type_counts['Unknown']}")
    lines.append("")
    lines.append("## Top 10 Most Numerous Cards")
    lines.append("| Count | CID | Name |")
    lines.append("| --- | --- | --- |")
    for card in top_cards:
        lines.append(f"| {card['count']} | {card['cid']} | {card['name']} |")
    lines.append("")
    lines.append("---")
    lines.append("Dataset versions:")
    lines.append(f"- card_library_sha256: {card_library_hash}")
    lines.append(f"- deck_json_sha256: {deck_hash}")
    lines.append(f"- git_commit: {git_commit}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_format_context(value: str | None, deck_name: str) -> dict[str, Any]:
    if not value:
        return {
            "game": "TCG",
            "banlist_id": "unknown",
            "banlist_date": "unknown",
            "rules": "unknown",
            "deck_name": deck_name,
        }
    path = Path(value)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Ingest, normalize, and profile a decklist.")
    parser.add_argument("--input", required=True, help="Path to decklist file (.ydk or .txt).")
    parser.add_argument("--deck-name", default=None, help="Deck name for outputs.")
    parser.add_argument(
        "--format-context",
        default=None,
        help="JSON string or path to JSON file describing format context.",
    )
    parser.add_argument(
        "--card-library",
        default=str(repo_root / "data_processed" / "Fiendsmith_Master_Card_Library_CLEAN.xlsx"),
        help="Path to the clean card library XLSX.",
    )
    parser.add_argument(
        "--raw-dir",
        default=str(repo_root / "data_raw"),
        help="Base directory for raw ingest outputs.",
    )
    parser.add_argument(
        "--processed-dir",
        default=str(repo_root / "data_processed" / "decks"),
        help="Directory for normalized deck JSON outputs.",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(repo_root / "reports"),
        help="Directory for deck profile reports.",
    )
    return parser.parse_args()


def run_pipeline(args: argparse.Namespace) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = Path(args.input)
    deck_name = args.deck_name or input_path.stem
    format_context = parse_format_context(args.format_context, deck_name)

    clean_path = Path(args.card_library)
    if not clean_path.exists():
        raise SystemExit(f"Missing card library at {clean_path}")
    if not input_path.exists():
        raise SystemExit(f"Missing decklist at {input_path}")

    deck_format, parsed = parse_deck_file(input_path)
    manifest = build_manifest(deck_name, input_path, deck_format, parsed)
    raw_dir = Path(args.raw_dir) / deck_name
    write_manifest(manifest, raw_dir, input_path)

    library = load_card_library(clean_path)
    try:
        deck = normalize_deck(deck_name, format_context, parsed, library)
    except DeckResolutionError as exc:
        lines = ["Unresolved card references:"]
        for item in exc.unresolved:
            line = f"- {item['section']}: '{item['input']}' x{item['count']}"
            if item["candidates"]:
                candidates = ", ".join(
                    f"{c['cid']}:{c['name']}" for c in item["candidates"]
                )
                line += f" | candidates: {candidates}"
            lines.append(line)
        raise SystemExit("\n".join(lines))

    deck_json_path = Path(args.processed_dir) / f"{deck_name}.json"
    write_deck_json(deck, deck_json_path)

    report_path = Path(args.reports_dir) / f"deck_profile_{deck_name}.md"
    generate_deck_profile(deck, library, clean_path, deck_json_path, report_path, repo_root)

    print(f"Deck pipeline: PASS | deck={deck_name} | format={deck_format}")
    print(f"- manifest: {raw_dir / 'manifest.json'}")
    print(f"- deck_json: {deck_json_path}")
    print(f"- report: {report_path}")


def main() -> None:
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
