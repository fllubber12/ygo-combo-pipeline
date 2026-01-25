# Issues and Fixes Document

> Generated: 2026-01-25
> Purpose: Hand off to Claude Code for implementation

---

## Critical Issues

### Issue 1: MSG_SELECT_OPTION Hardcoded to 2 Options

**File:** `src/cffi/combo_enumeration.py`
**Location:** Lines ~1149-1164 (`_handle_select_option` method)

**Problem:**
```python
def _handle_select_option(self, duel, action_history, msg_data):
    """Handle MSG_SELECT_OPTION - select from multiple options."""
    depth = len(action_history)
    # TODO: Parse option count from msg_data
    # For now, assume 2 options
    for opt in range(2):  # <-- HARDCODED!
```

**Impact:** Will break on cards with 3+ options (some Fiendsmith cards may have multiple effect choices).

**Fix Required:**

1. Add `parse_select_option()` function after `parse_select_unselect_card()` (~line 483):

```python
def parse_select_option(data):
    """Parse MSG_SELECT_OPTION to extract available options.
    
    Format:
    - player (1 byte)
    - count (1 byte)
    - options[] (count * 8 bytes each - u64 desc for each option)
    """
    buf = io.BytesIO(data) if isinstance(data, bytes) else data

    player = read_u8(buf)
    count = read_u8(buf)

    options = []
    for i in range(count):
        desc = read_u64(buf)
        options.append({"index": i, "desc": desc})

    return {
        "player": player,
        "count": count,
        "options": options,
    }
```

2. Add parsing in `_get_messages()` (~line 1281, before the `else` clause):

```python
elif msg_type == MSG_SELECT_OPTION:
    msg_data = parse_select_option(msg_body)
    messages.append((MSG_SELECT_OPTION, msg_data))
```

3. Fix `_handle_select_option()` to use parsed count:

```python
def _handle_select_option(self, duel, action_history, msg_data):
    """Handle MSG_SELECT_OPTION - select from multiple options."""
    depth = len(action_history)
    count = msg_data.get("count", 2)  # Fallback to 2 if parsing failed
    options = msg_data.get("options", [])
    
    self.log(f"SELECT_OPTION: {count} options available", depth)
    
    for opt in range(count):
        desc = options[opt]["desc"] if opt < len(options) else 0
        response = struct.pack("<I", opt)
        action = Action(
            action_type="SELECT_OPTION",
            message_type=MSG_SELECT_OPTION,
            response_value=opt,
            response_bytes=response,
            description=f"Option {opt} (desc={desc})",
        )
        self.log(f"Branch: Option {opt}", depth)
        self._enumerate_recursive(action_history + [action])
```

---

### Issue 2: Circular Import Risk

**File:** `src/cffi/state_representation.py`
**Location:** Lines ~126 and ~215

**Problem:**
```python
def from_engine(cls, lib, duel, capture_func=None) -> "BoardSignature":
    if capture_func is None:
        from combo_enumeration import capture_board_state  # Late import
        capture_func = capture_board_state
```

**Impact:** Works currently but fragile. If import order changes, could cause circular import errors.

**Fix Required:**

Option A (Preferred): Always require `capture_func` parameter:
```python
@classmethod
def from_engine(cls, lib, duel, capture_func) -> "BoardSignature":
    """
    Capture board signature directly from engine.
    
    Args:
        lib: OCG library handle
        duel: Duel pointer
        capture_func: Function to capture board state (lib, duel) -> dict
    """
    if capture_func is None:
        raise ValueError("capture_func is required to avoid circular imports")
    
    board_state = capture_func(lib, duel)
    return cls.from_board_state(board_state)
```

Option B: Move `capture_board_state` to `state_representation.py` (more invasive).

---

## Medium Issues

### Issue 3: Transposition Table Eviction Strategy

**File:** `src/cffi/transposition_table.py`
**Location:** Lines ~38-42

**Problem:**
```python
def _evict(self):
    """Remove least valuable entries when full."""
    # Simple strategy: remove oldest (FIFO)
    keys = list(self.table.keys())
    for key in keys[:len(keys)//10]:  # Remove 10%
        del self.table[key]
```

**Impact:** May evict valuable deep states while keeping shallow ones.

**Fix Required:** Add depth-prioritized eviction:

```python
def _evict(self):
    """Remove least valuable entries when full.
    
    Strategy: Prioritize keeping entries with higher depth_to_terminal
    (those closer to good boards are more valuable to cache).
    """
    if not self.table:
        return
    
    # Sort by depth_to_terminal (ascending) - remove shallow entries first
    sorted_entries = sorted(
        self.table.items(),
        key=lambda x: (x[1].depth_to_terminal, x[1].visit_count)
    )
    
    # Remove bottom 10%
    to_remove = max(1, len(sorted_entries) // 10)
    for key, _ in sorted_entries[:to_remove]:
        del self.table[key]
```

---

### Issue 4: Magic Numbers in Board Evaluation

**File:** `src/cffi/state_representation.py`
**Location:** Lines ~288-310

**Problem:**
```python
# Determine tier
if score >= 100:
    tier = "S"
elif score >= 70:
    tier = "A"
elif score >= 40:
    tier = "B"
elif score >= 20:
    tier = "C"
else:
    tier = "brick"
```

**Impact:** Hard to tune evaluation without code changes.

**Fix Required:** Move thresholds to configuration:

1. Add to `config/evaluation_config.json`:
```json
{
  "tier_thresholds": {
    "S": 100,
    "A": 70,
    "B": 40,
    "C": 20
  },
  "score_weights": {
    "boss_monster": 50,
    "interaction_piece": 30,
    "equipped_link": 20,
    "monster_on_field": 5,
    "fiendsmith_in_gy": 10
  }
}
```

2. Modify `evaluate_board_quality()` to load from config.

---

### Issue 5: No Graceful Shutdown

**File:** `src/cffi/combo_enumeration.py`

**Problem:** No handling for Ctrl+C - partial results are lost.

**Fix Required:** Add signal handler in `main()`:

```python
import signal
import sys

# Global flag for graceful shutdown
_shutdown_requested = False

def signal_handler(signum, frame):
    global _shutdown_requested
    print("\n\nShutdown requested - finishing current path and saving results...")
    _shutdown_requested = True

def main():
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # ... existing code ...
```

Then in `EnumerationEngine._enumerate_recursive()`:
```python
def _enumerate_recursive(self, action_history: List[Action]):
    global _shutdown_requested
    if _shutdown_requested:
        return  # Stop exploring new paths
    
    # ... rest of method ...
```

---

## Minor Issues

### Issue 6: Test File Uses Hardcoded Passcodes

**File:** `src/cffi/test_state.py`

**Problem:** Tests use magic numbers like `79559912` instead of named constants.

**Fix Required:** Import from library or define constants:

```python
# At top of test_state.py
from state_representation import BOSS_MONSTERS

# Or define test constants
CAESAR = 79559912
REQUIEM = 2463794
ENGRAVER = 60764609
SP_LITTLE_KNIGHT = 29301450
```

---

### Issue 7: TranspositionEntry Not Truly Immutable

**File:** `src/cffi/transposition_table.py`
**Location:** Line ~8

**Problem:**
```python
@dataclass
class TranspositionEntry:  # Not frozen, but visit_count is mutated
```

**Fix Required:** Either:
- Make it `@dataclass(frozen=True)` and return new entry on update
- Or document that it's intentionally mutable

---

### Issue 8: Missing Type Hints

**Files:** `src/cffi/combo_enumeration.py`, `src/cffi/transposition_table.py`

**Problem:** Many functions lack type hints.

**Fix Required:** Add type hints to public functions:

```python
# Example fixes
def parse_idle(data: bytes) -> dict: ...
def parse_select_card(data: bytes) -> dict: ...
def build_activate_response(index: int) -> Tuple[int, bytes]: ...
```

---

## Summary Checklist

| Issue | Priority | Estimated Effort |
|-------|----------|------------------|
| MSG_SELECT_OPTION fix | Critical | 15 min |
| Circular import fix | Critical | 5 min |
| Eviction strategy | Medium | 10 min |
| Magic numbers to config | Medium | 20 min |
| Graceful shutdown | Medium | 15 min |
| Test constants | Minor | 5 min |
| TranspositionEntry docs | Minor | 2 min |
| Type hints | Minor | 30 min |

**Total estimated time:** ~1.5 hours

---

## Testing After Fixes

```bash
cd /path/to/project/src/cffi

# Run unit tests
python3 test_state.py

# Quick enumeration test
python3 combo_enumeration.py --max-depth 15 --max-paths 100

# Test graceful shutdown (Ctrl+C during run)
python3 combo_enumeration.py --max-depth 30 --max-paths 5000
# Press Ctrl+C partway through - should save partial results
```
