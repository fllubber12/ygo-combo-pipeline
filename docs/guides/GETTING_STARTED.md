# Crystal Beast Fiendsmith Deck Setup Guide

## Overview

This guide walks through setting up your 60-card Crystal Beast Fiendsmith deck for combo analysis using the ygo-combo-pipeline.

## Your Deck Summary

**Main Deck (60 cards):**
- Engine Cards: 47
- Non-Engine (Hand Traps): 13

**Engine Breakdown:**
| Role | Count | Examples |
|------|-------|----------|
| STARTER | ~24 | Engraver, Terrortop, Crystal Bond, Rainbow Bridge |
| EXTENDER | ~18 | Ruby Carbuncle, Fabled Lurrie, Golden Rule |
| PAYOFF | 1 | Awakening of the Crystal Ultimates |
| GARNET | 1 | Rainbow Dragon |
| UTILITY | 3 | TTT, Vaylantz fields |

**Non-Engine (Excluded from Combo Analysis):**
- 3x Ash Blossom & Joyous Spring
- 2x Droll & Lock Bird
- 3x Mulcharmy Fuwalos
- 1x Called by the Grave
- 3x Forbidden Droplet

**Extra Deck Pool (17+ cards for evaluation):**
- Fiendsmith package: Requiem, Sequence, Lacrima, Desirae, Agnumday, Rextremende
- Rank 6: Caesar, Beatrice
- Links: S:P Little Knight, Cherubini
- Crystal Beast: Rainbow Overdragon, Ultimate Crystal Rainbow Dragon Overdrive
- Utility: A Bao A Qu, Aerial Eater, Melomelody, etc.

---

## Setup Steps

### Step 1: Run Card Lookup

```bash
cd ygo-combo-pipeline

# Point to your cards.cdb (from EDOPro or ygopro-core)
python scripts/setup_deck.py --db /path/to/cards.cdb --output-dir config/
```

This creates:
- `config/cb_fiendsmith_library.json` - Card passcodes for engine
- `config/cb_fiendsmith_roles.json` - Card role classifications
- `config/cb_fiendsmith_deck_validated.json` - Full validation report

### Step 2: Review Validation Report

Check for cards marked with errors:
- `NOT_FOUND` - Card name doesn't exist in database
- `MULTIPLE_MATCHES` - Ambiguous name, needs manual selection
- `NAME_MISMATCH` - Found but name differs slightly

Fix any issues by editing the JSON files manually.

### Step 3: Run Engine Validation

```bash
python scripts/validate_engine.py --library config/cb_fiendsmith_library.json
```

Expected output:
```
+ Library Loads
+ Card Counts
+ Passcode Validity
+ Extra Deck Duplicates
+ Key Cards Present
+ Engine Import

Passed: 6/6
```

### Step 4: Run Mini Combo Test

Before full analysis, test with a specific hand:

```bash
# Example: Test Terrortop + Engraver hand
python -c "
from combo_enumeration import EnumerationEngine
# Load with your library
# engine = EnumerationEngine(...)
# Test specific 5-card hand
# results = engine.enumerate_from_hand([card1, card2, card3, card4, card5])
print('Mini test placeholder')
"
```

---

## Analysis Options

### Option A: Sample Analysis (Recommended First)
```bash
python run_analysis.py \
    --library config/cb_fiendsmith_library.json \
    --mode sample \
    --sample-size 100 \
    --max-depth 20
```
- Tests 100 random hands
- Fast: ~5-10 minutes
- Good for consistency estimates

### Option B: Targeted Hand Analysis
```bash
python run_analysis.py \
    --library config/cb_fiendsmith_library.json \
    --mode targeted \
    --hand "Fiendsmith Engraver,Speedroid Terrortop,Crystal Bond,Golden Rule,Rainbow Bridge"
```
- Tests specific hand combinations
- Good for understanding specific lines

### Option C: Full Parallel Analysis
```bash
python run_analysis.py \
    --library config/cb_fiendsmith_library.json \
    --mode full \
    --workers 8 \
    --max-depth 25
```
- Tests all C(47,5) = 1,533,939 engine hands
- Slow: Several hours with 8 workers
- Complete consistency statistics

---

## Expected Outputs

### Combo Lines
```
Hand: [Terrortop, Engraver, Crystal Bond, Golden Rule, Rainbow Bridge]
Line 1 (12 actions, Score: 850, Tier: A):
  1. Activate Rainbow Bridge -> Search Sapphire Pegasus
  2. Normal Summon Sapphire Pegasus -> Place Ruby Carbuncle
  3. Activate Crystal Bond -> Search Crystal Keeper
  4. ...
  -> End Board: Caesar + S:P + Backrow
```

### Consistency Report
```
Hands Tested: 1000
Successful Combos: 847 (84.7%)

Board Quality Distribution:
  S-Tier (3+ negates): 12.3%
  A-Tier (2 negates): 45.2%
  B-Tier (1 negate): 27.2%
  C-Tier (board present): 15.3%
```

### Extra Deck Usage Report
```
Card Usage Frequency (across 847 successful combos):
  Fiendsmith's Requiem: 823 (97.2%) - ESSENTIAL
  Fiendsmith's Sequence: 756 (89.3%) - ESSENTIAL
  D/D/D Wave High King Caesar: 612 (72.3%) - HIGH
  S:P Little Knight: 445 (52.5%) - MEDIUM
  ...
  Evilswarm Exciton Knight: 12 (1.4%) - CUT CANDIDATE
```

---

## Troubleshooting

### "Card not found" errors
1. Check card name spelling exactly matches cards.cdb
2. Some cards have alternate names (e.g., "D/D/D" vs "DDD")
3. Try searching: `python scripts/setup_deck.py --db cards.cdb --lookup "partial name"`

### Engine import errors
1. Make sure you're in the ygo-combo-pipeline directory
2. Check Python path includes src/ygo_combo
3. Verify ygopro-core library is built

### Combo analysis hangs
1. Start with lower --max-depth (15-20)
2. Use --max-paths limit
3. Check for infinite loops in card effects

---

## Files Created

| File | Purpose |
|------|---------|
| `scripts/setup_deck.py` | Card lookup and validation |
| `scripts/validate_engine.py` | Engine functionality tests |
| `cb_fiendsmith_library.json` | Card passcodes for combo engine |
| `cb_fiendsmith_roles.json` | Card role classifications |
| `cb_fiendsmith_deck_validated.json` | Full deck with validation status |

---

## Next Steps After Validation

1. **Run sample analysis** (100-500 hands)
2. **Review combo lines** - Do they make sense?
3. **Check for hallucinations** - Are illegal moves being made?
4. **Identify key decision points** - Where does the engine branch?
5. **Run full analysis** when confident
6. **Analyze extra deck usage** - Which cards can be cut?
