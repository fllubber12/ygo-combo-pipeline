# Test Suite

## Current Tests

### Unit Tests (`tests/unit/`)
- `test_state.py` - State representation, board signatures, transposition table (19 tests)

### Integration Tests (`tests/integration/`)
- `test_fiendsmith_duel.py` - End-to-end duel creation and MSG_IDLE parsing

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage (requires pytest-cov)
python -m pytest tests/ --cov=src/cffi --cov-report=html

# Run specific test file
python -m pytest tests/unit/test_state.py -v
```

## Planned Tests (TODO)

The following test files are planned for future development:

- `test_opt_tracking.py` - Verify OPT (Once Per Turn) tracking via legal actions
- `test_activate_engraver.py` - Test Fiendsmith Engraver activation sequences
- `test_full_combo.py` - End-to-end combo enumeration validation
- `verify_all_cards.py` - Verify all 26 library cards load correctly

## Test Requirements

Tests require:
1. `cards.cdb` - Card database in project root
2. `YGOPRO_SCRIPTS_PATH` environment variable set to ygopro-core scripts directory
3. `libygo.dylib` (or `.so`/`.dll`) built in `src/cffi/build/`
