# Baseline Metrics for Regression Testing

**Last Updated:** 2026-01-26
**MAX_PATHS:** 5000
**MAX_DEPTH:** 20

---

## Test Configuration

| Parameter | Value |
|-----------|-------|
| Test Framework | pytest |
| Max Paths | 5000 |
| Max Depth | 20 |
| Python Version | 3.13.7 |

---

## Engraver Hand Baseline

**Hand:** Engraver of the Mark + 4 hand traps (dead cards)
**Card Codes:** `[60764609, 14558127, 14558127, 14558127, 94145021]`

### Enumeration Results

| Metric | Value | Notes |
|--------|-------|-------|
| Terminals Found | 15 | Unique board states |
| Paths Explored | 396 | Total DFS paths |
| Max Depth Seen | 17 | Deepest path explored |

### Transposition Table Stats

| Metric | Value | Notes |
|--------|-------|-------|
| Size | 59 | Entries in table |
| Hits | 107 | Cache lookups that succeeded |
| Misses | 59 | Cache lookups that failed |
| Hit Rate | 64.5% | hits / (hits + misses) |
| Stores | 59 | Total store operations |
| Overwrites | 0 | Entries replaced |
| Evictions | 0 | Eviction cycles triggered |

### Depth Distribution

| Depth | Entries |
|-------|---------|
| 0 | 1 |
| 2 | 6 |
| 4 | 8 |
| 6 | 9 |
| 8 | 18 |
| 9 | 2 |
| 10 | 11 |
| 12 | 2 |
| 14 | 2 |

**Average Depth:** 7.15

### Visit Stats

| Metric | Value |
|--------|-------|
| Max Visits | 10 |
| Avg Visits | 2.81 |

---

## Brick Hand Baseline

**Hand:** All hand traps (no starters)
**Card Codes:** `[14558127, 14558127, 14558127, 94145021, 94145021]`

| Metric | Expected |
|--------|----------|
| Terminals | <= 5 |
| Behavior | Minimal exploration, pass turn |

---

## Regression Thresholds

These thresholds trigger test failures if exceeded:

| Test | Condition | Threshold |
|------|-----------|-----------|
| `test_engraver_hand_terminal_count` | Too few | < 5 |
| `test_engraver_hand_terminal_count` | Too many | > 100 |
| `test_brick_hand_minimal_terminals` | Too many | > 5 |
| `test_paths_explored_reasonable` | Too few | < 100 |
| `test_paths_explored_reasonable` | Exceeded limit | > MAX_PATHS |
| `test_transposition_table_has_hits` | No caching | hits == 0 |
| `test_no_evictions_under_limit` | Unexpected evictions | evictions > 0 |

---

## Running Regression Tests

```bash
# Set environment variable
export YGOPRO_SCRIPTS_PATH=/path/to/ygopro-scripts

# Run all regression tests
python -m pytest tests/regression/ -v

# Run with timing
python -m pytest tests/regression/ -v --durations=0
```

---

## Notes

1. **Determinism:** Same hand always produces same terminal count
2. **Gold Standard:** The full A Bao A Qu + Caesar combo is NOT found due to SELECT_SUM_CANCEL backtracking bug (pre-existing issue documented in ARCHITECTURE_DECISION_RESEARCH.md)
3. **Performance:** Full test suite runs in ~110 seconds with MAX_PATHS=5000
