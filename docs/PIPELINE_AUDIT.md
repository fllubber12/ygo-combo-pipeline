# Pipeline Audit: Card Data Flow

**Audit Date:** 2026-01-26
**Auditor:** Claude Code + Human verification
**Purpose:** Document every file that touches card data and identify gaps between verified data and engine behavior.

---

## 1. Files That Touch Card Data

### Source Files

| File | Card Data Usage | Data Source |
|------|-----------------|-------------|
| `src/cffi/combo_enumeration.py` | Parses MSG_SELECT_SUM, extracts level/sum_param | ygopro-core engine messages |
| `src/cffi/engine_interface.py` | Card code lookup, script loading | cards.cdb, script files |
| `src/cffi/state_representation.py` | BoardSignature with card codes | Engine state queries |
| `src/cffi/card_validator.py` | Validates card attributes | config/verified_cards.json |
| `src/cffi/card_roles.py` | Card role classification | config/card_roles.json |
| `src/cffi/ml_encoding.py` | Card feature encoding | Engine state + cards.cdb |

### Configuration Files

| File | Purpose | Verified? |
|------|---------|-----------|
| `config/locked_library.json` | Deck list with card passcodes | Passcodes verified |
| `config/verified_cards.json` | Human-verified card attributes | **PRIMARY SOURCE** |
| `config/card_roles.json` | Card role classifications | Manually assigned |
| `cards.cdb` | SQLite card database | Official database |

### Script Files

| File | Card Data Usage |
|------|-----------------|
| `scripts/setup_deck.py` | Card lookup from cards.cdb |
| `scripts/validate_engine.py` | Engine validation tests |

---

## 2. Data Flow Diagram

```
                    ┌─────────────────┐
                    │   cards.cdb     │
                    │ (SQLite DB)     │
                    └────────┬────────┘
                             │
                             ▼
┌─────────────────┐    ┌─────────────────┐
│ verified_cards  │◄───│ engine_interface│
│    .json        │    │     .py         │
│ (Human-verified)│    └────────┬────────┘
└────────┬────────┘             │
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│ card_validator  │    │  ygopro-core    │
│     .py         │    │    engine       │
└────────┬────────┘    └────────┬────────┘
         │                      │
         │                      ▼
         │             ┌─────────────────┐
         │             │ combo_enumeration│
         │             │      .py        │
         │             └────────┬────────┘
         │                      │
         └──────────┬───────────┘
                    │
                    ▼
            ┌─────────────────┐
            │   Validation    │
            │   (mismatch?)   │
            └─────────────────┘
```

---

## 3. Message Parsing: Where Card Data Comes From

### MSG_SELECT_SUM (Critical)

**File:** `combo_enumeration.py:826-908`

**Current Format Assumption (14-byte cards, BE header):**
```
Header:
  - player: 1 byte
  - select_mode: 1 byte
  - select_min: 1 byte
  - select_max: 1 byte
  - target_sum: 4 bytes BIG-ENDIAN
  - can_count: 4 bytes BIG-ENDIAN
  - padding: 3 bytes

Card (14 bytes each):
  - code: 4 bytes LE
  - controller: 1 byte
  - location: 1 byte
  - sequence: 4 bytes LE
  - sum_param: 4 bytes LE
```

**Observed Issue:**
```
RAW: 000001010000000100000002000000c1319f0300040000000001000000...
Parsed: Fiendsmith Engraver sum_param=0x00000001 (Level 1)
Expected: sum_param=0x00000006 (Level 6)
```

**Status:** BUG - Engine sends level=1 for Level 6 monsters

### MSG_SELECT_CARD

**File:** `combo_enumeration.py:725-764`

**Format:** Standard 14-byte card format
- No level/sum_param issues observed

### MSG_IDLE

**File:** `combo_enumeration.py:1521-1634`

**Data:** Card codes for activatable effects, special summons
- Uses card codes correctly

---

## 4. Assumptions in the Code

### combo_enumeration.py

| Line | Assumption | Verified? |
|------|------------|-----------|
| 831 | Header uses BIG-ENDIAN for target_sum | Based on hex dump analysis |
| 832 | Card entries are 14 bytes (4-byte sequence) | Based on hex dump analysis |
| 869 | target_sum is at offset 4-7 | Based on hex dump analysis |
| 879 | Cards start at offset 15 | Based on hex dump analysis |

### engine_interface.py

| Line | Assumption | Verified? |
|------|------------|-----------|
| 384-394 | Script files in "official" subdirectory | Verified by file structure |
| 32 | CDB_PATH from paths.py | Verified |

### card_validator.py

| Line | Assumption | Verified? |
|------|------------|-----------|
| 18 | verified_cards.json path relative to module | Verified |
| 179 | CDB stores rank/link in level field with encoding | Documented in ygopro-core |

---

## 5. Gaps Between Verified Data and Engine Behavior

### Critical Gap: SELECT_SUM Level Values

**Verified Data:**
- Fiendsmith Engraver: Level 6
- Fabled Lurrie: Level 1
- D/D/D Wave High King Caesar: Rank 6 (requires 2 Level 6 Fiends)

**Engine Behavior:**
- SELECT_SUM shows `sum_param=0x00000001` for Engraver
- Target sum shows as 1, not 12 (expected for 2x Level 6)
- Caesar Xyz summon SUCCEEDS despite incorrect display values

**Hypothesis:**
1. Engine uses different encoding for sum_param (not raw level)
2. OR the format parsing is misaligned
3. OR this ygopro-core build uses custom sum mechanics

### Minor Gap: Card Names

**Verified Data:** Names from official sources
**Engine Behavior:** Names from cards.cdb `texts` table

**Status:** Should match, but not validated systematically

---

## 6. Validation Commands

### Validate CDB against Verified Data

```bash
python -c "from src.cffi.card_validator import compare_cdb_to_verified; import json; print(json.dumps(compare_cdb_to_verified(), indent=2))"
```

### Check Specific Card in CDB

```bash
sqlite3 cards.cdb "SELECT id, name, level, atk, def FROM datas JOIN texts USING(id) WHERE id = 60764609;"
```

Expected output: `60764609|Fiendsmith Engraver|6|1800|2400`

### Validate SELECT_SUM Parsing

```bash
export YGOPRO_SCRIPTS_PATH=/Users/zacharyhartley/ygopro-scripts
python3 src/cffi/combo_enumeration.py --max-depth 25 --max-paths 50 --verbose 2>&1 | grep -A10 "SELECT_SUM.*Caesar"
```

---

## 7. Recommendations

### Immediate

1. **Verify cards.cdb has correct data**
   ```sql
   SELECT id, name, level FROM datas JOIN texts USING(id)
   WHERE id IN (60764609, 97651498, 79559912);
   ```

2. **Add raw hex logging permanently** (already done in combo_enumeration.py)

3. **Create unit tests for SELECT_SUM parsing** with known hex inputs

### Medium-term

1. **Compare against edo9300/ygopro-core source**
   - Verify MSG_SELECT_SUM format in `field.cpp`
   - Check if sum_param encoding differs from raw level

2. **Add CardValidator integration** to combo_enumeration.py
   - Warn when parsed level doesn't match verified level

### Long-term

1. **Auto-sync verified_cards.json** with cards.cdb
2. **Add API fetcher** for YGOProDeck verification
3. **Create regression tests** for all verified cards

---

## 8. Files Modified in This Audit

| File | Change |
|------|--------|
| `config/verified_cards.json` | Created - human-verified card data |
| `src/cffi/card_validator.py` | Created - validation module |
| `src/cffi/combo_enumeration.py` | Added raw hex debug logging |
| `CLAUDE.md` | Added CARD DATA RULES section |
| `docs/PIPELINE_AUDIT.md` | Created - this document |

---

## 9. Next Steps

1. [ ] Run `compare_cdb_to_verified()` and fix any mismatches
2. [ ] Investigate why sum_param shows 1 instead of 6
3. [ ] Check ygopro-core source for MSG_SELECT_SUM format
4. [ ] Add remaining cards to verified_cards.json
5. [ ] Create automated validation in CI pipeline
