#!/usr/bin/env python3
"""Suggest initial card_tags fields from PSCT without writing PSCT into tags."""
import json
import re
from pathlib import Path

import pandas as pd


def normalize_cid(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return re.sub(r"\.0$", "", text)


def load_schema(schema_path: Path) -> dict:
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def detect_opt(text: str) -> str:
    lowered = text.lower()
    if "you can only use 1" in lowered:
        return "Hard OPT"
    if "you can only use this effect of" in lowered:
        return "Hard OPT"
    if "you can only use each effect of" in lowered:
        return "Hard OPT"
    if "once per turn" in lowered:
        return "Soft OPT"
    return "None"


def detect_primary_actions(text: str) -> list[str]:
    lowered = text.lower()
    actions = []

    if "add 1" in lowered and "from your deck to your hand" in lowered:
        actions.extend(["Search", "Add-to-hand"])
    if "special summon" in lowered:
        actions.append("Special Summon")
    if "send" in lowered and "to the gy" in lowered:
        actions.append("Send-to-GY")
    if "draw" in lowered:
        actions.append("Draw")
    if "negate" in lowered:
        actions.append("Negate")
    if "destroy" in lowered:
        actions.append("Destroy")
    if "banish" in lowered:
        actions.append("Banish")
    if "return" in lowered and "to the hand" in lowered:
        actions.append("Bounce")

    seen = set()
    ordered = []
    for action in actions:
        if action not in seen:
            seen.add(action)
            ordered.append(action)
    return ordered


def detect_role(text: str) -> list[str]:
    lowered = text.lower()
    roles = []

    if "add 1" in lowered and "from your deck to your hand" in lowered:
        roles.append("Searcher")

    self_ss = "special summon this card" in lowered
    from_zones = any(
        phrase in lowered
        for phrase in ["from your hand", "from your gy", "from your deck"]
    )
    if self_ss and from_zones:
        roles.append("Extender")

    seen = set()
    ordered = []
    for role in roles:
        if role not in seen:
            seen.add(role)
            ordered.append(role)
    return ordered


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "config" / "card_tags_schema.json"
    clean_path = repo_root / "data_processed" / "Fiendsmith_Master_Card_Library_CLEAN.xlsx"
    tags_path = repo_root / "card_tags.xlsx"
    jsonl_path = repo_root / "card_tags.jsonl"

    schema = load_schema(schema_path)
    columns = [col["name"] for col in schema.get("columns", [])]

    clean_df = pd.read_excel(clean_path)
    tags_df = pd.read_excel(tags_path)
    # Normalize dtypes for columns we mutate to avoid pandas FutureWarnings
    for col in [
        "Role_Suggested",
        "OPT_Suggested",
        "PrimaryActions_Suggested",
        "Locks_Suggested",
        "NeedsReview",
    ]:
        if col in tags_df.columns:
            tags_df[col] = tags_df[col].astype("string")

    clean_text = {}
    for _, row in clean_df.iterrows():
        cid = normalize_cid(row.get("CID"))
        if cid:
            clean_text[cid] = str(row.get("Official Card Text (Exact, TCG)", ""))

    # Ensure all schema columns exist
    for col in columns:
        if col not in tags_df.columns:
            tags_df[col] = ""

    for idx, row in tags_df.iterrows():
        cid = normalize_cid(row.get("CID"))
        if not cid:
            continue
        text = clean_text.get(cid, "")

        role_s = row.get("Role_Suggested", "")
        opt_s = row.get("OPT_Suggested", "")
        primary_s = row.get("PrimaryActions_Suggested", "")
        locks_s = row.get("Locks_Suggested", "")

        if not isinstance(role_s, str):
            role_s = ""
        if not isinstance(opt_s, str):
            opt_s = ""
        if not isinstance(primary_s, str):
            primary_s = ""
        if not isinstance(locks_s, str):
            locks_s = ""

        if not role_s.strip():
            roles = detect_role(text)
            if roles:
                tags_df.at[idx, "Role_Suggested"] = "; ".join(roles)

        if not opt_s.strip():
            tags_df.at[idx, "OPT_Suggested"] = detect_opt(text)

        if not primary_s.strip():
            actions = detect_primary_actions(text)
            if actions:
                tags_df.at[idx, "PrimaryActions_Suggested"] = "; ".join(actions)

        if not locks_s.strip():
            tags_df.at[idx, "Locks_Suggested"] = ""

        needs_review = False
        for col_name in [
            "Role_Suggested",
            "OPT_Suggested",
            "PrimaryActions_Suggested",
            "Locks_Suggested",
        ]:
            value = tags_df.at[idx, col_name]
            if isinstance(value, str) and value.strip():
                needs_review = True
                break

        tags_df.at[idx, "NeedsReview"] = "TRUE" if needs_review else "FALSE"

    # Reorder columns using schema order, keeping any extras at the end
    extras = [col for col in tags_df.columns if col not in columns]
    ordered_cols = columns + extras
    tags_df = tags_df[ordered_cols]

    tags_df.to_excel(tags_path, index=False)

    with jsonl_path.open("w", encoding="utf-8") as f:
        for _, record in tags_df.iterrows():
            obj = {col: ("" if pd.isna(record[col]) else record[col]) for col in ordered_cols}
            f.write(json.dumps(obj, ensure_ascii=True) + "\n")


if __name__ == "__main__":
    main()
