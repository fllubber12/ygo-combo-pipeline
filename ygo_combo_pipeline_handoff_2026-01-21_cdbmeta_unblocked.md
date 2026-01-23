# Yu-Gi-Oh Combo Pipeline Handoff (2026-01-21, cdb meta unblocked)

## Executive Summary
We were stuck because batch runs had `equip_actions_available=0` and missing metadata (attr/race/link) in terminal states. The root cause was that `cards.cdb` enrichment was a no-op: BabelCDB doesn't contain our custom CIDs. This was unblocked by adding a deterministic name-based fallback (texts.name -> datas.id) so custom CIDs can resolve to canonical metadata by name. With name fallback active and a real `cards.cdb` in repo root, batch runs now hit S=1 A=1 across all 10 hands for the standard seed7 probe.

## Key Decisions (Non-GPL Guardrails)
- Do NOT vendor/copy YGOPro code or scripts (GPL). We only ingest factual metadata from `cards.cdb`.
- `cards.cdb` remains a local runtime input (ignored by git and excluded from handoff zips).
- Metadata resolution is deterministic and fail-closed on ambiguity.

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
2) alias map (config/cdb_aliases.json) if present (NOT used yet)
3) texts.name exact match (case-insensitive) -> id -> datas row

Merge-only rule:
- CDB values are the base.
- Existing metadata overrides only when non-empty; empty strings never clobber CDB facts.

Diagnostic keys (debug only):
- _cdb_resolved_from: id | alias | name
- _cdb_resolved_id: numeric id used for lookup

## Batch Self-Debugging Outputs
- run_batch_search.py emits `*_final_snapshot.json` next to each markdown report.
  Includes: equip_actions_available, equip_action_ids, evaluation, and full final state snapshot.
- scripts/combos/make_fixture_from_snapshot.py builds a deterministic fixture from one of these snapshots.
  Use this to lock regressions when a surprising terminal state appears.

## Current Status
- Tests: OK (skipped=1)
- Coverage audit: Missing CIDs = 0
- Modeling status: Modeled 25, Stub 0, Missing 0
- Batch with metadata active:
  `reports/batch/seed7_d5_bw40_cdbmeta_namefallback/`
  All 10 hands: S=1 A=1

## Repro Instructions
1) Ensure cards.cdb is present at repo root (not bundled):
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
- If texts.name is ambiguous and YGOPRO_CDB_STRICT=1 (default), it fails closed.
- If a custom name does not exist in the DB, you must provide a local expansions CDB or alias map.

## Next Steps (Checklist)
- Optional: compute equip_actions_available histogram for the latest batch outputs.
- Now that metadata is fixed, review and remove "metadata-missing" hacks if unnecessary.
- Expand decklist scope + add 1-2 new golden fixtures targeting new S lines.
- Continue using fixture-from-snapshot to lock regressions from batch results.

## Validation Log (Exact Outputs)
### python3 -m unittest discover -s tests
```text

```

### python3 audit_effect_coverage.py
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
