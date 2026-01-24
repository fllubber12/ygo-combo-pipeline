# TODO Next Session

## Handoff Protocol

At 10% context remaining, run:
```bash
bash scripts/prepare_handoff.sh
```

This will:
1. Run all tests and audits
2. Commit any uncommitted changes
3. Create a timestamped handoff bundle in `handoffs/`
4. Print current status for session notes

## Current State (Updated 2026-01-23)

### Validation Framework (Phase 2 Complete)
- **253/263 tests passing (96%)**
- Rules engine: `src/sim/rules.py`
- Validation script: `scripts/validate_effects_comprehensive.py`
- 10 documented limitations (trap STZ activation, continuous effects, summoning procedures)

### Effect Coverage
- 28 CIDs registered in effect registry
- 25/25 decklist cards modeled
- 0 stubs, 0 missing

### Verified Effects
- ✅ verified_effects.json complete for all 25+ cards
- ✅ Engraver e3: cost is "shuffle OTHER LIGHT Fiend", NO "different name" restriction
- ✅ All effects documented with source verification

### Key Files
- `src/sim/effects/registry.py` - Effect registration and validation
- `src/sim/effects/fiendsmith_effects.py` - Fiendsmith card implementations
- `config/verified_effects.json` - Verified effect metadata
- `tests/` - 92 unit tests

## Next Steps (Priority Order)

1. **Trap STZ iteration** - Currently traps set in STZ don't enumerate when flipped
2. **Continuous effects** - Passive effects don't enumerate actions (by design)
3. **Summoning procedure effects** - Ritual/Fusion from hand need special handling

### Search Optimization (Lower Priority)
- Beam search is greedy, consumes Engravers for Desirae before exploring Caesar path
- S=2 scoring works (verified with pre-set fixture)
- Xyz enumeration added to closure passes
- Potential fixes: heuristic scoring, wider beam, multi-objective

## Quick Commands

```bash
# Run all tests
python3 -m unittest discover -s tests

# Run validation framework
python3 scripts/validate_effects_comprehensive.py

# Run combo search
python3 scripts/combos/search_combo.py --scenario tests/fixtures/combo_scenarios/fixture_engraver_lurrie_optimal.json --max-depth 15 --beam-width 20

# Create handoff
bash scripts/prepare_handoff.sh
```

## Recent Commits
- b83e749: Comprehensive effect validation framework
- 689933c: Add verified_effects.json structure, document Engraver effects
- b075d44: Add Xyz enumeration, fix scoring, create verified_effects.json
- 38eddaa: Fix scoring to count S-tier pieces, remove early exit
