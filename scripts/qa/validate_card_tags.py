#!/usr/bin/env python3
"""Fail-closed validator for card_tags.* against the CLEAN library."""
import json
import re
import sys
from pathlib import Path

import pandas as pd

PSCT_KEYWORDS = [
    "you can",
    "you cannot",
    "if",
    "when",
    "during",
    "target",
    "special summon",
    "destroy",
    "banish",
    "draw",
    "discard",
    "activate",
    "once per turn",
]


def normalize_cid(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    text = re.sub(r"\.0$", "", text)
    return text


def split_values(value: object, delimiters: list[str]) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    pattern = "[" + re.escape("".join(delimiters)) + "]"
    parts = re.split(pattern, text)
    return [part.strip() for part in parts if part.strip()]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def cell_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_name(name: str) -> str:
    name = name.strip()
    name = name.replace("\u2019", "'")
    name = name.replace("\u2010", "-")
    name = name.replace("\u2011", "-")
    name = name.replace("\u2013", "-")
    return name


def load_schema(schema_path: Path) -> dict:
    if not schema_path.exists():
        print(f"FAIL: Missing schema file at {schema_path}")
        sys.exit(1)
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def looks_like_psct(value: str, card_text: str) -> bool:
    if not value:
        return False
    norm_value = normalize_text(value)
    if len(norm_value) < 40:
        return False

    keyword_hits = sum(1 for kw in PSCT_KEYWORDS if kw in norm_value)
    if keyword_hits >= 2:
        return True

    norm_card = normalize_text(card_text) if card_text else ""
    if norm_card and (norm_value in norm_card or norm_card in norm_value):
        return True

    return False


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "config" / "card_tags_schema.json"
    schema = load_schema(schema_path)

    clean_path = repo_root / "data_processed" / "Fiendsmith_Master_Card_Library_CLEAN.xlsx"
    tags_xlsx = repo_root / "card_tags.xlsx"
    tags_jsonl = repo_root / "card_tags.jsonl"

    required_files = schema.get("required_files", [])
    for filename in required_files:
        path = repo_root / filename
        if not path.exists():
            print(f"FAIL: Missing required file {filename}")
            sys.exit(1)

    if not clean_path.exists():
        print(f"FAIL: Missing CLEAN library at {clean_path}")
        sys.exit(1)

    clean_df = pd.read_excel(clean_path)
    tags_df = pd.read_excel(tags_xlsx)

    clean_cid_to_name = {}
    clean_cid_to_text = {}
    for _, row in clean_df.iterrows():
        cid = normalize_cid(row.get("CID"))
        if cid:
            clean_cid_to_name[cid] = str(row.get("Name (Official formatting)", "")).strip()
            clean_cid_to_text[cid] = str(row.get("Official Card Text (Exact, TCG)", "")).strip()

    issues = []

    def add_issue(message: str) -> None:
        issues.append(message)

    required_columns = [col["name"] for col in schema.get("columns", []) if col.get("required")]
    required_values = {
        col["name"]
        for col in schema.get("columns", [])
        if col.get("required_value")
    }
    for col in required_columns:
        if col not in tags_df.columns:
            add_issue(f"Missing required column in card_tags.xlsx: {col}")

    vocab = schema.get("vocab", {})
    vocab_lower = {key: {v.lower() for v in values} for key, values in vocab.items()}
    multi_value_delimiters = schema.get("multi_value_delimiters", [";"])

    column_specs = {col["name"]: col for col in schema.get("columns", [])}
    tag_fields = [
        col["name"]
        for col in schema.get("columns", [])
        if col.get("psct_check")
    ]

    seen_cids = set()
    for idx, row in tags_df.iterrows():
        row_num = idx + 2
        cid = normalize_cid(row.get("CID"))
        name = cell_text(row.get("Name (Official formatting)", ""))

        if not cid:
            add_issue(f"Row {row_num}: CID is missing")
            continue
        if cid in seen_cids:
            add_issue(f"Row {row_num}: Duplicate CID {cid} in card_tags.xlsx")
        seen_cids.add(cid)

        if cid not in clean_cid_to_name:
            add_issue(f"Row {row_num}: CID {cid} not found in CLEAN library")
        else:
            official_name = clean_cid_to_name[cid]
            if not name:
                add_issue(f"Row {row_num}: Name missing for CID {cid}")
            elif normalize_name(name) != normalize_name(official_name):
                add_issue(
                    f"Row {row_num}: Name mismatch for CID {cid} (tags: '{name}' vs CLEAN: '{official_name}')"
                )

        for field_name, spec in column_specs.items():
            if field_name in ("CID", "Name (Official formatting)"):
                continue
            field_value = cell_text(row.get(field_name, ""))
            vocab_key = spec.get("vocab")
            if not field_value or not vocab_key:
                continue
            values = (
                split_values(field_value, multi_value_delimiters)
                if spec.get("multi_value")
                else [field_value]
            )
            allowed = vocab_lower.get(vocab_key, set())
            for value in values:
                if value.lower() not in allowed:
                    display = vocab.get(vocab_key, [])
                    add_issue(
                        f"Row {row_num}: {field_name} '{value}' not in allowed vocabulary ({display})"
                    )

        card_text = clean_cid_to_text.get(cid, "")
        for field in tag_fields:
            field_value = cell_text(row.get(field, ""))
            if looks_like_psct(field_value, card_text):
                add_issue(
                    f"Row {row_num}: Possible PSCT leakage in '{field}' for CID {cid}"
                )

    # Cross-format equivalence check
    json_cids = []
    json_required = required_columns
    with tags_jsonl.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                add_issue(f"JSONL line {line_num}: invalid JSON ({exc})")
                continue
            for field in json_required:
                if field not in obj:
                    add_issue(f"JSONL line {line_num}: Missing required field '{field}'")
                elif field in required_values and obj.get(field) in (None, ""):
                    add_issue(f"JSONL line {line_num}: Missing required value for '{field}'")
            cid = normalize_cid(obj.get("CID", ""))
            if not cid:
                add_issue(f"JSONL line {line_num}: CID missing")
            json_cids.append(cid)

    json_cid_set = {cid for cid in json_cids if cid}
    if len(json_cids) != len(json_cid_set):
        add_issue("JSONL: Duplicate CID detected")

    xlsx_cids = [normalize_cid(cid) for cid in tags_df.get("CID", [])]
    xlsx_cid_list = [cid for cid in xlsx_cids if cid]
    xlsx_cid_set = set(xlsx_cid_list)

    if json_cid_set != xlsx_cid_set:
        missing_in_json = sorted(xlsx_cid_set - json_cid_set)
        missing_in_xlsx = sorted(json_cid_set - xlsx_cid_set)
        if missing_in_json:
            add_issue(f"JSONL missing CIDs present in XLSX: {missing_in_json}")
        if missing_in_xlsx:
            add_issue(f"XLSX missing CIDs present in JSONL: {missing_in_xlsx}")

    if xlsx_cid_list != json_cids:
        add_issue("JSONL CID order does not match XLSX row order")

    if issues:
        print("Card Tags Validator: FAIL")
        for issue in issues:
            print(f"- {issue}")
        print(f"Schema: {schema_path}")
        sys.exit(1)

    print("Card Tags Validator: PASS")
    print(f"Schema: {schema_path}")


if __name__ == "__main__":
    main()
