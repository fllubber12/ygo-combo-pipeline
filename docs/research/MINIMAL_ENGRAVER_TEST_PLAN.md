# Minimal Engraver Combo Test Plan

## Objective

Validate the combo enumeration engine works correctly by testing the simplest possible case:
- **Hand:** 1x Fiendsmith Engraver + 4x dead cards (non-engine)
- **Goal:** Verify the engine finds the basic Engraver combo line
- **Success Criteria:** Actions are legal and make game sense

---

## Expected Combo Line (Manual Reference)

The Engraver 1-card combo should roughly follow this line:

```
Starting Hand: [Engraver, Ash, Ash, Ash, Droll]
(4 dead cards simulated with non-engine cards)

Turn 1 Actions:
1. Activate Fiendsmith Engraver (hand)
   -> Send Fiendsmith's Tract from Deck to GY

2. Fiendsmith's Tract triggers in GY
   -> Add Fiendsmith card from Deck to hand (e.g., Lacrima the Crimson Tears)
   OR return Engraver to hand (optional line)

3. Special Summon Fiendsmith's Requiem (Extra Deck)
   -> Use Engraver as Fusion material
   -> Engraver goes to GY

4. Fiendsmith's Requiem effect
   -> Special Summon Fiendsmith Token (ATK 2000)

5. Link Summon Fiendsmith's Sequence (Extra Deck)
   -> Use Token + Requiem as material
   -> Both go to GY

6. Fiendsmith's Sequence effect (on summon)
   -> Send Fiendsmith card from Deck to GY (e.g., Fiendsmith in Paradise)
   -> OR other Fiendsmith effect

7. Continue combo from here...
   -> Sequence can revive Requiem
   -> Make more Link/Xyz plays
   -> End on Caesar, S:P, etc.

Expected End Board (from Engraver alone):
- D/D/D Wave High King Caesar (Rank 6)
- S:P Little Knight (Link 2)
- Possibly backrow or additional monsters
```

---

## Test Configuration

```python
# Minimal test parameters
TEST_HAND = [
    60764609,   # Fiendsmith Engraver
    14558127,   # Ash Blossom (dead)
    14558127,   # Ash Blossom (dead)
    14558127,   # Ash Blossom (dead)
    94145021,   # Droll & Lock Bird (dead)
]

MAX_DEPTH = 15          # Limit actions to catch issues early
MAX_PATHS = 10          # Only explore 10 paths initially
VERBOSE = True          # Print every action for verification
```

---

## What We're Verifying

### Level 1: Engine Doesn't Crash
- [ ] Engine initializes with library
- [ ] Hand is set up correctly
- [ ] Enumeration runs without exceptions

### Level 2: Actions Are Legal
- [ ] Engraver activation is offered as first action
- [ ] Tract is sent from DECK (not hand/field)
- [ ] Tract trigger resolves correctly
- [ ] Requiem fusion summon uses correct materials
- [ ] Token is summoned to correct zone
- [ ] Link materials are sent to GY (not banished)

### Level 3: Combo Makes Sense
- [ ] Actions follow logical combo progression
- [ ] No impossible plays (e.g., summoning without materials)
- [ ] OPT restrictions are respected
- [ ] End board contains expected cards

---

## Red Flags to Watch For

**Hallucination Indicators:**
1. Activating cards not in hand/field
2. Summoning monsters without proper materials
3. Using effects that don't exist on the card
4. Ignoring OPT (Once Per Turn) restrictions
5. Cards appearing from nowhere
6. Illegal zone placements
7. Skipping mandatory effects
8. Wrong card names in output

**Engine Issues:**
1. Infinite loops (same action repeated)
2. No actions offered when legal plays exist
3. Crash on specific card effects
4. Memory errors on deep combos

---

## Test Procedure

### Step 1: Run Minimal Test
```bash
cd ygo-combo-pipeline
python scripts/test_engraver_combo.py
```

### Step 2: Review Output
- Check each action in output
- Verify against expected combo line above
- Note any suspicious actions

### Step 3: Document Issues
If issues found, note:
- Which action was wrong
- What the engine did vs. what it should do
- Any error messages

### Step 4: Iterate or Proceed
- If issues: Debug and re-test
- If clean: Proceed to slightly larger tests

---

## Files Involved

| File | Purpose |
|------|---------|
| `scripts/test_engraver_combo.py` | Minimal test script |
| `config/cb_fiendsmith_library.json` | Card passcodes |
| `src/ygo_combo/combo_enumeration.py` | Core enumeration engine |
| `src/ygo_combo/engine_interface.py` | ygopro-core bindings |

---

## Next Steps After This Test

1. **If PASS:** Test 2-card hands (Engraver + Terrortop)
2. **If FAIL:** Debug specific issue, document, fix
3. **Eventually:** Sample 100 hands, then full analysis

---

## Notes

- We're intentionally starting tiny to catch issues early
- Each action will be printed for manual verification
- The goal is confidence before scale, not speed
