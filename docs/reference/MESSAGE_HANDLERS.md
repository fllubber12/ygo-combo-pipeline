# Missing Message Handler Audit

## Problem Identified

The combo enumeration engine stops when it encounters unhandled ygopro-core messages:

| Message Type | ID | Status | Required For |
|--------------|-----|--------|--------------|
| MSG_SELECT_SUM | 26 | ❌ MISSING | Xyz summon material selection, Synchro tuning |
| MSG_ANNOUNCE_ATTRIB | 12 | ❌ MISSING | Lacrima declaring attribute |
| MSG_SELECT_TRIBUTE | 21 | ❓ CHECK | Tribute summons |
| MSG_SELECT_UNSELECT_CARD | 23 | ❓ CHECK | Variable selections |
| MSG_ANNOUNCE_RACE | 13 | ❓ CHECK | Cards that declare Type |
| MSG_ANNOUNCE_NUMBER | 14 | ❓ CHECK | Cards that declare a number |

---

## ygopro-core Message Reference

From ygopro-core source (`ocgapi_types.h`):

```cpp
#define MSG_RETRY              1
#define MSG_HINT               2
#define MSG_WAITING            3
#define MSG_START              4
#define MSG_WIN                5
#define MSG_UPDATE_DATA        6
#define MSG_UPDATE_CARD        7
#define MSG_REQUEST_DECK       8
#define MSG_SELECT_BATTLECMD   10
#define MSG_SELECT_IDLECMD     11
#define MSG_SELECT_EFFECTYN    12  // ← This is "select yes/no for effect"
#define MSG_SELECT_YESNO       13
#define MSG_SELECT_OPTION      14
#define MSG_SELECT_CARD        15
#define MSG_SELECT_CHAIN       16
#define MSG_SELECT_PLACE       18
#define MSG_SELECT_POSITION    19
#define MSG_SELECT_TRIBUTE     21
#define MSG_SELECT_COUNTER     22
#define MSG_SELECT_SUM         23  // ← Actually 23, not 26?
#define MSG_SELECT_UNSELECT_CARD 24
#define MSG_SORT_CARD          25
#define MSG_SELECT_RELEASE     26  // ← 26 is SELECT_RELEASE
#define MSG_ANNOUNCE_RACE      140
#define MSG_ANNOUNCE_ATTRIB    141
#define MSG_ANNOUNCE_CARD      142
#define MSG_ANNOUNCE_NUMBER    143
```

**Note:** The message IDs may vary by ygopro-core version. Need to check `ocg_bindings.py` for actual values used.

---

## Message Type 12: MSG_SELECT_EFFECTYN

This is asking "Do you want to activate this optional effect?"

**Format:**
```
[player: 1 byte]
[card_code: 4 bytes]
[controller: 1 byte]
[location: 1 byte]
[sequence: 1 byte]
[position: 1 byte]
[effect_description: 8 bytes]
```

**Handler needed:**
```python
def handle_select_effectyn(self, data):
    """Handle optional effect activation prompt."""
    # Parse the card info
    # Decide: activate (1) or not (0)
    # For combo enumeration: try both branches
    pass
```

---

## Message Type 26: MSG_SELECT_SUM (or MSG_SELECT_RELEASE)

If 26 is MSG_SELECT_RELEASE:
- Used for selecting cards to release (tribute)
- Relevant for Synchro/Link summons

If 26 is MSG_SELECT_SUM:
- Select cards whose levels sum to target
- Used for Xyz summons

**Format (SELECT_SUM):**
```
[player: 1 byte]
[must_select_count: 1 byte]  # min cards
[can_select_count: 1 byte]   # max cards
[target_value: 4 bytes]      # sum target (e.g., 6 for Rank 6 Xyz)
[must_select cards...]       # cards that must be used
[can_select cards...]        # optional cards
```

**Handler needed:**
```python
def handle_select_sum(self, data):
    """Handle sum selection (Xyz materials, etc)."""
    # Parse target sum and available cards
    # Find all valid combinations
    # Branch on each combination
    pass
```

---

## Audit Steps

### Step 1: Identify All Message Types in ocg_bindings.py

```bash
grep -n "MSG_" src/cffi/ocg_bindings.py
```

### Step 2: Check Which Handlers Exist

```bash
grep -n "def.*handle\|def.*process\|MSG_" src/cffi/combo_enumeration.py | head -50
```

### Step 3: Run Enumeration with Message Logging

Add to combo_enumeration.py temporarily:
```python
def process_message(self, msg_type, data):
    print(f"MSG TYPE: {msg_type}")
    # existing handling...
```

### Step 4: Catalog All Messages Hit During Engraver Combo

Run enumeration and log every message type encountered.

---

## Implementation Priority

### P0 - Critical (Blocking Basic Combos)

1. **MSG_SELECT_EFFECTYN (12)** - Optional effect activation
   - Lacrima effect declaration
   - Many other cards

2. **MSG_SELECT_SUM/MSG_SELECT_RELEASE (26)** - Material selection  
   - Xyz summons
   - Link summons with specific materials

### P1 - High (Extended Combos)

3. **MSG_ANNOUNCE_ATTRIB (140/141)** - Declare attribute
   - Lacrima the Crimson Tears

4. **MSG_ANNOUNCE_RACE (140)** - Declare type
   - Some searchers

### P2 - Medium (Full Coverage)

5. **MSG_SELECT_TRIBUTE (21)** - Tribute selection
6. **MSG_SELECT_COUNTER (22)** - Counter manipulation
7. **MSG_SELECT_UNSELECT_CARD (24)** - Variable selections

---

## Test Plan

### Phase 1: Message Discovery
1. Log all message types during Engraver combo
2. Identify which are unhandled
3. Map message ID → message name

### Phase 2: Handler Implementation
1. Implement handlers one at a time
2. Test after each implementation
3. Verify combo depth increases

### Phase 3: Validation
1. Run Engraver combo - should reach Caesar
2. Run Terrortop combo - should make Link plays
3. Run Crystal Bond combo - should place backrow

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/cffi/ocg_bindings.py` | Verify/add message constants |
| `src/cffi/combo_enumeration.py` | Add message handlers |
| `src/cffi/engine_interface.py` | May need parsing helpers |

---

## Next Steps

1. **Run message audit** to get exact list of unhandled messages
2. **Check ocg_bindings.py** for existing message constants
3. **Implement MSG 12 handler** (most likely blocking issue)
4. **Implement MSG 26 handler** (for Xyz summons)
5. **Re-test Engraver combo** - should go deeper
