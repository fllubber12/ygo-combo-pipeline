from __future__ import annotations

from typing import Any

from .state import GameState


def equipped_link_total(card) -> int:
    total = 0
    for equipped in getattr(card, "equipped", []):
        try:
            total += int(equipped.metadata.get("link_rating", 0))
        except (TypeError, ValueError):
            continue
    return total


def game_state_to_endboard_snapshot(state: GameState) -> dict[str, Any]:
    field_cards = [card.name for card in state.field.mz if card]
    field_cards += [card.name for card in state.field.emz if card]

    equipped_link_totals = []
    for card in state.field.mz + state.field.emz:
        if not card:
            continue
        total = equipped_link_total(card)
        if total:
            equipped_link_totals.append({"name": card.name, "total": total})

    return {
        "zones": {
            "hand": [card.name for card in state.hand],
            "field": field_cards,
            "gy": [card.name for card in state.gy],
            "banished": [card.name for card in state.banished],
            "deck": [card.name for card in state.deck],
            "extra": [card.name for card in state.extra],
        },
        "equipped_link_totals": equipped_link_totals,
    }
