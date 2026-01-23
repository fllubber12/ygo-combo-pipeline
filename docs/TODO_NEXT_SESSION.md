# TODO: Next Session (2026-01-23)

## CRITICAL: Hallucination Prevention

**BEFORE reasoning about any card effect:**
1. Read `config/verified_effects.json`
2. If card not in file, fetch from Konami DB first
3. NEVER add restrictions not in official text

**Example of hallucination caught this session:**
- Claimed Engraver e3 had "different name" restriction
- ACTUAL: "shuffle 1 OTHER LIGHT Fiend" + "SS this card" (SS's ITSELF)

## Completed This Session

1. Changed rank_key from boolean to count: `(count_s, count_a, count_b)`
2. Removed early exit in search.py when S-tier found
3. Added `_enumerate_xyz_summons()` to closure passes
4. Verified S=2 scoring works (pre-set fixture achieved S=2)
5. Created `config/verified_effects.json` with Engraver (20196)

## Why S=2 Not Found From Starting Hand

**Root cause: Beam search greed**
- Search finds Desirae+equip (S=1) by using Engravers as Link material
- This consumes Engravers before Caesar Xyz path explored
- Verified: when 2 Engravers pre-placed on field, search DOES make Caesar

**NOT the issue:**
- Xyz enumeration works
- Scoring works (S=2 > S=1)
- Engraver e3 implementation is correct

## Next Session Priority

1. **Complete verified_effects.json** for all library.ydk cards
   - Fetch each from Konami DB
   - Quote exact text
   - No interpretation

2. **Then** decide on search fix:
   - Option A: Multi-path exploration (keep S-1 and setup states)
   - Option B: Potential S-tier heuristic in scoring
   - Option C: Increase beam width significantly

## Key Files Changed

- `src/sim/search.py` - Added `_enumerate_xyz_summons()`, removed early exit
- `src/combos/endboard_evaluator.py` - count_s instead of has_s
- `config/verified_effects.json` - NEW, Engraver only so far

## Test Status

- 87 tests pass
- Fixtures created: `fixture_desirae_plus_caesar_setup.json` (achieves S=2)

## Verification Commands

```bash
python3 -m unittest discover -s tests
python3 scripts/combos/search_combo.py --scenario tests/fixtures/combo_scenarios/fixture_desirae_plus_caesar_setup.json
```
