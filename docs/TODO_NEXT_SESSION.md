# TODO: Next Session

## Priority 1: Search Scoring Fix

### Problem
Search stops at S=1 (Desirae + equipped link) instead of exploring S=2 (Desirae + Caesar).

### Root Cause
`rank_key` in `src/combos/endboard_evaluator.py` uses boolean for S-tier:
```python
rank_key: (True, True, 3)  # (has_s, has_a, b_count)
```
Should count S-tier pieces instead:
```python
rank_key: (2, 1, 3)  # (s_count, a_count, b_count)
```

### Fix Location
- File: `src/combos/endboard_evaluator.py`
- Change `has_s_tier` boolean to `s_tier_count` integer
- Update comparison logic in search beam ranking

---

## Priority 2: Engraver Resource Conflict

### Problem
With only 1 Engraver in hand, Desirae line and Caesar line are mutually exclusive:
- **Desirae line**: Engraver used as fusion material
- **Caesar line**: Engraver needed on field as Level 6 Xyz material

### Options
1. Create fixture with 2 Engravers to test if both lines are reachable
2. Accept that single-Engraver hands cannot achieve S=2
3. Add alternate bodies that can substitute for Engraver in fusion

### Test Fixture
`tests/fixtures/combo_scenarios/fixture_engraver_plus_body.json` - current S=1 result

---

## Verification Commands

```bash
# Run full test suite (expect 87 tests, 1 skipped)
python3 -m unittest discover -s tests

# Effect coverage audit (expect Missing=0)
python3 scripts/audit_effect_coverage.py

# Modeling status audit (expect Stub=0)
python3 scripts/audit_modeling_status.py --fail

# Test S-tier combo search
python3 scripts/combos/search_combo.py \
  --scenario tests/fixtures/combo_scenarios/fixture_engraver_plus_body.json \
  --max-depth 15 --beam-width 20
```

---

## Session 2026-01-23 Completed

- [x] Fabled Lurrie (CID 8092) discard trigger
- [x] Kyrie GY effect: fuse ANY Fiendsmith Fusion (not just Rextremende)
- [x] Kyrie materials: ANY LIGHT Fiend (not Fiendsmith Fusion)
- [x] Necroquip Princess Contact Fusion
- [x] Xyz Level matching validation
- [x] Lacrima CT: send ANY Fiendsmith from deck (not just Paradise)
- [x] Tract: set last_moved_to_gy for Lurrie trigger
- [x] Fixture fixes for Caesar Rank 6
- [x] New fixture: fixture_engraver_plus_body.json
