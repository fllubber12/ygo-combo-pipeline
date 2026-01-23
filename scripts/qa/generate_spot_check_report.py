#!/usr/bin/env python3
import argparse
import difflib
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.db.yugioh-card.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

ATTRIBUTES = {"LIGHT", "DARK", "EARTH", "FIRE", "WATER", "WIND", "DIVINE"}
EXTRA_DECK_TYPES = {"Fusion", "Synchro", "Xyz", "Link"}
DEFAULT_CARDS = [
    "Fiendsmith's Tract",
    "Cross-Sheep",
    "S:P Little Knight",
    "D/D/D Wave High King Caesar",
    "Evilswarm Exciton Knight",
    "Snake-Eyes Doomed Dragon",
    "Mutiny in the Sky",
    "Buio the Dawn's Light",
    "Luce the Dusk's Dark",
]


def normalize_name(name: str) -> str:
    name = name.strip()
    name = name.replace("\u2019", "'")
    name = name.replace("\u2010", "-")
    name = name.replace("\u2011", "-")
    name = name.replace("\u2013", "-")
    return name


def load_cached_html(cid: str, cache_dir: Path) -> str | None:
    cache_path = cache_dir / f"card_{cid}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    return None


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_card_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for block in soup.select("div.CardText"):
        if block.select_one(".item_box_text"):
            item_box_text = block.select_one(".item_box_text")
            raw = item_box_text.get_text("\n", strip=True) if item_box_text else ""
            lines = [line.strip() for line in raw.split("\n") if line.strip()]
            if lines and lines[0].lower() == "card text":
                lines = lines[1:]
            return "\n".join(lines)
    return ""


def extract_spec_block(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    spec_block = None
    for block in soup.select("div.CardText"):
        if block.select_one(".item_box_text"):
            continue
        classes = block.get("class") or []
        if "CardLanguage" in classes:
            continue
        spec_block = block
        break

    card_type = ""
    subtype_icon = ""
    attribute = ""
    monster_typing = ""
    level_rank_link = ""
    atk = ""
    defense = ""

    if spec_block:
        icon_value = None
        for item in spec_block.select(".item_box"):
            title_tag = item.select_one(".item_box_title")
            value_tag = item.select_one(".item_box_value")
            title_text = title_tag.get_text(strip=True) if title_tag else ""
            value_text = value_tag.get_text(strip=True) if value_tag else ""

            if title_text == "Icon":
                icon_value = value_text
            elif title_text == "ATK":
                atk = value_text
            elif title_text == "DEF":
                defense = value_text
            elif value_text in ATTRIBUTES:
                attribute = value_text
            elif value_text.startswith("Level ") or value_text.startswith("Rank ") or value_text.startswith("Link "):
                level_rank_link = value_text

        species = spec_block.select_one("p.species")
        if species:
            typing_text = species.get_text(" ", strip=True)
            typing_text = typing_text.replace("\uFF0F", "/")
            typing_text = re.sub(r"\s*/\s*", " / ", typing_text)
            monster_typing = typing_text

        if icon_value:
            subtype_icon = icon_value
            if "Spell" in icon_value:
                card_type = "Spell"
            elif "Trap" in icon_value:
                card_type = "Trap"
        else:
            if attribute or monster_typing:
                card_type = "Monster"
                if monster_typing:
                    parts = [p.strip() for p in monster_typing.split("/") if p.strip()]
                    if len(parts) > 1:
                        subtype_icon = " / ".join(parts[1:])

    return {
        "card_type": card_type,
        "subtype_icon": subtype_icon,
        "attribute": attribute,
        "monster_typing": monster_typing,
        "level_rank_link": level_rank_link,
        "atk": atk,
        "defense": defense,
    }


def is_extra_deck(subtype_icon: str) -> bool:
    if not subtype_icon:
        return False
    for t in EXTRA_DECK_TYPES:
        if t.lower() in subtype_icon.lower():
            return True
    return False


def extract_materials(card_text: str) -> str:
    if not card_text:
        return ""
    lines = [line.strip() for line in card_text.split("\n") if line.strip()]
    if not lines:
        return ""
    if len(lines) == 1:
        return lines[0]

    def is_effect_line(line: str) -> bool:
        if re.search(r"[\.:;]", line):
            return True
        if re.search(r"\b(When|If|During|Once|You can|Cannot|Must be|Target|Tribute|Special Summon|Destroy)\b", line):
            return True
        return False

    materials = []
    for line in lines:
        if materials and is_effect_line(line):
            break
        if not materials and is_effect_line(line):
            break
        materials.append(line)

    return "\n".join(materials) if materials else ""


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def categorize_mismatch(expected: str, actual: str, materials: str) -> tuple[str, str]:
    if normalize_newlines(expected) == normalize_newlines(actual):
        return "none", ""

    def collapse_ws(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    if collapse_ws(expected) == collapse_ws(actual):
        return "whitespace", "Normalize whitespace to preserve exact spacing and line breaks."

    if expected.replace("\n", "") == actual.replace("\n", ""):
        return "line breaks", "Preserve explicit line breaks from the source HTML, avoiding join/split that shifts lines."

    if materials and actual.startswith(materials) and not expected.startswith(materials):
        return "materials line handling", "Include the materials line at the top of the card text when present in the source."

    if expected.startswith(actual) or actual.startswith(expected):
        return "truncation", "Ensure full card text is captured; do not truncate at UI boundaries."

    if "Card Text" in expected or "Card Text" in actual:
        return "boilerplate", "Strip UI labels like \"Card Text\" from extracted text."

    return "other", "Review the HTML parsing block used for card text extraction to match the official text exactly."


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Generate a spot-check report for PSCT vs Konami DB."
    )
    parser.add_argument(
        "--clean-xlsx",
        default=str(repo_root / "data_processed" / "Fiendsmith_Master_Card_Library_CLEAN.xlsx"),
        help="Path to the clean card library XLSX.",
    )
    parser.add_argument(
        "--orig-xlsx",
        default=None,
        help="Optional path to the original input XLSX for normalization notes.",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(repo_root / "data_cache" / "konami_db"),
        help="Path to cached Konami card HTML.",
    )
    parser.add_argument(
        "--out",
        default=str(repo_root / "reports" / "spot_check_report.md"),
        help="Output path for the spot-check report.",
    )
    parser.add_argument(
        "--cards",
        nargs="+",
        default=None,
        help="Optional list of card names to check.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    clean_path = Path(args.clean_xlsx)
    orig_path = Path(args.orig_xlsx) if args.orig_xlsx else None
    cache_dir = Path(args.cache_dir)
    report_path = Path(args.out)

    if not clean_path.exists():
        print(f"FAIL: Missing clean XLSX at {clean_path}")
        sys.exit(1)
    if orig_path and not orig_path.exists():
        print(f"FAIL: Missing orig XLSX at {orig_path}")
        sys.exit(1)

    report_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(clean_path)
    orig_df = pd.DataFrame()
    if orig_path and orig_path.exists():
        orig_df = pd.read_excel(orig_path, sheet_name="Sheet1")

    def cell_text(value: object) -> str:
        if pd.isna(value):
            return ""
        return str(value)

    orig_map = {}
    if not orig_df.empty:
        for _, row in orig_df.iterrows():
            n = str(row.get("Name", ""))
            orig_map.setdefault(normalize_name(n), n)

    cards = args.cards if args.cards else DEFAULT_CARDS

    results = []
    fixes = []
    cache_hits = 0
    cache_misses = 0

    for name in cards:
        row = df[df["Name (Official formatting)"] == name]
        if row.empty:
            results.append({
                "name": name,
                "status": "FAIL",
                "reason": "Name not found in CLEAN.xlsx",
            })
            fixes.append("Ensure the card name matches the official formatting in CLEAN.xlsx.")
            continue

        rec = row.iloc[0]
        cid = cell_text(rec.get("CID", ""))
        url = cell_text(rec.get("Official DB URL", ""))
        verified = cell_text(rec.get("Verified Date", ""))
        extracted_text = cell_text(rec.get("Official Card Text (Exact, TCG)", ""))
        extracted_materials = cell_text(rec.get("Summoning Requirements / Materials", ""))

        normalization_notes = ""
        orig_name = orig_map.get(normalize_name(name), "")
        if orig_name:
            if any(ch in orig_name for ch in ["\u2019", "\u2010", "\u2011", "\u2013"]):
                if orig_name != name:
                    normalization_notes = (
                        f"Input name was '{orig_name}' and was normalized to '{name}'."
                    )

        cache_html = None
        cache_status = "MISS"
        if cid:
            cache_html = load_cached_html(cid, cache_dir)
            if cache_html:
                cache_status = "HIT"
                cache_hits += 1
            else:
                cache_misses += 1

        source_html = cache_html
        source_note = "cached HTML"
        if not source_html and url:
            try:
                source_html = fetch_html(url)
                source_note = "fresh fetch"
            except Exception as exc:
                source_html = None
                source_note = f"fetch failed: {exc}"

        source_text = ""
        source_materials = ""
        if source_html:
            source_text = extract_card_text(source_html)
            spec = extract_spec_block(source_html)
            if is_extra_deck(spec.get("subtype_icon", "")):
                source_materials = extract_materials(source_text)

        extracted_norm = normalize_newlines(extracted_text)
        source_norm = normalize_newlines(source_text)
        match = extracted_norm == source_norm

        status = "PASS" if match else "FAIL"
        diff_text = ""
        mismatch_category = ""
        heuristic_fix = ""
        if not match:
            mismatch_category, heuristic_fix = categorize_mismatch(extracted_norm, source_norm, source_materials)
            diff = difflib.unified_diff(
                source_norm.split("\n"),
                extracted_norm.split("\n"),
                fromfile="source",
                tofile="extracted",
                lineterm="",
            )
            diff_text = "\n".join(diff)
            if heuristic_fix:
                fixes.append(heuristic_fix)

        results.append({
            "name": name,
            "cid": cid,
            "url": url,
            "verified": verified,
            "normalization_notes": normalization_notes,
            "extracted_materials": extracted_materials,
            "extracted_text": extracted_text,
            "source_materials": source_materials,
            "source_text": source_text,
            "source_note": source_note,
            "cache_status": cache_status,
            "status": status,
            "diff": diff_text,
            "mismatch_category": mismatch_category,
            "heuristic_fix": heuristic_fix,
        })

    pass_count = sum(1 for r in results if r.get("status") == "PASS")
    fail_count = sum(1 for r in results if r.get("status") == "FAIL")

    lines = []
    lines.append("# Spot-Check Report: PSCT vs Konami DB")
    lines.append("")
    lines.append(f"Date: {date.today().isoformat()}")
    lines.append(f"Cards checked: {len(results)} | PASS: {pass_count} | FAIL: {fail_count}")
    lines.append(f"Cache: HIT {cache_hits} | MISS {cache_misses}")
    lines.append("")

    for r in results:
        lines.append(f"## {r['name']}")
        if r.get("reason"):
            lines.append(f"Status: FAIL ({r['reason']})")
            lines.append("")
            continue

        lines.append(f"Status: {r['status']}")
        lines.append(f"Name: {r['name']}")
        lines.append(f"CID: {r['cid']}")
        lines.append(f"Official DB URL: {r['url']}")
        lines.append(f"Verified Date: {r['verified']}")
        lines.append(f"Cache: {r['cache_status']} ({r['source_note']})")
        if r.get("normalization_notes"):
            lines.append(f"Normalization Notes: {r['normalization_notes']}")
        lines.append("")
        lines.append("Extracted:")
        if r['extracted_materials']:
            lines.append(f"- Summoning Requirements/Materials: {r['extracted_materials']}")
        else:
            lines.append("- Summoning Requirements/Materials: N/A")
        lines.append("- Official Card Text (Exact, TCG):")
        lines.append("```text")
        lines.append(r['extracted_text'])
        lines.append("```")
        lines.append("")
        lines.append("Source-of-truth excerpt:")
        if r['source_materials']:
            lines.append(f"- Summoning Requirements/Materials: {r['source_materials']}")
        else:
            lines.append("- Summoning Requirements/Materials: N/A")
        lines.append("- Official Card Text (Exact, TCG):")
        lines.append("```text")
        lines.append(r['source_text'])
        lines.append("```")
        lines.append("")
        lines.append("Comparison:")
        lines.append(f"- Exact match: {'YES' if r['status'] == 'PASS' else 'NO'}")
        if r['status'] == 'FAIL':
            lines.append(f"- Likely cause: {r['mismatch_category']}")
            if r['heuristic_fix']:
                lines.append(f"- Proposed heuristic fix: {r['heuristic_fix']}")
            if r['diff']:
                lines.append("- Diff:")
                lines.append("```diff")
                lines.append(r['diff'])
                lines.append("```")
        lines.append("")

    if fail_count:
        lines.append("## Fix Plan")
        lines.append("- Review the extraction script and update parsing to address the mismatches noted above.")
        if fixes:
            # Unique fixes, preserve order
            seen = set()
            unique_fixes = []
            for fix in fixes:
                if fix not in seen:
                    seen.add(fix)
                    unique_fixes.append(fix)
            for fix in unique_fixes:
                lines.append(f"- {fix}")
        lines.append("- Re-run the population script and regenerate this spot-check report.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    status = "PASS" if fail_count == 0 else "FAIL"
    print(
        f"Spot-check report: {status} | cards={len(results)} pass={pass_count} "
        f"fail={fail_count} | out={report_path}"
    )
    if fail_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
