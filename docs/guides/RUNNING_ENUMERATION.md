# Running Combo Enumeration

## Overview

This guide explains how to run combo enumeration to find all valid combo sequences from a starting hand.

## Quick Start

### Basic Enumeration

```python
from src.cffi.combo_enumeration import ComboEnumerator

# Create enumerator
enumerator = ComboEnumerator()

# Define starting hand (card codes)
hand = [60764609, 68304193, 27552504, 31553716, 24094653]  # Example hand

# Run enumeration
results = enumerator.enumerate(hand)

# Print results
for combo in results:
    print(f"Combo: {len(combo['actions'])} steps")
    for action in combo['actions']:
        print(f"  - {action}")
```

### Using Iterative Deepening

For shortest-first combo discovery:

```python
from src.cffi.iterative_deepening import IterativeDeepeningSearch, SearchConfig

config = SearchConfig(
    max_depth=30,
    time_budget_seconds=60.0,
    target_score=100
)

search = IterativeDeepeningSearch(config)
results = search.run(hand)
```

### Parallel Enumeration

For enumerating across multiple starting hands:

```python
from src.cffi.parallel_search import parallel_enumerate

# Enumerate all 5-card combinations
results = parallel_enumerate(
    deck_codes=deck,
    hand_size=5,
    workers=8
)
```

## Configuration

### Search Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `max_depth` | Maximum search depth | 50 |
| `time_budget_seconds` | Time limit | 300 |
| `target_score` | Stop when score reached | None |

### Card Roles

Configure card priorities in `config/card_roles.json`:
- Starters are tried first
- Extenders are deprioritized if no starter activated
- Garnets are avoided when possible

## Output Format

Results are returned as a list of combo dictionaries:

```python
{
    "actions": [
        {"type": "SUMMON", "card": "Card Name", "position": "ATK"},
        {"type": "ACTIVATE", "card": "Card Name", "effect": 1},
        # ...
    ],
    "terminal_state": {
        "field": [...],
        "graveyard": [...],
        "score": 85
    }
}
```

## See Also

- [Search Strategy](../architecture/SEARCH_STRATEGY.md) - How enumeration works
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
