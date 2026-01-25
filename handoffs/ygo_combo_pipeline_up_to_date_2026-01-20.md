# YGO Combo Pipeline Handoff Summary (2026-01-20)

## Overview
This repo models a deterministic combo search for Fiendsmith lines with minimal, fail-closed effects. The engine is intentionally narrow: only explicitly modeled effects are available; unknown CIDs are ignored by the registry. Endboards are scored via a bucket evaluator.

## Key Engine Concepts
- GameState holds zones, OPT tracking, events, last_moved_to_gy markers, and equipped lists on monsters.
- Effect enumeration is deterministic (sorted keys); search uses a beam and can prefer the longest line via scenario flag `prefer_longest`.
- Extra Deck summons mark `properly_summoned=True` and `metadata.from_extra=True` on the summoned card instance.
- Equip cards are stored on the target monster as `equipped` CardInstance entries.

## Important Files
- Core state/plumbing: `src/sim/state.py`, `src/sim/search.py`, `src/sim/convert.py`
- Effects: `src/sim/effects/fiendsmith_effects.py`, `src/sim/effects/registry.py`
- Evaluator: `src/combos/endboard_evaluator.py`
- Runner: `scripts/combos/search_combo.py`
- Tests: `tests/test_fiendsmith_more_effects.py`

## Modeled Effects (Fiendsmith)
- Engraver: discard search Fiendsmith S/T; GY revive by shuffling LIGHT Fiend.
- Tract: hand discard search; GY banish to fuse Desirae using Engraver + 2 LIGHT Fiends.
- Sanct: hand activation to create a Fiendsmith Token (Level 1, 0/0) if only LIGHT Fiends on field.
- Requiem: quick tribute to SS Lacrima (Crimson) from hand/deck; equip effect from field/GY to LIGHT non-Link Fiend.
- Lacrima the Crimson Tears: on-field send Paradise from deck; opponent-turn GY quick to SS Requiem/Agnumday link from GY (to EMZ) while shuffling itself.
- Paradise (GY): on opponent special summon, banish self, send Desirae from Extra to GY.
- Desirae: on sent-to-GY trigger pop (requires another LIGHT Fiend in GY); on-field negate action with credits based on total equipped link rating.
- Agnumday: quick revive LIGHT non-Link Fiend from GY and equip itself; requires properly_summoned for extra-deck monsters.

## Equipped Link Rating
- `total_equipped_link_rating` sums link_rating of equipped links (Requiem=1, Agnumday=3).
- Evaluator awards S bucket if Desirae is on field with equipped link total >= 1.

## Events
- `events` list in state; used for opponent-turn and opponent special summon triggers.
- `last_moved_to_gy` list used for Desirae sent-to-GY trigger.

## Fixtures (Golden Scenarios)
- `fixture_desirae_via_tract_gy_fusion.json` -> A endboard (Desirae).
- `fixture_desirae_with_equipped_requiem_s.json` -> S endboard (Desirae + equipped Requiem).
- `fixture_oppturn_pop_via_lacrima_requiem_paradise_desirae.json` -> opponent-turn pop line.
- `fixture_oppturn_agnumday_revive_desirae.json` -> opponent-turn Agnumday revive + equip (S endboard).
- `fixture_requiem_link_summon.json` -> link summon to EMZ.
- `fixture_requiem_tribute_ss.json` -> Requiem tribute -> SS Lacrima.

## Tests
Run full suite:
- `python3 -m unittest discover -s tests`
Focused:
- `python3 -m unittest tests.test_fiendsmith_more_effects`
Sanity run fixture:
- `python3 scripts/combos/search_combo.py --scenario tests/fixtures/combo_scenarios/fixture_oppturn_agnumday_revive_desirae.json`

## Latest Diff Zip
- `updates_20260120_130909.zip` (latest diff)

## Notes / Constraints
- Fail-closed: effects only enumerate when modeled.
- Deterministic ordering for actions and search.
- Equip modeling is minimal; no ATK/DEF changes or equip limits.
- Desirae negate is a capability marker (no chain resolution).

## Next Milestone
Milestone A: Sequence (CID 20238).
