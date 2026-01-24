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
- `updates_20260122_101740.zip` (latest diff)

## Notes / Constraints
- Fail-closed: effects only enumerate when modeled.
- Deterministic ordering for actions and search.
- Equip modeling is minimal; no ATK/DEF changes or equip limits.
- Desirae negate is a capability marker (no chain resolution).

## Hybrid Completion Definition
- Coverage audit must pass.
- Modeling-status audit must show Stub count == 0 (excluding explicitly allowed placeholders).
- Full unit test suite green.

## Next Milestone
Hybrid completion achieved for current library decklist; add new decklist entries and model them as needed.

## Update Log
- 2026-01-23: **Major Rules Compliance Fixes** (87 tests passing)
  - **Illegal Fusion Fix**: Core actions.py now skips fusion summon_type in generate_actions (line 278). Fusion summons REQUIRE card effects (Tract, Sequence, Kyrie) - cannot be performed as built-in mechanic.
  - **Fabled Lurrie (CID 8092)**: Added to library_effects.py with LURRIE_DISCARD_TRIGGER. SS from GY when discarded, NOT OPT. Registered in registry.py, trigger derivation in search.py.
  - **Kyrie GY Effect Fixed**: Now fuses ANY Fiendsmith Fusion (Lacrima/Desirae/Rextremende) via FIENDSMITH_FUSION_CIDS. Effect_id renamed to "kyrie_gy_banish_fuse". Materials requirement fixed: ANY LIGHT Fiend monsters (was wrongly requiring Fiendsmith Fusion as material).
  - **Necroquip Princess Contact Fusion**: Implemented "necroquip_contact_fusion" effect. Materials: 1 monster with equip + 1 Fiend → SS from Extra. Control restriction enforced.
  - **Xyz Level Matching**: Added xyz_materials_valid() in actions.py. All materials must have same Level matching Xyz Rank. Link monsters cannot be Xyz material. Fixed test fixtures: Caesar is Rank 6 (needs 2 Level 6 monsters).
  - **Lacrima CT Effect Fixed**: Can send ANY Fiendsmith card from deck (was hardcoded to Paradise only). New constant LACRIMA_CT_SEND_TARGET_CIDS. Effect_id renamed to "send_fiendsmith_from_deck". Sets last_moved_to_gy for triggers.
  - **Tract Discard Fix**: Now sets last_moved_to_gy when discarding, enabling Lurrie trigger.
  - **Fixture Updates**: fixture_caesar_via_sanct.json, fixture_search_combo.json updated for correct Xyz Level 6 materials.
  - **New Test**: test_lacrima_can_send_kyrie_from_deck verifies Lacrima CT can send Kyrie.
  - **New Fixture**: fixture_engraver_plus_body.json for S-tier combo testing.
  - QA: `python3 -m unittest discover -s tests` (OK, 87 tests, skipped=1)

- 2026-01-23: **Search Limitation Identified**
  - Search finds S=1 (Desirae + equipped link) but NOT Caesar.
  - Root cause: rank_key uses boolean for S-tier (True/False), not count.
  - With 1 Engraver, Desirae line and Caesar line are mutually exclusive (Engraver used as fusion material vs needed on field for Xyz).
  - Pending: Change rank_key to count S-tier pieces (S=2 > S=1).

- 2026-01-20: Modeled remaining library decklist cards and removed stubbed placeholder behavior.
  - Modeled CIDs: 10942, 13081, 14856, 17806, 19188, 20226, 20389, 20423, 20427, 20772, 20786, 21624, 21625, 21626.
  - New fixtures/tests for each event-gated effect; Exciton/Caesar now require explicit event tokens (no free actions).
  - QA: `python3 -m unittest discover -s tests` (OK, skipped=1); `python3 scripts/audit_effect_coverage.py` (Missing=0); `python3 scripts/audit_modeling_status.py --fail` (Modeled=25, Stub=0, Missing=0)
  - Updates zip: `updates_20260120_232311.zip`
- 2026-01-20: CID 13081 moved from Missing → Stub so modeling-status audit can drive it.
  - Files changed/added: `src/sim/effects/inert_effects.py`, `src/sim/effects/registry.py`
  - QA: `python3 -m unittest discover -s tests` (OK, skipped=1); `python3 scripts/audit_modeling_status.py --fail` (stubbed still nonzero)
  - Updates zip: `updates_20260120_222431.zip`
- 2026-01-20: Modeled Evilswarm Exciton Knight (CID 10942) minimal self-send effect.
  - New fixture/test for deterministic self-send.
  - QA: `python3 scripts/audit_modeling_status.py --fail` (stub count -1); `python3 -m unittest discover -s tests` (OK, skipped=1)
  - Updates zip: `updates_20260120_222431.zip`
- 2026-01-20: Modeled D/D/D Wave High King Caesar (CID 13081) minimal self-send effect.
  - New fixture/test for deterministic self-send.
  - QA: `python3 scripts/audit_modeling_status.py --fail` (stub count -1); `python3 -m unittest discover -s tests` (OK, skipped=1)
  - Updates zip: `updates_20260120_222431.zip`
- 2026-01-20: Added modeling-status audit to distinguish stubbed vs modeled cards.
  - New script and non-blocking unit test; stubs remain coverage-only.
  - QA: `python3 -m unittest tests.test_fiendsmith_kyrie_effects` (OK); `python3 -m unittest discover -s tests` (OK, skipped=1)
  - Updates zip: `updates_20260120_221525.zip`
- 2026-01-20: Registered inert coverage for remaining decklist CIDs (10942, 14856, 17806, 19188, 20226, 20389, 20423, 20427, 20772, 20786, 21624, 21625, 21626).
  - New inert fixtures and a consolidated test for deterministic coverage.
  - QA: `python3 -m unittest tests.test_fiendsmith_kyrie_effects` (OK); `python3 -m unittest discover -s tests` (OK, skipped=1)
  - Updates zip: `updates_20260120_220900.zip`
- 2026-01-20: Implemented Fiendsmith's Lacrima (CID 20214) minimal fusion-recover + sent-to-GY shuffle trigger.
  - New fixtures/tests for fusion recover and GY shuffle.
  - QA: `python3 -m unittest tests.test_fiendsmith_kyrie_effects` (OK); `python3 -m unittest discover -s tests` (OK, skipped=1)
  - Updates zip: `updates_20260120_181615.zip`
- 2026-01-20: Coverage audit is now decklist-driven via `decklists/library.ydk`; fixtures still included.
  - Files changed/added: `scripts/audit_effect_coverage.py`, `tests/test_effect_coverage_audit.py`, `decklists/library.ydk`, `ygo_combo_pipeline_handoff_2026-01-20.md`
  - QA: `python3 -m unittest tests.test_fiendsmith_kyrie_effects` (OK); `python3 -m unittest discover -s tests` (OK, skipped=1)
  - Updates zip: `updates_20260120_212729.zip`
- 2026-01-20: Verified Milestone A already implemented in current tree; no code changes needed.
  - Files changed/added: `ygo_combo_pipeline_handoff_2026-01-20.md`
  - QA: `python3 -m unittest tests.test_fiendsmith_kyrie_effects` (OK); `python3 -m unittest discover -s tests` (OK, skipped=1)
  - Updates zip: `updates_20260120_175544.zip`
- 2026-01-20: Verified Milestone A already implemented in current tree; no code changes needed.
  - Files changed/added: `ygo_combo_pipeline_handoff_2026-01-20.md`
  - QA: `python3 -m unittest tests.test_fiendsmith_kyrie_effects` (OK); `python3 -m unittest discover -s tests` (OK, skipped=1)
  - Updates zip: `updates_20260120_175544.zip`

- Handoff refresh (2026-01-21 09:02)
  - QA: `python3 -m unittest discover -s tests` (exit 0)
  - Coverage audit: Missing CIDs (unknown) (exit 0)
  - Modeling-status: Modeled unknown, Stub unknown, Missing unknown (exit 0)
  - Latest diff zip: `updates_20260120_232311.zip`
  - Bundles: `handoff_min_20260121_090234.zip`, `handoff_context_20260121_090234.zip`
  - QA output:
```text
..............................................................................
----------------------------------------------------------------------
Ran 78 tests in 1.406s

OK
```
  - Coverage output:
```text
Registered CIDs (27):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
Inert CIDs (9):
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Fixture CIDs (36):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Decklist CIDs (25):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
Missing CIDs (0):
```
  - Modeling-status output:
```text
Decklist CIDs: 25
Modeled count: 25
Stub count (excluding allowed): 0
Missing count: 0
Stub CIDs (excluding allowed):
  (none)
Missing CIDs:
  (none)
```

- Handoff refresh (2026-01-21 10:06)
  - QA: `python3 -m unittest discover -s tests` (exit 0)
  - Coverage audit: Missing CIDs (unknown) (exit 0)
  - Modeling-status: Modeled unknown, Stub unknown, Missing unknown (exit 0)
  - Latest diff zip: `updates_20260121_090302.zip`
  - Bundles: `handoff_min_20260121_100638.zip`, `handoff_context_20260121_100638.zip`
  - QA output:
```text
..............................................................................
----------------------------------------------------------------------
Ran 78 tests in 1.416s

OK
```
  - Coverage output:
```text
Registered CIDs (27):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
Inert CIDs (9):
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Fixture CIDs (36):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Decklist CIDs (25):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
Missing CIDs (0):
```
  - Modeling-status output:
```text
Decklist CIDs: 25
Modeled count: 25
Stub count (excluding allowed): 0
Missing count: 0
Stub CIDs (excluding allowed):
  (none)
Missing CIDs:
  (none)
```

- Handoff refresh (2026-01-21 11:08)
  - QA: `python3 -m unittest discover -s tests` (exit 0)
  - Coverage audit: Missing CIDs (unknown) (exit 0)
  - Modeling-status: Modeled unknown, Stub unknown, Missing unknown (exit 0)
  - Latest diff zip: `updates_20260121_102836.zip`
  - Bundles: `handoff_min_20260121_110808.zip`, `handoff_context_20260121_110808.zip`
  - QA output:
```text
................................................................................
----------------------------------------------------------------------
Ran 80 tests in 1.564s

OK
```
  - Coverage output:
```text
Registered CIDs (27):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
Inert CIDs (9):
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Fixture CIDs (36):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Decklist CIDs (26):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
Missing CIDs (0):
```
  - Modeling-status output:
```text
Decklist CIDs: 25
Modeled count: 25
Stub count (excluding allowed): 0
Missing count: 0
Stub CIDs (excluding allowed):
  (none)
Missing CIDs:
  (none)
```

- Handoff refresh (2026-01-21 11:11)
  - QA: `python3 -m unittest discover -s tests` (exit 0)
  - Coverage audit: Missing CIDs (unknown) (exit 0)
  - Modeling-status: Modeled unknown, Stub unknown, Missing unknown (exit 0)
  - Latest diff zip: `updates_20260121_111042.zip`
  - Bundles: `handoff_min_20260121_111127.zip`, `handoff_context_20260121_111127.zip`
  - QA output:
```text
................................................................................
----------------------------------------------------------------------
Ran 80 tests in 1.460s

OK
```
  - Coverage output:
```text
Registered CIDs (27):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
Inert CIDs (9):
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Fixture CIDs (36):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Decklist CIDs (26):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
Missing CIDs (0):
```
  - Modeling-status output:
```text
Decklist CIDs: 25
Modeled count: 25
Stub count (excluding allowed): 0
Missing count: 0
Stub CIDs (excluding allowed):
  (none)
Missing CIDs:
  (none)
```

- Handoff refresh (2026-01-21 12:02)
  - QA: `python3 -m unittest discover -s tests` (exit 0)
  - Coverage audit: Missing CIDs (unknown) (exit 0)
  - Modeling-status: Modeled unknown, Stub unknown, Missing unknown (exit 0)
  - Latest diff zip: `updates_20260121_120200.zip`
  - Bundles: `handoff_min_20260121_120214.zip`, `handoff_context_20260121_120214.zip`
  - QA output:
```text
..................................................................................
----------------------------------------------------------------------
Ran 82 tests in 1.561s

OK
```
  - Coverage output:
```text
Registered CIDs (27):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
Inert CIDs (9):
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Fixture CIDs (36):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Decklist CIDs (26):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
Missing CIDs (0):
```
  - Modeling-status output:
```text
Decklist CIDs: 25
Modeled count: 25
Stub count (excluding allowed): 0
Missing count: 0
Stub CIDs (excluding allowed):
  (none)
Missing CIDs:
  (none)
```

- Handoff refresh (2026-01-21 21:39)
  - QA: `python3 -m unittest discover -s tests` (exit 0)
  - Coverage audit: Missing CIDs (unknown) (exit 0)
  - Modeling-status: Modeled unknown, Stub unknown, Missing unknown (exit 0)
  - Latest diff zip: `updates_20260121_212014.zip`
  - Bundles: `handoff_min_20260121_213930.zip`, `handoff_context_20260121_213930.zip`
  - QA output:
```text
.....................................................................................
----------------------------------------------------------------------
Ran 85 tests in 4.053s

OK
```
  - Coverage output:
```text
Registered CIDs (27):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
Inert CIDs (9):
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Fixture CIDs (36):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Decklist CIDs (26):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
Missing CIDs (0):
```
  - Modeling-status output:
```text
Decklist CIDs: 25
Modeled count: 25
Stub count (excluding allowed): 0
Missing count: 0
Stub CIDs (excluding allowed):
  (none)
Missing CIDs:
  (none)
```

- Refresh Log (2026-01-21): CDB metadata unblocked via name fallback; batch now S=1 A=1 across 10 hands.
  - Name-based lookup (texts.name -> datas.id) added to YGOPro CDB enrichment; resolves custom CIDs when BabelCDB lacks them.
  - Added batch-derived deterministic fixture and inert token coverage; opp-turn pop fixture depth adjusted.
  - Updates zip: `updates_20260121_233755.zip`

- Handoff refresh (2026-01-22 10:13)
  - QA: `python3 -m unittest discover -s tests` (exit 0)
  - Coverage audit: Missing CIDs (unknown) (exit 0)
  - Modeling-status: Modeled unknown, Stub unknown, Missing unknown (exit 0)
  - Latest diff zip: `updates_20260122_094430.zip`
  - Bundles: `handoff_min_20260122_101350.zip`, `handoff_context_20260122_101350.zip`
  - QA output:
```text
..........................................................................................
----------------------------------------------------------------------
Ran 90 tests in 2.597s

OK
```
  - Coverage output:
```text
Registered CIDs (27):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
Inert CIDs (13):
  90001
  90002
  90003
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  FIENDSMITH_TOKEN
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Fixture CIDs (40):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  90001
  90002
  90003
  DEMO_EXTENDER_001
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  FIENDSMITH_TOKEN
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Decklist CIDs (26):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
Missing CIDs (0):
```
  - Modeling-status output:
```text
Decklist CIDs: 25
Modeled count: 25
Stub count (excluding allowed): 0
Missing count: 0
Stub CIDs (excluding allowed):
  (none)
Missing CIDs:
  (none)
```

- Handoff refresh (2026-01-23 10:01)
  - QA: `python3 -m unittest discover -s tests` (exit 0)
  - Coverage audit: Missing CIDs (unknown) (exit 0)
  - Modeling-status: Modeled unknown, Stub unknown, Missing unknown (exit 0)
  - Latest diff zip: `updates_20260122_101740.zip`
  - Bundles: `handoff_min_20260123_100144.zip`, `handoff_context_20260123_100144.zip`
  - QA output:
```text
..........................................................................................
----------------------------------------------------------------------
Ran 90 tests in 2.378s

OK
```
  - Coverage output:
```text
Registered CIDs (27):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  DEMO_EXTENDER_001
Inert CIDs (12):
  90001
  90002
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  FIENDSMITH_TOKEN
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Fixture CIDs (39):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  90001
  90002
  DEMO_EXTENDER_001
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  FIENDSMITH_TOKEN
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  OPP_CARD_1
Decklist CIDs (26):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
Missing CIDs (0):
```
  - Modeling-status output:
```text
Decklist CIDs: 25
Modeled count: 25
Stub count (excluding allowed): 0
Missing count: 0
Stub CIDs (excluding allowed):
  (none)
Missing CIDs:
  (none)
```

- Handoff refresh (2026-01-23 12:58)
  - QA: `python3 -m unittest discover -s tests` (exit 0)
  - Coverage audit: Missing CIDs (unknown) (exit 0)
  - Modeling-status: Modeled unknown, Stub unknown, Missing unknown (exit 0)
  - Latest diff zip: `updates_20260122_101740.zip`
  - Bundles: `handoff_min_20260123_125815.zip`, `handoff_context_20260123_125815.zip`
  - QA output:
```text
...........................................................................................
----------------------------------------------------------------------
Ran 91 tests in 2.423s

OK
```
  - Coverage output:
```text
Registered CIDs (28):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  8092
  DEMO_EXTENDER_001
Inert CIDs (16):
  90001
  90002
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  FIENDSMITH_TOKEN
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  INERT_01
  INERT_02
  INERT_03
  OPP_CARD_1
  RANDOM_CARD
Fixture CIDs (43):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  8092
  90001
  90002
  DEMO_EXTENDER_001
  DISCARD_1
  DUMMY_1
  DUMMY_2
  DUMMY_3
  DUMMY_4
  FIENDSMITH_TOKEN
  G_LIGHT_FIEND_A
  G_LIGHT_FIEND_B
  G_LINK_MAT
  INERT_01
  INERT_02
  INERT_03
  OPP_CARD_1
Decklist CIDs (27):
  10942
  13081
  14856
  17806
  19188
  20196
  20214
  20215
  20225
  20226
  20238
  20240
  20241
  20251
  20389
  20423
  20427
  20490
  20521
  20772
  20774
  20786
  20816
  21624
  21625
  21626
  8092
Missing CIDs (0):
```
  - Modeling-status output:
```text
Decklist CIDs: 25
Modeled count: 25
Stub count (excluding allowed): 0
Missing count: 0
Stub CIDs (excluding allowed):
  (none)
Missing CIDs:
  (none)
```

- 2026-01-21: Handoff refresh for cdb metadata + name fallback (non-GPL facts only).
  - Note: cards.cdb ingestion active via texts.name fallback; batch reports previously showed S=1 A=1 across 10 hands under cdbmeta_namefallback.
  - Added deterministic batch-derived fixture and inert coverage for FIENDSMITH_TOKEN.
  - Tweaked opp-turn pop fixture to allow Desirae trigger within max_depth.
  - QA (this run): `python3 -m unittest discover -s tests` (FAILED, 13 failures); `python3 audit_effect_coverage.py` (Missing=0); `python3 audit_modeling_status.py --fail` (Modeled=25, Stub=0, Missing=0).
  - Updates zip: `updates_20260123_162828.zip`
