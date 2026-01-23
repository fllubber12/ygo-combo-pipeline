#!/usr/bin/env python3
"""Seeded hand sampler -> combo search -> report generator."""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "src"))

from combos.endboard_evaluator import evaluate_endboard  # noqa: E402
from sim.actions import Action  # noqa: E402
from sim.convert import game_state_to_endboard_snapshot  # noqa: E402
from sim.effects.registry import enumerate_effect_actions  # noqa: E402
from sim.effects.fiendsmith_effects import is_light_fiend_card, is_link_monster  # noqa: E402
from sim.effects.types import EffectAction  # noqa: E402
from sim.search import EQUIP_EFFECT_IDS, _add_derived_events, search_best_line  # noqa: E402
from sim.state import GameState  # noqa: E402

CARD_NAME_BY_CID = {
    "10942": "Evilswarm Exciton Knight",
    "13081": "D/D/D Wave High King Caesar",
    "14856": "Cross-Sheep",
    "17806": "Muckraker From the Underworld",
    "19188": "S:P Little Knight",
    "20196": "Fiendsmith Engraver",
    "20214": "Fiendsmith's Lacrima",
    "20215": "Fiendsmith's Desirae",
    "20225": "Fiendsmith's Requiem",
    "20226": "Fiendsmith's Sequence",
    "20238": "Fiendsmith's Sequence",
    "20240": "Fiendsmith's Tract",
    "20241": "Fiendsmith's Sanct",
    "20251": "Fiendsmith in Paradise",
    "20389": "The Duke of Demise",
    "20423": "Necroquip Princess",
    "20427": "Aerial Eater",
    "20490": "Lacrima the Crimson Tears",
    "20521": "Fiendsmith's Agnumday",
    "20772": "Snake-Eyes Doomed Dragon",
    "20774": "Fiendsmith's Rextremende",
    "20786": "A Bao A Qu, the Lightless Shadow",
    "20816": "Fiendsmith Kyrie",
    "21624": "Buio the Dawn's Light",
    "21625": "Luce the Dusk's Dark",
    "21626": "Mutiny in the Sky",
}

# Verified against docs/CARD_DATA.md
SUMMON_TYPE_BY_CID = {
    "10942": "xyz",   # Evilswarm Exciton Knight
    "13081": "xyz",   # D/D/D Wave High King Caesar
    "14856": "link",  # Cross-Sheep
    "17806": "link",  # Muckraker From the Underworld
    "19188": "link",  # S:P Little Knight
    "20214": "fusion",  # Fiendsmith's Lacrima (Fusion)
    "20215": "fusion",  # Fiendsmith's Desirae
    "20225": "link",  # Fiendsmith's Requiem
    "20226": "link",  # Fiendsmith's Sequence (alt CID)
    "20238": "link",  # Fiendsmith's Sequence
    "20423": "fusion",  # Necroquip Princess
    "20427": "fusion",  # Aerial Eater
    "20521": "link",  # Fiendsmith's Agnumday
    "20772": "fusion",  # Snake-Eyes Doomed Dragon
    "20774": "fusion",  # Fiendsmith's Rextremende
    "20786": "link",  # A Bao A Qu, the Lightless Shadow
    # NOTE: CID 20816 (Fiendsmith Kyrie) is a TRAP card, not a monster - omitted
}


def card_to_raw(card) -> dict:
    data = {
        "cid": card.cid,
        "name": card.name,
        "metadata": dict(card.metadata),
        "properly_summoned": bool(getattr(card, "properly_summoned", False)),
    }
    if getattr(card, "equipped", None):
        data["equipped"] = [card_to_raw(item) for item in card.equipped]
    return data


def game_state_to_snapshot(state: GameState) -> dict:
    return {
        "turn_number": state.turn_number,
        "phase": state.phase,
        "normal_summon_set_used": state.normal_summon_set_used,
        "opt_used": dict(state.opt_used),
        "restrictions": list(state.restrictions),
        "events": list(state.events),
        "last_moved_to_gy": list(state.last_moved_to_gy),
        "zones": {
            "hand": [card_to_raw(card) for card in state.hand],
            "deck": [card_to_raw(card) for card in state.deck],
            "gy": [card_to_raw(card) for card in state.gy],
            "banished": [card_to_raw(card) for card in state.banished],
            "extra": [card_to_raw(card) for card in state.extra],
            "field_zones": {
                "mz": [card_to_raw(card) if card else None for card in state.field.mz],
                "emz": [card_to_raw(card) if card else None for card in state.field.emz],
                "stz": [card_to_raw(card) if card else None for card in state.field.stz],
                "fz": [card_to_raw(card) if card else None for card in state.field.fz],
            },
        },
    }


def parse_ydk(path: Path) -> dict[str, list[str]]:
    sections = {"main": [], "extra": [], "side": []}
    current = "main"
    for raw_line in path.read_text(encoding="utf-8").splitlines():
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
        if line.startswith("#"):
            continue
        sections[current].append(line)
    return sections


def make_card(cid: str, is_extra: bool = False) -> dict:
    card = {"cid": cid, "name": CARD_NAME_BY_CID.get(cid, f"CID {cid}")}
    metadata = {}
    summon_type = SUMMON_TYPE_BY_CID.get(cid)
    if summon_type:
        metadata["summon_type"] = summon_type
    if is_extra:
        metadata["from_extra"] = True
    if metadata:
        card["metadata"] = metadata
    return card


def build_state(hand: list[str], deck: list[str], extra: list[str]) -> GameState:
    snapshot = {
        "phase": "Main Phase 1",
        "events": [],
        "zones": {
            "field_zones": {
                "mz": [None, None, None, None, None],
                "emz": [None, None],
            },
            "hand": [make_card(cid) for cid in hand],
            "deck": [make_card(cid) for cid in deck],
            "gy": [],
            "banished": [],
            "extra": [make_card(cid, is_extra=True) for cid in extra],
        },
        "opt_used": {},
        "last_moved_to_gy": [],
    }
    return GameState.from_snapshot(snapshot)


def write_report(name: str, result, out_path: Path, hand: list[str], seed: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = game_state_to_endboard_snapshot(result.final_state)
    state_snapshot = game_state_to_snapshot(result.final_state)
    lines = []
    lines.append(f"# Batch Combo Report: {name}")
    lines.append("")
    lines.append(f"- seed: {seed}")
    lines.append(f"- hand: {', '.join(hand) if hand else '(empty)'}")
    lines.append("")
    core_actions = [action for action in result.actions if isinstance(action, Action)]
    effect_actions = [action for action in result.actions if isinstance(action, EffectAction)]
    lines.append("## Core Actions")
    if core_actions:
        for idx, action in enumerate(core_actions, start=1):
            lines.append(f"{idx}. {action.describe()}")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Effect Actions")
    if effect_actions:
        for idx, action in enumerate(effect_actions, start=1):
            lines.append(f"{idx}. {action.describe()}")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Target Eligibility Diagnostics")
    mz_cards = [c for c in result.final_state.field.mz if c]
    lines.append(f"- mz_count: {len(mz_cards)}")
    for c in mz_cards:
        attr = str(c.metadata.get("attribute", ""))
        race = str(c.metadata.get("race", ""))
        stype = str(c.metadata.get("summon_type", ""))
        lines.append(
            f"- {c.name} (cid={c.cid}) attr={attr} race={race} summon_type={stype} "
            f"properly={getattr(c, 'properly_summoned', False)} "
            f"is_light_fiend={is_light_fiend_card(c)} is_link={is_link_monster(c)}"
        )
    lines.append(f"- open_mz: {len(result.final_state.open_mz_indices())}")
    lines.append(f"- open_emz: {len(result.final_state.open_emz_indices())}")
    lines.append(
        f"- hand_size: {len(result.final_state.hand)} "
        f"fiend_in_hand: {sum(1 for c in result.final_state.hand if str(c.metadata.get('race', '')).upper() == 'FIEND')}"
    )
    lines.append(f"- gy_size: {len(result.final_state.gy)}")
    lines.append(f"- extra_has_sequence: {any(c.cid == '20226' for c in result.final_state.extra)}")
    lines.append(f"- extra_has_requiem: {any(c.cid == '20225' for c in result.final_state.extra)}")
    lines.append("")
    # Diagnostics: are equip actions available at the terminal state?
    derived_state = _add_derived_events(result.final_state)
    equip_actions = [
        a for a in enumerate_effect_actions(derived_state) if a.effect_id in EQUIP_EFFECT_IDS
    ]
    equip_actions_available = len(equip_actions)
    equip_action_ids = sorted({a.effect_id for a in equip_actions})
    lines.append("## Equip Diagnostics")
    lines.append(f"- equip_actions_available: {equip_actions_available}")
    if equip_actions:
        lines.append("- equip_action_ids: " + ", ".join(equip_action_ids))
    else:
        lines.append("- equip_action_ids: (none)")
    lines.append("")

    lines.append("## Final Snapshot")
    lines.append("```json")
    lines.append(json.dumps(snapshot, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Endboard Evaluation")
    lines.append(f"- rank_key: {result.evaluation['rank_key']}")
    lines.append(f"- summary: {result.evaluation['summary']}")
    lines.append("")
    lines.append("### Achieved Buckets")
    lines.append("```json")
    lines.append(json.dumps(result.evaluation.get("achieved", []), indent=2))
    lines.append("```")
    snapshot_path = out_path.parent / f"{name}_final_snapshot.json"
    payload = {
        "hand_index": int(name.rsplit("_hand", 1)[-1]) if "_hand" in name else None,
        "seed": seed,
        "rank_key": result.evaluation.get("rank_key"),
        "evaluation": result.evaluation,
        "equip_actions_available": equip_actions_available,
        "equip_action_ids": equip_action_ids,
        "final_snapshot": snapshot,
        "final_state_snapshot": state_snapshot,
    }
    snapshot_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seeded batch combo runner.")
    parser.add_argument(
        "decklist_path",
        nargs="?",
        default=None,
        help="Optional decklist path (.ydk). Overrides --decklist.",
    )
    parser.add_argument(
        "--decklist",
        default=str(repo_root / "decklists" / "fiendsmith_v1.ydk"),
        help="Path to decklist (.ydk).",
    )
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--hand-size", type=int, default=5)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--beam-width", type=int, default=10)
    parser.add_argument(
        "--output-dir",
        default=str(repo_root / "reports" / "batch"),
        help="Directory for batch reports.",
    )
    parser.add_argument("--prefer-longest", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    decklist_arg = args.decklist_path or args.decklist
    decklist_path = Path(decklist_arg)
    if not decklist_path.exists():
        raise SystemExit(f"Missing decklist: {decklist_path}")

    sections = parse_ydk(decklist_path)
    main_cards = sections["main"]
    extra_cards = sections["extra"]

    if args.hand_size > len(main_cards):
        raise SystemExit("Hand size exceeds main deck card count.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for idx in range(args.samples):
        rng = random.Random(args.seed + idx)
        deck = list(main_cards)
        rng.shuffle(deck)
        hand = deck[: args.hand_size]
        remaining = deck[args.hand_size :]

        state = build_state(hand, remaining, extra_cards)
        result = search_best_line(
            state,
            max_depth=args.max_depth,
            beam_width=args.beam_width,
            allowed_actions=None,
            prefer_longest=False,
        )

        evaluation = evaluate_endboard(game_state_to_endboard_snapshot(result.final_state))
        name = f"{decklist_path.stem}_seed{args.seed}_hand{idx + 1}"
        out_path = output_dir / f"{name}.md"
        write_report(name, result, out_path, hand, args.seed)
        print(f"{name}: {evaluation['summary']} -> {out_path}")


if __name__ == "__main__":
    main()
