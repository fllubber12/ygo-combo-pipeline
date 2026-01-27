# Enumeration Investigation Handoff

**Date**: 2026-01-26
**Last Commit**: 4c5d3a9
**Purpose**: Handoff to Claude Chat for investigation into combo enumeration path explosion problem

---

## Problem Statement

The combo enumeration cannot find the gold standard combo (Engraver → A Bao A Qu + Caesar) within 50,000 paths. The enumeration finds only 9 unique terminal boards, with ~40,000 duplicate boards skipped.

**Root Cause Identified**: DFS exploration order combined with path explosion means the enumeration exhausts its budget exploring suboptimal branches before reaching the optimal Tract → Lurrie line.

---

## Changes Since Last Web Client Session

### Commits Made

1. **4c5d3a9** - Add gold standard combo: Engraver -> A Bao A Qu + Caesar
   - Created `config/gold_standard_combo.json` - 23-step combo with card IDs, effects, endboard
   - Created `scripts/validate_gold_standard_combo.py` - Validation and display script

2. **f2fe671** - Implement cryptographic locking for verified card data
   - Created `scripts/generate_lock_checksum.py` - SHA256 checksum generation
   - Updated `scripts/validate_verified_cards.py` - Added integrity verification
   - Updated `config/verified_cards.json` - Added lock metadata with checksum
   - Updated `CLAUDE.md` - Added LOCKED CARD DATA policy section

3. **f26678a** - Triple-verified card library: 48 cards, 7 corrections applied

### Uncommitted Changes (Local Only)

1. **`src/cffi/combo_enumeration.py`** - Added `--prioritize-cards` option
   - Allows specifying card passcodes to explore first during SELECT_CARD
   - User decided NOT to use this approach (wants thorough investigation instead)

2. **`scripts/diagnose_tract_path.py`** - Diagnostic script created
   - Confirms Tract IS searchable (at position 2 in SELECT_CARD list)
   - Shows DFS exploration order: Paradise (0) → Sanct (1) → Tract (2) → Kyrie (3)

3. **`CLAUDE.md`** - Added STOP/HALT commands section

---

## Key Findings

### 1. Tract is Searchable
The diagnostic confirmed:
- After activating Engraver, SELECT_CARD shows 4 options
- Tract (98567237) is at position 2 in the list
- The enumeration CAN reach Tract, but DFS explores earlier options first

### 2. DFS Order is the Problem
```
SELECT_CARD list order (determines DFS exploration):
  Position 0: Fiendsmith in Paradise (99989863)
  Position 1: Fiendsmith's Sanct (35552985)
  Position 2: Fiendsmith's Tract (98567237)  <-- Gold standard uses this
  Position 3: Fiendsmith Kyrie (26434972)
```

DFS fully explores Paradise subtree, then Sanct subtree, before ever touching Tract.

### 3. Path Explosion Statistics
From 50,000 path run:
- **9 unique terminal boards** found
- **39,960 duplicate boards** skipped (80%!)
- **Only 3 intermediate states** pruned
- **Max depth**: 49 actions

The low intermediate state pruning (3) suggests paths diverge early and rarely reconverge.

### 4. Current Deduplication Strategy
- **Terminal deduplication**: Uses BoardSignature (monsters, spells, GY, hand, banished, equips)
- **Intermediate deduplication**: Uses IntermediateState (board + legal actions)
- Both use hash-based lookup in transposition table

---

## Questions for Investigation

1. **Should we use BFS instead of DFS?**
   - BFS would explore all branches at each depth level
   - Would find shortest combos first
   - But may have higher memory requirements

2. **Can we improve intermediate state pruning?**
   - Only 3 states pruned out of 50,000 paths suggests paths rarely reconverge
   - Is the IntermediateState hash too specific?
   - Should we use a coarser equivalence relation?

3. **Should we randomize exploration order?**
   - Random selection would give statistical coverage
   - Multiple runs could find different combo lines
   - But loses determinism

4. **Is iterative deepening the answer?**
   - Already implemented in `src/cffi/iterative_deepening.py`
   - Finds shortest combos first
   - But may still miss deep combos due to budget

5. **Can we use card roles for smart pruning?**
   - `src/cffi/card_roles.py` classifies cards as STARTER, EXTENDER, PAYOFF, etc.
   - Could prune branches that activate extenders before starters
   - But may prune valid combo lines

6. **Should we implement Monte Carlo Tree Search (MCTS)?**
   - Would balance exploration vs exploitation
   - Could use board evaluation as reward signal
   - More complex to implement

---

## Gold Standard Combo Reference

**Starting Hand**: 1x Fiendsmith Engraver (60764609)
**Endboard**: A Bao A Qu (4731783) + D/D/D Wave High King Caesar (79559912)

Key steps:
1. Engraver → search Tract (not Sanct!)
2. Tract → add Lurrie, discard Lurrie
3. Lurrie SS from GY
4. Link Lurrie → Requiem
5. ... 19 more steps to A Bao A Qu + Caesar

Full 23-step sequence in `config/gold_standard_combo.json`

---

## Files for Review

### Core Enumeration
- `src/cffi/combo_enumeration.py` - Main DFS enumeration engine
- `src/cffi/state_representation.py` - BoardSignature, IntermediateState classes
- `src/cffi/transposition_table.py` - Memoization cache

### Alternative Search Strategies (Already Implemented)
- `src/cffi/iterative_deepening.py` - Iterative deepening wrapper
- `src/cffi/card_roles.py` - Card role classification for move ordering
- `src/cffi/zobrist.py` - O(1) incremental hashing

### Research Documentation
- `docs/RESEARCH.md` - Game AI research report
- `docs/IMPLEMENTATION_ROADMAP.md` - P0-P4 prioritized improvements

### Gold Standard Reference
- `config/gold_standard_combo.json` - Target combo to find
- `scripts/validate_gold_standard_combo.py` - Combo validation

---

## Environment Setup

```bash
export YGOPRO_SCRIPTS_PATH=/Users/zacharyhartley/ygopro-scripts

# Run enumeration
python3 src/cffi/combo_enumeration.py --max-paths 50000 --max-depth 50

# Validate gold standard
python3 scripts/validate_gold_standard_combo.py --show-steps
```

---

## Next Steps

1. **Web client investigation** - Research best practices for combo game search
2. **Evaluate search strategies** - BFS, MCTS, beam search, etc.
3. **Design improved pruning** - Without privileging specific cards
4. **Implement chosen solution** - After investigation concludes
