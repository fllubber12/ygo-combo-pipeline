# New Card Integration Protocol

This document describes the mandatory process for adding new cards to the combo simulation pipeline. Every card must pass through these gates before it can be used in combo search.

## Why This Process Exists

Previous sessions revealed that cards implemented without verification against the official Lua scripts contained bugs:
- Effects activating from wrong locations (hand vs field vs GY)
- Missing field checks (effect worked even when card wasn't on field)
- Incorrect targeting (only player's cards when should include opponent's)
- Wrong OPT tracking

These bugs were only discovered through manual Lua comparison. This protocol prevents such issues.

## The Integration Script

```bash
python3 scripts/add_new_card.py --cid 12345 --passcode 98765432 --name "Card Name"
```

The script enforces a strict gate process:

### Gate 1: Fetch Official Lua Script

The script downloads the card's Lua implementation from ProjectIgnis:
```
https://github.com/ProjectIgnis/CardScripts/blob/master/official/c{PASSCODE}.lua
```

The passcode is the 8-digit number printed on the physical card (NOT the database CID).

**To find passcodes:**
- Search at https://db.ygoprodeck.com/
- Or check https://www.db.yugioh-card.com/

### Gate 2: Verify Effects Against Lua

The script displays the Lua content and requires you to fill in `config/verified_effects.json`:

```json
{
  "12345": {
    "name": "Card Name",
    "card_type": "monster",
    "source": "https://github.com/ProjectIgnis/CardScripts/blob/master/official/c98765432.lua",
    "effects": [
      {
        "id": "e1",
        "location": "hand",
        "effect_type": "ignition",
        "cost": "Discard this card",
        "condition": "",
        "action": "Add 1 'Archetype' Spell/Trap from Deck to hand",
        "opt": "hard_opt",
        "lines": "7-15"
      }
    ]
  }
}
```

**Key Lua patterns to identify:**

| Pattern | Meaning |
|---------|---------|
| `SetRange(LOCATION_HAND)` | Activates from hand |
| `SetRange(LOCATION_MZONE)` | Activates from monster zone (must be on field) |
| `SetRange(LOCATION_GRAVE)` | Activates from GY |
| `SetRange(LOCATION_MZONE\|LOCATION_GRAVE)` | Activates from field OR GY |
| `SetCountLimit(1,id)` | Hard OPT (once per turn, per card name) |
| `SetCountLimit(1,{id,1})` | Hard OPT with different counter |
| `EFFECT_TYPE_IGNITION` | Ignition effect (player's turn, open game state) |
| `EFFECT_TYPE_QUICK_O` | Quick effect (can chain) |
| `EFFECT_TYPE_TRIGGER_O` | Trigger effect (optional) |
| `Cost.SelfDiscard` | Cost: discard this card |
| `Cost.SelfBanish` | Cost: banish this card |

### Gate 3: Create Golden Fixtures

For each effect in verified_effects.json, the script creates a fixture template:

```json
{
  "name": "golden_12345_e1",
  "description": "GOLDEN: Card Name e1 - Add Spell/Trap from Deck",
  "lua_reference": "c98765432.lua lines 7-15",
  "test": {
    "effect_id": "card_e1_search",
    "preconditions": ["Card in hand", "Target in deck"],
    "expected_action_count_min": 1,
    "expected_outcome": {"card_location": "gy", "target_location": "hand"}
  },
  "state": {
    "zones": {
      "hand": [{"cid": "12345", "name": "Card Name"}],
      "deck": [{"cid": "TARGET", "name": "Target Card"}],
      ...
    }
  }
}
```

**You must fill in:**
1. The state with minimal cards needed for the effect
2. The expected outcome after applying the effect
3. Any required events/triggers

### Gate 4: Implement Effect Class

Create the Python implementation:

```python
class CardNameEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions = []

        # Check OPT
        if state.opt_used.get("12345:e1"):
            return actions

        # Check location (MUST match Lua SetRange)
        for hand_index, card in enumerate(state.hand):
            if card.cid != "12345":
                continue
            # Enumerate valid targets
            for deck_index, target in enumerate(state.deck):
                if is_valid_target(target):
                    actions.append(EffectAction(
                        cid="12345",
                        name=card.name,
                        effect_id="card_e1_search",
                        params={"hand_index": hand_index, "deck_index": deck_index}
                    ))

        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        # Implement the effect
        ...
```

**Register in registry.py:**
```python
EFFECT_REGISTRY["12345"] = CardNameEffect()
```

### Gate 5: Run Tests

The script runs:
1. Full test suite: `python3 -m unittest discover -s tests`
2. Validation framework: `python3 scripts/validate_effects_comprehensive.py`

All tests must pass before the card is considered integrated.

## Manual Process (Without Script)

If you need to add a card manually, follow these steps:

### Step 1: Get the Lua

```bash
# Find passcode at db.ygoprodeck.com
curl -o reports/verified_lua/c{PASSCODE}.lua \
  https://raw.githubusercontent.com/ProjectIgnis/CardScripts/master/official/c{PASSCODE}.lua
```

### Step 2: Analyze the Lua

Read the script and identify:
- What effects does the card have?
- Where does each effect activate from? (hand, field, GY, banished)
- What is the effect type? (ignition, trigger, quick, continuous)
- What are the costs and conditions?
- Is it once per turn? How is OPT tracked?

### Step 3: Update verified_effects.json

Add an entry with all effects documented.

### Step 4: Create Golden Fixture

Create `tests/fixtures/combo_scenarios/golden/golden_{CID}_{effect_id}.json`

### Step 5: Implement and Test

1. Create effect class
2. Register in registry
3. Run tests
4. Run validation

## Common Pitfalls

### 1. Wrong Location Check

**Bug:** Effect enumerates even when card isn't on field
**Lua tells you:** `e1:SetRange(LOCATION_MZONE)` means card MUST be on field

### 2. Missing Field/GY Dual Location

**Bug:** Effect only works from GY, but Lua says both
**Lua tells you:** `SetRange(LOCATION_MZONE|LOCATION_GRAVE)` means both locations work

### 3. Incorrect OPT Tracking

**Bug:** Using wrong OPT key or not tracking at all
**Lua tells you:** `SetCountLimit(1,id)` vs `SetCountLimit(1,{id,1})` use different counters

### 4. Missing Trigger Conditions

**Bug:** Trigger effect works without the trigger event
**Lua tells you:** Check `SetCode(EVENT_*)` for what triggers the effect

## Verification Checklist

Before marking a card as complete:

- [ ] Lua script downloaded and reviewed
- [ ] All effects documented in verified_effects.json
- [ ] Each effect has correct location, type, cost, condition
- [ ] Golden fixtures created and filled in
- [ ] Effect class implemented matching Lua logic
- [ ] Effect registered in registry.py
- [ ] All unit tests pass
- [ ] Validation framework passes
- [ ] Tested in actual combo search

## Files Reference

| File | Purpose |
|------|---------|
| `scripts/add_new_card.py` | Integration script |
| `config/verified_effects.json` | Effect documentation |
| `reports/verified_lua/` | Downloaded Lua scripts |
| `tests/fixtures/combo_scenarios/golden/` | Golden fixtures |
| `src/sim/effects/registry.py` | Effect registration |
| `src/sim/effects/*.py` | Effect implementations |
| `docs/EFFECT_VERIFICATION_CHECKLIST.md` | Detailed verification for core cards |
| `docs/EFFECT_VERIFICATION_REMAINING.md` | Verification for all other cards |
