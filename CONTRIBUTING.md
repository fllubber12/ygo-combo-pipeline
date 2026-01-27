# Contributing to YGO-Combo-Pipeline

## Development Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up the engine:
   ```bash
   export YGOPRO_SCRIPTS_PATH=/path/to/ygopro-core/scripts
   ```
4. Verify setup:
   ```bash
   python -m pytest tests/ -v
   ```

## Code Standards

- Type hints on all public functions
- Docstrings with Args/Returns/Raises
- No bare `except:` - catch specific exceptions
- Constants in SCREAMING_SNAKE_CASE

## Testing

Run tests before submitting changes:

```bash
# All tests
python -m pytest tests/ -v

# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests (require engine)
python -m pytest tests/integration/ -v
```

## Card Data Guidelines

**CRITICAL:** Never guess card data. Always verify against:
1. `config/verified_cards.json` (primary)
2. `cards.cdb` database queries (secondary)
3. Official sources (YGOProDeck API, Yugipedia)

See [CLAUDE.md](CLAUDE.md) for detailed anti-hallucination rules.

## Commit Guidelines

- Write clear commit messages
- Run tests before committing
- Pre-commit hooks validate card data integrity

## Documentation

Documentation lives in `docs/`:
- `docs/architecture/` - System design
- `docs/guides/` - How-to guides
- `docs/reference/` - Technical reference
- `docs/research/` - Background research

See [docs/index.md](docs/index.md) for the full documentation index.
