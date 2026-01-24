# Yu-Gi-Oh Combo Pipeline Handoff (2026-01-23)

## Executive Summary
- Added Lua ground-truth verification for condition/cost/target hooks and activation gating.
- Introduced deterministic case file for 5 core cards and aligned Lua vs Python activation checks.
- Non-GPL guardrails preserved: Lua scripts are loaded only via `YGOPRO_SCRIPT_DIR`.

## What Changed
- `scripts/lua_ground_truth.py`
  - Requires `YGOPRO_SCRIPT_DIR` for script loading; skips gracefully if unset.
  - Added hook verification (`condition`, `cost`, `target`) + activation comparison.
  - Added Lua stubs for `bit32`, `Group` operations, `Card.IsNegatable`.
  - Added fusion material checker for Tract e2 (via `_py_fusion_materials_ok`).
  - Added case runner + CLI flags: `--cases`, `--verify-hooks`, `--verify-activation`, `--ci`.
- `config/lua_ground_truth_cases.json`
  - New deterministic cases for Engraver e3, Tract e2, Requiem e2, Lacrima CT e1, Desirae e1.

## How To Run (Ground Truth)
1) Set Lua scripts path (local only):
   ```bash
   export YGOPRO_SCRIPT_DIR=reports/verified_lua
   ```
2) Run the full location report:
   ```bash
   python3 scripts/lua_ground_truth.py --report
   ```
3) Run hook + activation verification:
   ```bash
   python3 scripts/lua_ground_truth.py \
     --cases config/lua_ground_truth_cases.json \
     --verify-hooks --verify-activation --report
   ```


## CI-gated Lua ground-truth cases test
- Added `tests/test_lua_ground_truth_cases.py`.
- This test **skips by default** and only runs when `YGOPRO_SCRIPT_DIR` is set.
- When enabled, it executes:
  - `python3 scripts/lua_ground_truth.py --cases config/lua_ground_truth_cases.json --verify-hooks --verify-activation --ci`
- Rationale: keep CI green without requiring local YGOPro lua scripts, while still allowing strict verification on dev machines.

## Validation Outputs
### Unit Tests
```
python3 -m unittest discover -s tests
s...............................................................................................................
----------------------------------------------------------------------
Ran 112 tests in 2.973s

OK (skipped=1)
```

### Effect Coverage
```
python3 audit_effect_coverage.py
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

### Modeling Status
```
python3 audit_modeling_status.py --fail
Decklist CIDs: 25
Modeled count: 25
Stub count (excluding allowed): 0
Missing count: 0
Stub CIDs (excluding allowed):
  (none)
Missing CIDs:
  (none)
```

### Lua Ground Truth (locations)
```
YGOPRO_SCRIPT_DIR=reports/verified_lua python3 scripts/lua_ground_truth.py --report
======================================================================
FULL GROUND TRUTH COMPARISON REPORT
======================================================================

CID 20196 (Fiendsmith Engraver):
  e1: Lua=hand         JSON=hand         ✓
  e2: Lua=field        JSON=field        ✓
  e3: Lua=gy           JSON=gy           ✓

CID 20240 (Fiendsmith's Tract):
  e1: Lua=trigger      JSON=spell        ✓
  e2: Lua=gy           JSON=gy           ✓

CID 20225 (Fiendsmith's Requiem):
  e1: Lua=field        JSON=field        ✓
  e2: Lua=field/gy     JSON=field        ✓

CID 20215 (Fiendsmith's Desirae):
  e1: Lua=field        JSON=field        ✓
  e2: Lua=trigger      JSON=gy           ✓

CID 20214 (Fiendsmith's Lacrima):
  e1: Lua=field        JSON=field        ✓
  e2: Lua=trigger      JSON=field        ✓
  e3: Lua=trigger      JSON=gy           ✓

CID 20238 (Fiendsmith's Sequence):
  e1: Lua=field        JSON=field        ✓
  e2: Lua=field/gy     JSON=field/gy     ✓

CID 20521 (Fiendsmith's Agnumday):
  e1: Lua=field        JSON=field        ✓

CID 20774 (Fiendsmith's Rextremende):
  e1: Lua=field        JSON=field        ✓
  e2: Lua=trigger      JSON=field        ✓
  e3: Lua=trigger      JSON=gy           ✓

CID 20241 (Fiendsmith's Sanct):
  e1: Lua=trigger      JSON=spell        ✓
  e2: Lua=gy           JSON=gy           ✓

CID 20251 (Fiendsmith in Paradise):
  e1: Lua=trigger      JSON=trap         ✓
  e2: Lua=gy           JSON=gy           ✓

CID 20816 (Fiendsmith Kyrie):
  e1: Lua=trigger      JSON=trap         ✓
  e2: Lua=gy           JSON=gy           ✓

CID 20490 (Lacrima the Crimson Tears):
  e1: Lua=trigger      JSON=field        ✓
  e2: Lua=trigger      JSON=field        ✓
  e3: Lua=gy           JSON=gy           ✓

======================================================================
SUMMARY
======================================================================

Total effects: 27
Matching: 27
Mismatches: 0
```

### Lua Ground Truth (conditions/costs/targets vs Python)
```
YGOPRO_SCRIPT_DIR=reports/verified_lua python3 scripts/lua_ground_truth.py --cases config/lua_ground_truth_cases.json --verify-hooks --verify-activation --report

CASE: Engraver e3: alone in GY
  lua.condition: None
  lua.cost: False
  lua.target: True
  lua_can=False py_can=False => OK

CASE: Engraver e3: other LIGHT Fiend in GY
  lua.condition: None
  lua.cost: True
  lua.target: True
  lua_can=True py_can=True => OK

CASE: Tract e2: Engraver missing
  lua.condition: None
  lua.cost: True
  lua.target: False
  lua_can=False py_can=False => OK

CASE: Tract e2: Engraver + 1 LIGHT Fiend
  lua.condition: None
  lua.cost: True
  lua.target: False
  lua_can=False py_can=False => OK

CASE: Tract e2: Engraver + 2 LIGHT Fiends
  lua.condition: None
  lua.cost: True
  lua.target: True
  lua_can=True py_can=True => OK

CASE: Requiem e2: only Link LIGHT Fiend on field
  lua.condition: None
  lua.cost: None
  lua.target: False
  lua_can=False py_can=False => OK

CASE: Requiem e2: non-Link LIGHT Fiend on field
  lua.condition: None
  lua.cost: None
  lua.target: True
  lua_can=True py_can=True => OK

CASE: Lacrima CT e1: no Fiendsmith in deck
  lua.condition: None
  lua.cost: None
  lua.target: False
  lua_can=False py_can=False => OK

CASE: Lacrima CT e1: Fiendsmith in deck
  lua.condition: None
  lua.cost: None
  lua.target: True
  lua_can=True py_can=True => OK

CASE: Desirae e1: no equips
  lua.condition: None
  lua.cost: None
  lua.target: False
  lua_can=False py_can=False => OK

CASE: Desirae e1: with equip
  lua.condition: None
  lua.cost: None
  lua.target: True
  lua_can=True py_can=True => OK
```

## Non-GPL Guardrails
- Do NOT vendor/copy YGOPro scripts into the repo.
- Provide Lua scripts via `YGOPRO_SCRIPT_DIR` only.
- Keep `cards.cdb` out of handoff bundles.

## Next Steps
- Add more cases to `config/lua_ground_truth_cases.json` for additional cards/effects.
- Extend Lua stubs only as needed to support new cases.
- Optionally wire a CI-skipped unit test that runs the case verifier when `YGOPRO_SCRIPT_DIR` is set.
