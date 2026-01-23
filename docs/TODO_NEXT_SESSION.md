# TODO: Next Session

## Critical: Eliminate Hallucinations

### Completed
- ✅ Verified Engraver e3: cost is "shuffle OTHER LIGHT Fiend", NO "different name" restriction
- ✅ Created config/verified_effects.json structure

### Next Session MUST DO FIRST
1. Complete verified_effects.json for ALL 25+ cards in library
   - Fetch each from Konami DB (Lua scripts not publicly accessible)
   - Document every effect with source URL
   - User verifies before proceeding

2. RULE: Claude must NEVER state card effects without quoting verified_effects.json

3. Only after effects are verified: resume search optimization

### Search Issues Identified (but NOT priority)
- Beam search is greedy, consumes Engravers for Desirae before exploring Caesar path
- S=2 scoring works (verified with pre-set fixture)
- Xyz enumeration added to closure passes
- Potential fixes: heuristic scoring, wider beam, multi-objective
- DO NOT work on this until effects are verified

### Commits This Session
- 38eddaa: Fix scoring to count S-tier pieces, remove early exit
- b075d44: Add Xyz enumeration, create verified_effects.json

### Test Status
- 87 tests pass
- S=2 achieved with fixture_desirae_plus_caesar_setup.json
