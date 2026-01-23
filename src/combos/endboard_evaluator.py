#!/usr/bin/env python3
"""Endboard evaluator using bucket-only definitions."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def normalize_name(name: str) -> str:
    value = name.strip()
    value = value.replace("\u2019", "'")
    value = value.replace("\u2010", "-")
    value = value.replace("\u2011", "-")
    value = value.replace("\u2013", "-")
    value = re.sub(r"\s+", " ", value)
    return value.lower()


def load_buckets(config_path: Path) -> list[dict[str, Any]]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Bucket config must be a list.")
    return data


def snapshot_zone(snapshot: dict[str, Any], zone: str) -> list[str]:
    zones = snapshot.get("zones", {})
    values = zones.get(zone, []) if isinstance(zones, dict) else []
    return [str(v) for v in values]


def is_card_in_zone(snapshot: dict[str, Any], zone: str, names: list[str]) -> bool:
    zone_values = snapshot_zone(snapshot, zone)
    normalized_zone = {normalize_name(value) for value in zone_values}
    return any(normalize_name(name) in normalized_zone for name in names)


def evaluate_endboard(snapshot: dict[str, Any], config_path: Path | None = None) -> dict[str, Any]:
    """Evaluate endboard buckets against a snapshot.

    StateSnapshot contract:
      - snapshot['zones'] is a dict with keys: hand, field, gy, banished, deck, extra
      - each zone is a list of card names or CIDs
    """
    if config_path is None:
        repo_root = Path(__file__).resolve().parents[2]
        config_path = repo_root / "config" / "endboard_piece_buckets.json"

    buckets = load_buckets(config_path)
    achieved = []

    for entry in buckets:
        kind = entry.get("kind")
        name = entry.get("name", "")
        aliases = entry.get("aliases", [])
        bucket = entry.get("bucket")
        notes = entry.get("notes", "")

        if not kind or not name or not bucket:
            continue

        names = [name] + aliases
        source_zone = None
        matched = False

        if kind == "card":
            if is_card_in_zone(snapshot, "field", names):
                matched = True
                source_zone = "field"
        elif kind == "condition":
            if name.lower().endswith(" in gy"):
                condition_name = name[:-6].strip()
                if is_card_in_zone(snapshot, "gy", [condition_name] + aliases):
                    matched = True
                    source_zone = "gy"

        if matched:
            achieved.append(
                {
                    "kind": kind,
                    "name": name,
                    "bucket": bucket,
                    "zone": source_zone,
                    "notes": notes,
                }
            )

    equipped_totals = snapshot.get("equipped_link_totals", [])
    for entry in equipped_totals:
        if normalize_name(entry.get("name", "")) == normalize_name("Fiendsmith's Desirae"):
            if int(entry.get("total", 0)) >= 1:
                achieved.append(
                    {
                        "kind": "condition",
                        "name": "Desirae equipped link",
                        "bucket": "S",
                        "zone": "field",
                        "notes": "Desirae with equipped Link rating",
                    }
                )
                break

    count_s = sum(1 for item in achieved if item["bucket"] == "S")
    count_a = sum(1 for item in achieved if item["bucket"] == "A")
    count_b = sum(1 for item in achieved if item["bucket"] == "B")

    summary = f"S={count_s} A={count_a} B={count_b}"

    achieved_sorted = sorted(
        achieved,
        key=lambda x: (x["bucket"], x["name"].lower()),
    )

    return {
        "achieved": achieved_sorted,
        "rank_key": (count_s, count_a, count_b),
        "summary": summary,
    }
