# Troubleshooting

## Common Issues

### Engine Initialization Fails

**Symptom:** `FileNotFoundError` or `OSError` when creating duel.

**Solution:**
1. Ensure `YGOPRO_SCRIPTS_PATH` environment variable is set:
   ```bash
   export YGOPRO_SCRIPTS_PATH=/path/to/ygopro-core/scripts
   ```
2. Verify `cards.cdb` exists in project root
3. Verify `libygo.dylib` (or `.so`/`.dll`) exists in `src/cffi/build/`

### Card Not Found

**Symptom:** `KeyError` or `Card not found` error.

**Solution:**
1. Verify card exists in `cards.cdb`:
   ```bash
   sqlite3 cards.cdb "SELECT id, name FROM texts WHERE name LIKE '%Card Name%'"
   ```
2. Add card to `config/verified_cards.json` if needed
3. Check for typos in card name

### Infinite Loop in Enumeration

**Symptom:** Enumeration never terminates.

**Solution:**
1. This usually indicates a backtracking bug
2. Check if SELECT_SUM_CANCEL is being handled properly
3. Verify failed choices are being tracked
4. Enable debug logging to trace the search path

### Test Import Errors

**Symptom:** `ModuleNotFoundError` when running tests.

**Solution:**
1. Ensure you're in the project root directory
2. Run tests with `python -m pytest tests/` (not just `pytest`)
3. Verify `tests/conftest.py` adds `src/cffi` to path

### Pre-commit Hook Fails

**Symptom:** Commit rejected with validation error.

**Solution:**
1. **Checksum mismatch:** Run `python scripts/generate_lock_checksum.py` after modifying `verified_cards.json`
2. **Library validation:** Check `config/locked_library.json` for invalid cards
3. **Syntax error:** Fix Python syntax in modified files

### Memory Issues

**Symptom:** `MemoryError` or system slowdown.

**Solution:**
1. Reduce `max_depth` in search configuration
2. Enable transposition table size limits
3. Use iterative deepening instead of pure DFS
4. Consider parallel search with fewer workers

## Debug Logging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or for specific modules:

```python
logging.getLogger('combo_enumeration').setLevel(logging.DEBUG)
```

## Getting Help

1. Check the [Decision Log](../architecture/DECISION_LOG.md) for design rationale
2. Review [Message Handlers](../reference/MESSAGE_HANDLERS.md) for MSG_* handling
3. See [handoffs](../handoffs/) for session context
