# Handoff: Combo Enumeration Pipeline

## Session Summary

This document captures the state of the Yu-Gi-Oh combo evaluation pipeline for continuation in a fresh conversation.

## What Was Accomplished

### CFFI Integration - COMPLETE
- Built libygo.dylib (ocgcore engine) with C++ Lua support
- Created Python CFFI bindings for edo9300 API
- Implemented card data reader (from SQLite CDB)
- Implemented script reader (loads official Lua scripts)
- Implemented MSG_IDLE parser (extracts legal actions)
- Successfully executed card effects through the engine

### Card Verification - 12/12 PASS
All Fiendsmith cards verified:
- Scripts load correctly
- Effects enumerate in correct game states
- Effects resolve with correct outcomes

Key fix: Tract passcode corrected to 98567237 (was incorrectly 74875003)

### Research Conclusions
1. **CFFI is the right approach** - Official Lua scripts guarantee correctness
2. **Deterministic enumeration** - Engine provides legal actions, code explores ALL paths
3. **AI only for evaluation** - No AI during path generation, only for ranking final states
4. **Pass at every node** - Every state has "pass" as an option, creating natural terminals

## Current State

### Files Created
- `src/cffi/ocg_bindings.py` - CFFI bindings for ocgcore
- `src/cffi/test_fiendsmith_duel.py` - Working duel with card loading
- `src/cffi/test_full_combo.py` - Combo execution test
- `src/cffi/verify_all_cards.py` - Card verification suite (12/12 passing)
- `src/cffi/build/libygo.dylib` - Compiled engine (2.8MB)
- `docs/ARCHITECTURE_RESEARCH.md` - Full research findings
- `docs/CFFI_PROTOTYPE_PLAN.md` - Build instructions

### Verified Passcodes
```python
CARDS = {
    "Fiendsmith Engraver": 60764609,
    "Lacrima the Crimson Tears": 28803166,
    "Fiendsmith's Tract": 98567237,  # CORRECTED from 74875003
    "Fiendsmith's Sanct": 35552985,
    "Fiendsmith in Paradise": 99989863,
    "Fiendsmith Kyrie": 26434972,
    "Fiendsmith's Desirae": 82135803,
    "Fiendsmith's Requiem": 2463794,
    "Fiendsmith's Sequence": 49867899,
    "Fiendsmith's Lacrima": 46640168,
    "Fiendsmith's Agnumday": 32991300,
    "Fiendsmith's Rextremende": 11464648,
}
```

### Test Status
- 126 unit tests passing (2 skipped)
- 12/12 card verifications passing

### MSG_MOVE Format Discovery
The newer ocgcore uses a 28-byte MSG_MOVE format (not 16 bytes):
- Extra sequence fields between prev_loc and curr_loc
- Different byte ordering for curr_loc (location is in MSB, not byte 1)
- Format: code(4) + prev_loc(4) + prev_seq_ext(4) + curr_loc(4) + curr_seq_ext(4) + reason(4) + extra(4)

## Roadmap for Next Session

### Objective
Exhaustively enumerate all possible action sequences from:
- **Hand:** 1 Engraver + 4 dead cards (discardable only)
- **Deck:** 1+ copy of every card in library
- **Extra Deck:** All extra deck monsters in library

### Phase 1: Setup & Validation
1.1 Confirm card verification still passes
1.2 Create exact starting state configuration
1.3 Understand engine behavior for pass/end phase, triggers, chains

### Phase 2: Enumeration Engine
2.1 Core recursive enumeration loop
2.2 State representation and hashing
2.3 Action representation and recording
2.4 Termination conditions (PASS or no legal actions)

### Phase 3: Data Collection
3.1 Run full enumeration from Engraver-only
3.2 Record: total paths, max depth, branching factor
3.3 Identify patterns in the data

### Phase 4: Evaluation Framework
4.1 Define board state metrics (no AI)
4.2 Define tier criteria (S/A/B/Brick)
4.3 Categorize all terminal states

### Key Principles
1. **No AI during enumeration** - Engine provides actions, code explores all
2. **Record everything** - Filter later, can't recover unrecorded data
3. **Derive rules from data** - Don't assume what's optimal, measure it

## Open Questions for Next Session

1. How does the engine represent "pass/end main phase"?
2. How are triggered effects presented (mandatory vs optional)?
3. How are chain orderings handled for simultaneous triggers?
4. What's MSG_IDLE format when no actions available?
5. What's the actual branching factor from Engraver-only?

## Starting the Next Session

### Quick Verification
```bash
# Verify tests pass
python3 -m unittest discover -s tests 2>&1 | tail -5

# Verify CFFI works
python3 src/cffi/verify_all_cards.py

# Check handoff bundle exists
ls -la handoffs/ | tail -3
```

### First Task
Create the enumeration engine that:
1. Takes a starting state
2. Gets legal actions from MSG_IDLE
3. For each action (including PASS), recursively explores
4. Records all terminal states with their action paths

## Library Cards (Full List)

All cards that should be in deck/extra for enumeration:

### Main Deck
| Card | Passcode | Type |
|------|----------|------|
| Fiendsmith Engraver | 60764609 | LIGHT Fiend Level 6 |
| Lacrima the Crimson Tears | 28803166 | LIGHT Fiend Level 4 |
| Fiendsmith's Tract | 98567237 | Spell |
| Fiendsmith's Sanct | 35552985 | Continuous Trap |
| Fiendsmith in Paradise | 99989863 | Trap |
| Fiendsmith Kyrie | 26434972 | Trap |

### Extra Deck
| Card | Passcode | Type |
|------|----------|------|
| Fiendsmith's Desirae | 82135803 | Fusion Level 9 |
| Fiendsmith's Lacrima | 46640168 | Fusion Level 8 |
| Fiendsmith's Rextremende | 11464648 | Fusion Level 6 |
| Fiendsmith's Requiem | 2463794 | Link-1 |
| Fiendsmith's Sequence | 49867899 | Link-2 |
| Fiendsmith's Agnumday | 32991300 | Link-3 |

## Technical Details

### MSG_IDLE Structure (from parse_idle)
```python
{
    "player": int,
    "summonable": [{"code", "name", "controller", "location", "sequence"}],
    "spsummon": [{"code", "name", "controller", "location", "sequence"}],
    "repos": [...],
    "mset": [...],
    "sset": [...],
    "activatable": [{"code", "name", "controller", "location", "sequence", "desc", "mode"}],
    "to_bp": int,
    "to_ep": int,
    "can_shuffle": int,
}
```

### Response Formats
- Normal Summon: `(index << 16) | 0`
- Special Summon: `(index << 16) | 1`
- Reposition: `(index << 16) | 2`
- Monster Set: `(index << 16) | 3`
- Spell/Trap Set: `(index << 16) | 4`
- Activate Effect: `(index << 16) | 5`
- To Battle Phase: `6`
- To End Phase: `7`
- Shuffle: `8`

### Card Selection Response
```python
# Format: type(i32) + count(u32) + indices(u32...)
data = struct.pack("<iI", 0, len(indices))
for idx in indices:
    data += struct.pack("<I", idx)
```

## Bundle Location

Latest handoff: `handoffs/handoff_YYYYMMDD_HHMMSS.zip`

Run `bash scripts/prepare_handoff.sh` to create fresh bundle before ending session.

## Session Metrics

- Session Duration: Multiple hours across context resets
- Cards Verified: 12/12
- Key Bug Fixes: Tract passcode, MSG_MOVE format parsing
- Code Written: ~2000 lines across CFFI bindings and verification
