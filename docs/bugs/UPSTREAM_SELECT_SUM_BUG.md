# Upstream Bug Report: MSG_SELECT_SUM sum_param Incorrect

**Repository:** https://github.com/Fluorohydride/ygopro-core
**Affected Message:** `MSG_SELECT_SUM`
**Severity:** Medium (workaround available)
**Status:** Draft - Ready to file

---

## Summary

`MSG_SELECT_SUM` messages contain incorrect `sum_param` values for cards. The field consistently shows `1` or `0` instead of the actual card level, making it impossible to correctly enumerate valid material combinations for Xyz/Synchro summons without external card data lookup.

---

## Environment

- **ygopro-core version:** Built from source (commit TBD)
- **Platform:** macOS Darwin 25.2.0 (arm64)
- **Build:** CFFI bindings via `libygo.dylib`
- **Cards tested:** Fiendsmith Engraver (60764609, Level 6)

---

## Expected Behavior

When `MSG_SELECT_SUM` is sent for an Xyz summon (e.g., Beatrice, Lady of the Eternal selecting Level 6 materials), the `sum_param` field for each selectable card should contain the card's level:

```
Card: Fiendsmith Engraver (60764609)
Expected sum_param: 0x00000006 (Level 6)
```

---

## Actual Behavior

The `sum_param` field contains `1` (or occasionally `0`) regardless of the actual card level:

```
Card: Fiendsmith Engraver (60764609)
Actual sum_param: 0x00000001 (shows as Level 1)
```

**Hex dump of MSG_SELECT_SUM message:**
```
Offset  Hex                                       ASCII
0000    00 00 01 02 0c 00 00 00 02 00 00 00 00 00 00  ...............
000f    52 e8 9e 03 00 02 00 00 00 05 00 00 00 01 00  R..............
001d    00 00 ...
        ^^^^^^^^ sum_param = 0x00000001 (should be 0x00000006)
```

---

## Impact

1. **Cannot enumerate valid Xyz/Synchro material combinations** - The algorithm needs correct levels to find combinations that sum to the target (e.g., 6+6=12 for Rank 6)
2. **Requires external workaround** - Must look up card levels from `cards.cdb` or hardcoded data instead of using engine-provided values
3. **May affect other SELECT_SUM use cases** - Ritual tributes, Synchro tuning, etc.

---

## Reproduction Steps

1. Set up a duel with Fiendsmith Engraver (60764609) on field
2. Activate an effect that triggers Xyz summon requiring Level 6 materials
3. Intercept `MSG_SELECT_SUM` message
4. Parse the card entries and inspect `sum_param` field
5. Observe: `sum_param = 1` instead of `sum_param = 6`

**Minimal test case:**
```python
# After receiving MSG_SELECT_SUM for Rank 6 Xyz summon
# Parse card at offset 15 (first card entry)
code = struct.unpack_from('<I', data, 15)[0]      # 60764609 (Engraver) ✓
controller = data[19]                              # 0 ✓
location = data[20]                                # 4 (MZONE) ✓
sequence = struct.unpack_from('<I', data, 21)[0]  # 0 ✓
position = struct.unpack_from('<I', data, 25)[0]  # 5 (ATK position)
sum_param = struct.unpack_from('<I', data, 29)[0] # 1 ✗ (should be 6!)
```

---

## Analysis

Looking at `playerop.cpp` around line 815-818:
```cpp
message->write<uint32_t>(pcard->data.code);
message->write(pcard->get_info_location());
message->write<uint32_t>(pcard->sum_param);
```

The issue appears to be that `pcard->sum_param` is not being populated with the card's level before the message is written. Possible causes:

1. `sum_param` is not initialized from `pcard->data.level`
2. `sum_param` is being set to a flag/mode value instead of level
3. Different encoding scheme that we're not aware of

---

## Current Workaround

We look up card levels from `cards.cdb` when `sum_param` is invalid:

```python
# In parse_select_sum():
level = sum_param & 0xFFFF
if level == 0 or level > 12:
    # Fallback to database lookup
    level = lookup_card_level(code)  # Query cards.cdb
```

This works but:
- Requires external data dependency
- Adds latency to message processing
- May not work for cards not in the local database

---

## Suggested Fix

In the function that populates `MSG_SELECT_SUM` cards (likely in `playerop.cpp` or `field.cpp`), ensure `sum_param` is set to the card's level before writing:

```cpp
// Before writing MSG_SELECT_SUM card entry:
pcard->sum_param = pcard->data.level;  // Or appropriate level calculation
message->write<uint32_t>(pcard->sum_param);
```

For variable-level monsters (e.g., Gagaga Magician), the high 16 bits should contain the alternative level:
```cpp
pcard->sum_param = (alt_level << 16) | primary_level;
```

---

## References

- Our tracking issue: `tests/unit/test_select_sum.py::test_parse_select_sum_basic`
- Related file: `src/ygo_combo/enumeration/parsers.py` (line 483-540)
- Card database: Fiendsmith Engraver verified as Level 6 in `cards.cdb`

---

## Filing Instructions

**To file this bug:**

1. Go to: https://github.com/Fluorohydride/ygopro-core/issues/new
2. Title: `MSG_SELECT_SUM: sum_param field contains incorrect value (always 1)`
3. Copy the Summary, Expected/Actual Behavior, and Reproduction Steps sections
4. Add the ygopro-core version/commit hash being used
5. Tag with: `bug`, `protocol`

---

*Generated: 2026-01-26*
*Project: ygo-combo-pipeline*
