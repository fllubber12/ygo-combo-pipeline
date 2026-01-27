# Adding New Card Support

## Overview

This guide explains how to add support for new cards to the combo pipeline.

## Prerequisites

- Access to cards.cdb (SQLite card database)
- Card's Lua script from ygopro-scripts
- Understanding of the card's effects

## Steps

### 1. Verify Card Exists in Database

```bash
python scripts/setup_deck.py --lookup "Card Name"
```

### 2. Add to Verified Cards

Add the card to `config/verified_cards.json`:

```json
{
  "card_id": {
    "name": "Card Name",
    "level": 4,
    "atk": 1800,
    "def": 1500,
    "verified": true
  }
}
```

### 3. Update Card Roles (if applicable)

Edit `config/card_roles.json` to classify the card:
- **STARTER**: Cards that begin combos
- **EXTENDER**: Cards that continue combos
- **PAYOFF**: End-goal cards
- **UTILITY**: Supporting cards
- **GARNET**: Cards that should stay in deck

### 4. Run Verification

```bash
python scripts/validate_verified_cards.py
```

### 5. Update Library (if needed)

If the card is part of the test library, add it to `config/locked_library.json`.

## See Also

- [New Card Protocol](NEW_CARD_PROTOCOL.md) - Detailed protocol for card addition
- [Card Data Reference](../reference/CARD_DATA.md) - Card data format
