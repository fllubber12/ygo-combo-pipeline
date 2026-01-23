#!/usr/bin/env python3
"""Generate a tag review report to guide manual curation."""
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


def cell_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def split_values(value: str, delimiters: list[str]) -> list[str]:
    text = value.strip()
    if not text:
        return []
    pattern = "[" + re.escape("".join(delimiters)) + "]"
    parts = re.split(pattern, text)
    return [part.strip() for part in parts if part.strip()]


def normalize_values(value: str, delimiters: list[str]) -> list[str]:
    return sorted({part.lower() for part in split_values(value, delimiters)})


def load_schema(schema_path: Path) -> dict:
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(jsonl_path: Path) -> list[dict]:
    rows = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def truthy_needs_review(value: str) -> bool:
    if not value:
        return False
    return value.strip().upper() == "TRUE"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "config" / "card_tags_schema.json"
    tags_path = repo_root / "card_tags.xlsx"
    jsonl_path = repo_root / "card_tags.jsonl"
    report_path = repo_root / "tag_review_report.md"

    schema = load_schema(schema_path)
    delimiters = schema.get("multi_value_delimiters", [";"])

    tags_df = pd.read_excel(tags_path)
    _ = load_jsonl(jsonl_path)

    final_fields = {
        "Role": "Role_Suggested",
        "OPT": "OPT_Suggested",
        "Primary Actions": "PrimaryActions_Suggested",
    }

    rows_total = len(tags_df)
    rows_needs_review = 0
    rows_final_blank_suggested_present = 0
    rows_final_differs = 0

    highest_priority = []
    disagreements = []
    notes_rows = []

    for _, row in tags_df.iterrows():
        cid = normalize_cid(row.get("CID"))
        name = cell_text(row.get("Name (Official formatting)"))

        needs_review = truthy_needs_review(cell_text(row.get("NeedsReview")))
        if needs_review:
            rows_needs_review += 1

        final_blank_any = False
        suggested_present_any = False
        differs_any = False

        final_blank_all = True

        for final_field, suggested_field in final_fields.items():
            final_value = cell_text(row.get(final_field))
            suggested_value = cell_text(row.get(suggested_field))

            if final_value:
                final_blank_all = False
            else:
                final_blank_any = True
            if suggested_value:
                suggested_present_any = True

            if final_value and suggested_value:
                if final_field == "OPT":
                    differs = final_value.strip().lower() != suggested_value.strip().lower()
                else:
                    final_norm = normalize_values(final_value, delimiters)
                    sugg_norm = normalize_values(suggested_value, delimiters)
                    differs = final_norm != sugg_norm
                if differs:
                    differs_any = True

        if final_blank_any and suggested_present_any:
            rows_final_blank_suggested_present += 1
        if differs_any:
            rows_final_differs += 1

        if final_blank_all:
            highest_priority.append(
                {
                    "CID": cid,
                    "Name": name,
                    "Role_Suggested": cell_text(row.get("Role_Suggested")),
                    "OPT_Suggested": cell_text(row.get("OPT_Suggested")),
                    "PrimaryActions_Suggested": cell_text(row.get("PrimaryActions_Suggested")),
                }
            )

        if differs_any:
            disagreements.append(
                {
                    "CID": cid,
                    "Name": name,
                    "Role": cell_text(row.get("Role")),
                    "Role_Suggested": cell_text(row.get("Role_Suggested")),
                    "OPT": cell_text(row.get("OPT")),
                    "OPT_Suggested": cell_text(row.get("OPT_Suggested")),
                    "Primary Actions": cell_text(row.get("Primary Actions")),
                    "PrimaryActions_Suggested": cell_text(row.get("PrimaryActions_Suggested")),
                }
            )

        notes = cell_text(row.get("Combo Relevance Notes"))
        if notes:
            notes_rows.append(
                {
                    "CID": cid,
                    "Name": name,
                    "Combo Relevance Notes": notes,
                }
            )

    lines = []
    lines.append("# Tag Review Report")
    lines.append("")
    lines.append("## 1) Summary counts")
    lines.append(f"- total rows: {rows_total}")
    lines.append(f"- rows with NeedsReview=TRUE: {rows_needs_review}")
    lines.append(
        "- rows where any Final field is empty but Suggested is present: "
        f"{rows_final_blank_suggested_present}"
    )
    lines.append(
        "- rows where Final differs from Suggested: "
        f"{rows_final_differs}"
    )
    lines.append("")

    lines.append("## 2) Highest priority to fill next")
    lines.append("| CID | Name | Role_Suggested | OPT_Suggested | PrimaryActions_Suggested |")
    lines.append("| --- | --- | --- | --- | --- |")
    if highest_priority:
        for row in highest_priority:
            lines.append(
                f"| {row['CID']} | {row['Name']} | {row['Role_Suggested']} | "
                f"{row['OPT_Suggested']} | {row['PrimaryActions_Suggested']} |"
            )
    lines.append("")

    lines.append("## 3) Potential disagreements")
    lines.append("| CID | Name | Role (Final) | Role_Suggested | OPT (Final) | OPT_Suggested | Primary Actions (Final) | PrimaryActions_Suggested |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    if disagreements:
        for row in disagreements:
            lines.append(
                f"| {row['CID']} | {row['Name']} | {row['Role']} | "
                f"{row['Role_Suggested']} | {row['OPT']} | {row['OPT_Suggested']} | "
                f"{row['Primary Actions']} | {row['PrimaryActions_Suggested']} |"
            )
    lines.append("")

    lines.append("## 4) Validator-risk warnings")
    if notes_rows:
        lines.append("The following rows contain Combo Relevance Notes and should be reviewed for PSCT leakage:")
        lines.append("")
        lines.append("| CID | Name | Combo Relevance Notes |")
        lines.append("| --- | --- | --- |")
        for row in notes_rows:
            lines.append(f"| {row['CID']} | {row['Name']} | {row['Combo Relevance Notes']} |")
    else:
        lines.append("No rows contain Combo Relevance Notes.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Tag Review Report: Wrote {report_path}")


if __name__ == "__main__":
    main()
