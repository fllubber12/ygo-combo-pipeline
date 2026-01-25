# Yu-Gi-Oh Combo Pipeline Handoff (2026-01-21, cdb meta unblocked)

## Executive Summary
We were circling because batch runs reported `equip_actions_available=0` and missing metadata (attr/race/link) in terminal states. The root cause was that `cards.cdb` enrichment was a no-op because BabelCDB does not contain our custom CIDs. This was unblocked by adding a deterministic name-based fallback (texts.name -> datas.id) so custom CIDs can resolve to canonical metadata by name. With name fallback active and a real `cards.cdb` in repo root, the reported batch probe `seed7` at depth 5, beam 40 now yields S=1 A=1 across all 10 hands in `reports/batch/seed7_d5_bw40_cdbmeta_namefallback/`.

## Key Decisions (Non-GPL Guardrails)
- Do not vendor or copy YGOPro code or scripts (GPL). We only ingest factual metadata from `cards.cdb`.
- `cards.cdb` is a local runtime input, ignored by git and excluded from handoff bundles.
- Metadata resolution is deterministic and fail-closed on ambiguity (unless YGOPRO_CDB_STRICT=0).

## What Changed
- Added optional YGOPro CDB enrichment with caching and merge-only overrides.
- Added deterministic name-based CDB fallback for custom CIDs (texts.name exact match).
- Added batch-derived deterministic fixture for a previously failing A-ending state.
- Added inert coverage for FIENDSMITH_TOKEN.
- Tweaked opp-turn pop fixture to allow Desirae trigger within search depth.

Files changed/added:
- src/sim/ygopro_cdb.py
- src/sim/state.py
- tests/test_ygopro_cdb_metadata.py
- tests/test_fiendsmith_more_effects.py
- tests/fixtures/combo_scenarios/fixture_oppturn_pop_via_lacrima_requiem_paradise_desirae.json
- tests/fixtures/combo_scenarios/fixture_from_batch_fiendsmith_v1_seed7_hand10_final_snapshot.json
- audit_effect_coverage.py
- .gitignore
- Updates-only zip: updates_20260121_233755.zip

## Metadata Resolution Logic (Important)
Resolution order:
1) direct datas.id == CID
2) alias map (config/cdb_aliases.json) if present (not used in this repo snapshot)
3) texts.name exact match (case-insensitive) -> id -> datas row

Merge-only rule:
- CDB values are the base.
- Existing metadata overrides only when non-empty; empty strings never clobber CDB facts.

Diagnostic keys (debug only; must not affect game logic):
- _cdb_resolved_from: id | alias | name
- _cdb_resolved_id: numeric id used for lookup

## Batch Self-Debugging Outputs
- `scripts/combos/run_batch_search.py` emits `*_final_snapshot.json` next to each markdown report.
  Includes: equip_actions_available, equip_action_ids, evaluation, and the final state snapshot.
- `scripts/combos/make_fixture_from_snapshot.py` builds a deterministic fixture from one of these snapshots.
  Use this to lock regressions when a surprising terminal state appears.

## Current Status
- Reported: With metadata active, batch probe `seed7` (depth 5, beam 40) yields S=1 A=1 for all 10 hands.
- Current validation (this run): tests are failing; see Validation Log below.

## Repro Instructions
1) Ensure `cards.cdb` is present at repo root (not bundled):
   ```bash
   python3 - <<'PY'
   from src.sim.ygopro_cdb import _resolve_db_path, get_card_metadata
   print("cdb_path:", _resolve_db_path())
   print(get_card_metadata("20215", "Fiendsmith's Desirae"))
   PY
   ```
2) Run tests + audits:
   ```bash
   python3 -m unittest discover -s tests
   python3 audit_effect_coverage.py
   python3 audit_modeling_status.py --fail
   ```
3) Run batch with metadata active:
   ```bash
   python3 scripts/combos/run_batch_search.py decklists/fiendsmith_v1.ydk \
     --seed 7 --samples 10 --hand-size 5 --max-depth 5 --beam-width 40 \
     --output-dir reports/batch/seed7_d5_bw40_cdbmeta_namefallback
   ```

## Known Pitfalls
- BabelCDB lacks custom CIDs; name fallback only works if the English name exists in texts.name.
- If texts.name is ambiguous and YGOPRO_CDB_STRICT=1 (default), resolution fails closed.
- If a custom name does not exist in the DB, you must provide a local expansions CDB or alias map.

## Next Steps (Checklist)
- Optional: compute equip_actions_available histogram for the latest batch outputs.
- Now that metadata is fixed, review and remove metadata-missing hacks if unnecessary.
- Expand decklist scope and add 1-2 new golden fixtures targeting new S lines.
- Keep using fixture-from-snapshot to lock regressions from batch results.

## Validation Log (Exact Outputs)
### python3 -m unittest discover -s tests
```text
s.........F.F..........F......FF....FF..........FF...........FFFF.......................
======================================================================
FAIL: test_paradise_gy_send_rextremende_fixture (test_fiendsmith_in_paradise_effects.TestFiendsmithInParadiseEffects.test_paradise_gy_send_rextremende_fixture)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_fiendsmith_in_paradise_effects.py", line 48, in test_paradise_gy_send_rextremende_fixture
    self.assertIn("Fiendsmith in Paradise", snapshot["zones"]["banished"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'Fiendsmith in Paradise' not found in []

======================================================================
FAIL: test_lacrima_fusion_recover_ss_fixture (test_fiendsmith_lacrima_effects.TestFiendsmithLacrimaEffects.test_lacrima_fusion_recover_ss_fixture)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_fiendsmith_lacrima_effects.py", line 49, in test_lacrima_fusion_recover_ss_fixture
    self.assertIn("Fiendsmith Engraver", snapshot["zones"]["field"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'Fiendsmith Engraver' not found in ["Fiendsmith's Lacrima"]

======================================================================
FAIL: test_engraver_revive (test_fiendsmith_more_effects.TestFiendsmithMoreEffects.test_engraver_revive)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_fiendsmith_more_effects.py", line 70, in test_engraver_revive
    self.assertIn("Fiendsmith's Lacrima", snapshot["zones"]["deck"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: "Fiendsmith's Lacrima" not found in []

======================================================================
FAIL: test_oppturn_pop_fixture (test_fiendsmith_more_effects.TestFiendsmithMoreEffects.test_oppturn_pop_fixture)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_fiendsmith_more_effects.py", line 732, in test_oppturn_pop_fixture
    self.assertIn("Opponent Card", snapshot["zones"]["gy"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'Opponent Card' not found in ['Generic LIGHT Fiend']

======================================================================
FAIL: test_paradise_gy_trigger_requires_event (test_fiendsmith_more_effects.TestFiendsmithMoreEffects.test_paradise_gy_trigger_requires_event)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_fiendsmith_more_effects.py", line 261, in test_paradise_gy_trigger_requires_event
    self.assertTrue(actions)
    ~~~~~~~~~~~~~~~^^^^^^^^^
AssertionError: [] is not true

======================================================================
FAIL: test_requiem_tribute_ss (test_fiendsmith_more_effects.TestFiendsmithMoreEffects.test_requiem_tribute_ss)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_fiendsmith_more_effects.py", line 75, in test_requiem_tribute_ss
    self.assertIn("Fiendsmith's Lacrima", snapshot["zones"]["field"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: "Fiendsmith's Lacrima" not found in ["Fiendsmith's Requiem"]

======================================================================
FAIL: test_requiem_tribute_ss_lacrima (test_fiendsmith_more_effects.TestFiendsmithMoreEffects.test_requiem_tribute_ss_lacrima)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_fiendsmith_more_effects.py", line 232, in test_requiem_tribute_ss_lacrima
    self.assertTrue(actions)
    ~~~~~~~~~~~~~~~^^^^^^^^^
AssertionError: [] is not true

======================================================================
FAIL: test_abao_revive_sequence_equip (test_library_decklist_effects.TestLibraryDecklistEffects.test_abao_revive_sequence_equip)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_library_decklist_effects.py", line 100, in test_abao_revive_sequence_equip
    self.assertIn("A Bao A Qu, the Lightless Shadow", snapshot["zones"]["banished"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'A Bao A Qu, the Lightless Shadow' not found in []

======================================================================
FAIL: test_abao_revive_sequence_equip_auto_events (test_library_decklist_effects.TestLibraryDecklistEffects.test_abao_revive_sequence_equip_auto_events)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_library_decklist_effects.py", line 114, in test_abao_revive_sequence_equip_auto_events
    self.assertIn("A Bao A Qu, the Lightless Shadow", snapshot["zones"]["banished"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'A Bao A Qu, the Lightless Shadow' not found in []

======================================================================
FAIL: test_duke_demise_recover (test_library_decklist_effects.TestLibraryDecklistEffects.test_duke_demise_recover)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_library_decklist_effects.py", line 80, in test_duke_demise_recover
    self.assertIn("Buio the Dawn's Light", snapshot["zones"]["hand"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: "Buio the Dawn's Light" not found in []

======================================================================
FAIL: test_luce_destroy_trigger (test_library_decklist_effects.TestLibraryDecklistEffects.test_luce_destroy_trigger)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_library_decklist_effects.py", line 141, in test_luce_destroy_trigger
    self.assertIn("Opponent Card", snapshot["zones"]["gy"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'Opponent Card' not found in []

======================================================================
FAIL: test_luce_send_destroy (test_library_decklist_effects.TestLibraryDecklistEffects.test_luce_send_destroy)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_library_decklist_effects.py", line 136, in test_luce_send_destroy
    self.assertIn("Buio the Dawn's Light", snapshot["zones"]["gy"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: "Buio the Dawn's Light" not found in []

======================================================================
FAIL: test_muckraker_revive (test_library_decklist_effects.TestLibraryDecklistEffects.test_muckraker_revive)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/zacharyhartley/Desktop/Testing/tests/test_library_decklist_effects.py", line 58, in test_muckraker_revive
    self.assertIn("Buio the Dawn's Light", snapshot["zones"]["field"])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: "Buio the Dawn's Light" not found in ['Muckraker From the Underworld']

----------------------------------------------------------------------
Ran 88 tests in 2.687s

FAILED (failures=13, skipped=1)
```

### python3 audit_effect_coverage.py
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

### python3 audit_modeling_status.py --fail
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
