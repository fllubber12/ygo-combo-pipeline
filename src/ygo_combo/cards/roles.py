#!/usr/bin/env python3
"""
Card role classification for move ordering and pruning.

Classifies cards into roles (Starter, Extender, Payoff, etc.) to enable:
1. Better move ordering (starters first, then extenders, then payoffs)
2. Pruning (skip extenders if no starter has been activated)
3. Combo pattern recognition

Roles are determined by card effects and deck context. This module supports
both heuristic classification and manual overrides via config.

Usage:
    from card_roles import CardRoleClassifier, CardRole

    classifier = CardRoleClassifier.from_config("config/card_roles.json")
    role = classifier.get_role(60764609)  # Engraver -> STARTER

    # Prioritize actions
    ordered = classifier.prioritize_actions(actions)
"""

from enum import IntEnum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, FrozenSet, Tuple
from pathlib import Path
import json


class CardRole(IntEnum):
    """
    Card role classification for combo sequencing.

    Lower values = higher priority in move ordering.
    """
    STARTER = 1      # Initiates combos (1-card starters, self-activating)
    EXTENDER = 2     # Continues combos (requires setup, adds bodies)
    PAYOFF = 3       # End goals (boss monsters, negates, interaction)
    UTILITY = 4      # Support cards (hand traps, removal, protection)
    GARNET = 5       # Bricks (must be in deck, not hand)
    UNKNOWN = 99     # Not yet classified


@dataclass
class CardClassification:
    """
    Complete classification info for a single card.

    Attributes:
        passcode: Card passcode (unique identifier)
        role: Primary role classification
        tags: Additional descriptive tags (e.g., "tuner", "link_material")
        priority_boost: Adjustment to default role priority (negative = higher)
        notes: Human-readable notes about the card
    """
    passcode: int
    role: CardRole
    tags: FrozenSet[str] = field(default_factory=frozenset)
    priority_boost: int = 0
    notes: str = ""

    def effective_priority(self) -> int:
        """Get effective priority (role value + boost)."""
        return self.role.value + self.priority_boost


@dataclass
class ActionWithRole:
    """
    Action paired with its card's role for sorting.

    Used internally by prioritize_actions().
    """
    action: dict  # Original action dict from idle_data
    role: CardRole
    priority: int
    card_code: int


class CardRoleClassifier:
    """
    Classifies cards into roles for move ordering.

    Supports:
    - Manual classification via config file
    - Heuristic classification based on card properties
    - Runtime classification updates

    Thread-safe after initialization (read-only lookups).
    """

    def __init__(self):
        """Initialize empty classifier."""
        self._classifications: Dict[int, CardClassification] = {}
        self._role_sets: Dict[CardRole, Set[int]] = {role: set() for role in CardRole}

    @classmethod
    def from_config(cls, config_path: Path) -> "CardRoleClassifier":
        """
        Load classifier from JSON config file.

        Config format:
        {
            "cards": {
                "60764609": {
                    "role": "STARTER",
                    "tags": ["fiendsmith", "hand_activatable"],
                    "priority_boost": 0,
                    "notes": "Fiendsmith Engraver - 1-card starter"
                },
                ...
            },
            "default_role": "UNKNOWN"
        }
        """
        classifier = cls()

        if not Path(config_path).exists():
            return classifier

        with open(config_path) as f:
            config = json.load(f)

        for passcode_str, card_data in config.get("cards", {}).items():
            passcode = int(passcode_str)
            role_str = card_data.get("role", "UNKNOWN")
            role = CardRole[role_str] if role_str in CardRole.__members__ else CardRole.UNKNOWN

            classification = CardClassification(
                passcode=passcode,
                role=role,
                tags=frozenset(card_data.get("tags", [])),
                priority_boost=card_data.get("priority_boost", 0),
                notes=card_data.get("notes", ""),
            )
            classifier.add_classification(classification)

        return classifier

    @classmethod
    def from_locked_library(cls, library_path: Path) -> "CardRoleClassifier":
        """
        Create classifier from locked library with heuristic classification.

        Uses card properties from locked_library.json to guess roles:
        - Cards with "hand" activation -> likely STARTER
        - Extra deck monsters -> likely PAYOFF or EXTENDER
        - High-level main deck monsters -> likely GARNET
        """
        classifier = cls()

        if not Path(library_path).exists():
            return classifier

        with open(library_path) as f:
            library = json.load(f)

        for passcode_str, card_data in library.get("cards", {}).items():
            passcode = int(passcode_str)
            role = classifier._heuristic_classify(card_data)

            classification = CardClassification(
                passcode=passcode,
                role=role,
                tags=frozenset(),
                notes=f"Heuristic: {card_data.get('name', 'Unknown')}",
            )
            classifier.add_classification(classification)

        return classifier

    def _heuristic_classify(self, card_data: dict) -> CardRole:
        """
        Heuristic role classification based on card properties.

        This is a best-effort guess; manual config overrides are preferred.
        """
        is_extra = card_data.get("is_extra_deck", False)
        card_type = card_data.get("type", 0)
        level = card_data.get("level", 0)
        name = card_data.get("name", "").lower()

        # Extra deck monsters
        if is_extra:
            # Link monsters with high link rating -> PAYOFF
            link_rating = card_data.get("link_rating", 0)
            if link_rating >= 3:
                return CardRole.PAYOFF
            # Lower link monsters -> EXTENDER (stepping stones)
            return CardRole.EXTENDER

        # Main deck analysis
        # High-level monsters that can't be normal summoned -> GARNET
        if level >= 5 and not self._can_special_summon_self(card_data):
            return CardRole.GARNET

        # Fiendsmith cards are mostly starters
        if "fiendsmith" in name:
            if "engraver" in name or "sequence" in name:
                return CardRole.STARTER
            return CardRole.EXTENDER

        # Default: UNKNOWN (needs manual classification)
        return CardRole.UNKNOWN

    def _can_special_summon_self(self, card_data: dict) -> bool:
        """Check if card can special summon itself (heuristic)."""
        # This would need effect text parsing for accuracy
        # For now, assume extra deck monsters can, main deck high-levels can't
        return card_data.get("is_extra_deck", False)

    def add_classification(self, classification: CardClassification):
        """Add or update a card classification."""
        passcode = classification.passcode

        # Remove from old role set if exists
        if passcode in self._classifications:
            old_role = self._classifications[passcode].role
            self._role_sets[old_role].discard(passcode)

        # Add to new role set
        self._classifications[passcode] = classification
        self._role_sets[classification.role].add(passcode)

    def get_role(self, passcode: int) -> CardRole:
        """Get role for a card (UNKNOWN if not classified)."""
        if passcode in self._classifications:
            return self._classifications[passcode].role
        return CardRole.UNKNOWN

    def get_classification(self, passcode: int) -> Optional[CardClassification]:
        """Get full classification for a card."""
        return self._classifications.get(passcode)

    def get_priority(self, passcode: int) -> int:
        """Get effective priority for a card (lower = higher priority)."""
        classification = self._classifications.get(passcode)
        if classification:
            return classification.effective_priority()
        return CardRole.UNKNOWN.value

    def get_cards_by_role(self, role: CardRole) -> Set[int]:
        """Get all passcodes with a given role."""
        return self._role_sets[role].copy()

    def prioritize_actions(
        self,
        actions: List[dict],
        code_key: str = "code",
    ) -> List[dict]:
        """
        Sort actions by card role priority.

        Args:
            actions: List of action dicts (from idle_data parsing)
            code_key: Key name for card passcode in action dict

        Returns:
            Actions sorted by priority (starters first, then extenders, etc.)
        """
        def get_sort_key(action: dict) -> Tuple[int, int]:
            code = action.get(code_key, 0)
            priority = self.get_priority(code)
            # Secondary sort by passcode for determinism
            return (priority, code)

        return sorted(actions, key=get_sort_key)

    def prioritize_idle_actions(self, idle_data: dict) -> dict:
        """
        Sort all action lists in idle_data by card role priority.

        Args:
            idle_data: Parsed MSG_IDLE data with activatable, spsummon, etc.

        Returns:
            New idle_data dict with sorted action lists
        """
        result = dict(idle_data)

        # Sort each action list
        for key in ["activatable", "spsummon", "summonable", "mset", "sset"]:
            if key in result and result[key]:
                result[key] = self.prioritize_actions(result[key])

        return result

    def should_prune_extenders(
        self,
        actions_taken: List[dict],
        code_key: str = "code",
    ) -> bool:
        """
        Check if extender actions should be pruned.

        Heuristic: If no starter has been activated yet, extenders are
        unlikely to lead to good boards. This enables early pruning.

        Args:
            actions_taken: List of actions already taken this path
            code_key: Key name for card passcode in action dict

        Returns:
            True if extenders should be skipped (no starter activated)
        """
        starters = self._role_sets[CardRole.STARTER]

        for action in actions_taken:
            code = action.get(code_key, 0)
            if code in starters:
                return False  # Starter found, don't prune

        # No starter activated -> prune extenders
        return True

    def filter_by_role(
        self,
        actions: List[dict],
        allowed_roles: Set[CardRole],
        code_key: str = "code",
    ) -> List[dict]:
        """
        Filter actions to only include cards with allowed roles.

        Args:
            actions: List of action dicts
            allowed_roles: Set of CardRole values to allow
            code_key: Key name for card passcode in action dict

        Returns:
            Filtered list of actions
        """
        result = []
        for action in actions:
            code = action.get(code_key, 0)
            role = self.get_role(code)
            if role in allowed_roles:
                result.append(action)
        return result

    def stats(self) -> dict:
        """Return classification statistics."""
        return {
            "total_classified": len(self._classifications),
            "by_role": {role.name: len(codes) for role, codes in self._role_sets.items()},
            "unknown_count": len(self._role_sets[CardRole.UNKNOWN]),
        }

    def to_config(self) -> dict:
        """Export classifications to config format."""
        cards = {}
        for passcode, classification in self._classifications.items():
            cards[str(passcode)] = {
                "role": classification.role.name,
                "tags": list(classification.tags),
                "priority_boost": classification.priority_boost,
                "notes": classification.notes,
            }
        return {"cards": cards, "default_role": "UNKNOWN"}

    def save_config(self, config_path: Path):
        """Save classifications to JSON config file."""
        with open(config_path, "w") as f:
            json.dump(self.to_config(), f, indent=2)


# =============================================================================
# FIENDSMITH LIBRARY CLASSIFICATIONS
# =============================================================================

def get_fiendsmith_classifications() -> Dict[int, CardClassification]:
    """
    Pre-defined classifications for the Fiendsmith library.

    These are manually verified role assignments for optimal move ordering.
    """
    return {
        # === STARTERS (1-card combo initiators) ===
        60764609: CardClassification(
            passcode=60764609,
            role=CardRole.STARTER,
            tags=frozenset(["fiendsmith", "hand_activatable", "sends_to_gy"]),
            notes="Fiendsmith Engraver - Primary 1-card starter",
        ),
        49867899: CardClassification(
            passcode=49867899,
            role=CardRole.STARTER,
            tags=frozenset(["fiendsmith", "hand_activatable"]),
            notes="Fiendsmith Sequence - Secondary starter",
        ),

        # === EXTENDERS (require setup, add bodies) ===
        2463794: CardClassification(
            passcode=2463794,
            role=CardRole.EXTENDER,
            tags=frozenset(["fiendsmith", "link", "link1"]),
            notes="Fiendsmith's Requiem - Link-1 extender",
        ),
        35552986: CardClassification(
            passcode=35552986,
            role=CardRole.EXTENDER,
            tags=frozenset(["token"]),
            notes="Fiendsmith Token",
        ),

        # === PAYOFFS (end boards, interaction) ===
        79559912: CardClassification(
            passcode=79559912,
            role=CardRole.PAYOFF,
            tags=frozenset(["boss", "xyz", "rank6", "negate"]),
            priority_boost=-1,  # High priority payoff
            notes="D/D/D Wave High King Caesar - Negates SS effects",
        ),
        29301450: CardClassification(
            passcode=29301450,
            role=CardRole.PAYOFF,
            tags=frozenset(["boss", "link", "link2", "banish"]),
            priority_boost=-1,
            notes="S:P Little Knight - Banishes on response",
        ),
        4731783: CardClassification(
            passcode=4731783,
            role=CardRole.PAYOFF,
            tags=frozenset(["boss", "link", "interaction"]),
            notes="A Bao A Qu - Destruction/banish",
        ),
        32991300: CardClassification(
            passcode=32991300,
            role=CardRole.PAYOFF,
            tags=frozenset(["fiendsmith", "link"]),
            notes="Fiendsmith's Agnumday",
        ),
        82135803: CardClassification(
            passcode=82135803,
            role=CardRole.PAYOFF,
            tags=frozenset(["fiendsmith", "link"]),
            notes="Fiendsmith's Desirae",
        ),
        11464648: CardClassification(
            passcode=11464648,
            role=CardRole.PAYOFF,
            tags=frozenset(["fiendsmith", "link"]),
            notes="Fiendsmith's Rextremende",
        ),
        45409943: CardClassification(
            passcode=45409943,
            role=CardRole.PAYOFF,
            tags=frozenset(["boss", "link"]),
            notes="Luce the Dusk's Dark",
        ),

        # === GARNETS (bricks if drawn) ===
        10000040: CardClassification(
            passcode=10000040,
            role=CardRole.GARNET,
            tags=frozenset(["filler", "brick"]),
            notes="Holactie - Dead card (filler)",
        ),
    }


def create_fiendsmith_classifier() -> CardRoleClassifier:
    """Create a classifier pre-loaded with Fiendsmith classifications."""
    classifier = CardRoleClassifier()
    for classification in get_fiendsmith_classifications().values():
        classifier.add_classification(classification)
    return classifier


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Card Role Classification Tests")
    print("=" * 60)

    # Test 1: Create classifier with Fiendsmith cards
    print("\n1. Fiendsmith classifier:")
    classifier = create_fiendsmith_classifier()
    stats = classifier.stats()
    print(f"   Total classified: {stats['total_classified']}")
    print(f"   By role: {stats['by_role']}")

    # Test 2: Get role for known card
    print("\n2. Role lookups:")
    engraver_role = classifier.get_role(60764609)
    print(f"   Engraver (60764609): {engraver_role.name}")
    assert engraver_role == CardRole.STARTER

    caesar_role = classifier.get_role(79559912)
    print(f"   Caesar (79559912): {caesar_role.name}")
    assert caesar_role == CardRole.PAYOFF

    unknown_role = classifier.get_role(99999999)
    print(f"   Unknown (99999999): {unknown_role.name}")
    assert unknown_role == CardRole.UNKNOWN

    # Test 3: Priority ordering
    print("\n3. Priority ordering:")
    actions = [
        {"code": 79559912, "name": "Caesar"},      # PAYOFF
        {"code": 60764609, "name": "Engraver"},    # STARTER
        {"code": 2463794, "name": "Requiem"},      # EXTENDER
        {"code": 10000040, "name": "Holactie"},    # GARNET
    ]

    sorted_actions = classifier.prioritize_actions(actions)
    print("   Before:", [a["name"] for a in actions])
    print("   After:", [a["name"] for a in sorted_actions])

    # Verify order: STARTER < EXTENDER < PAYOFF < GARNET
    assert sorted_actions[0]["name"] == "Engraver"   # STARTER (1)
    assert sorted_actions[1]["name"] == "Requiem"    # EXTENDER (2)

    # Test 4: Extender pruning
    print("\n4. Extender pruning heuristic:")
    no_starter_actions = [{"code": 2463794}]  # Only extender
    should_prune = classifier.should_prune_extenders(no_starter_actions)
    print(f"   No starter activated, prune extenders: {should_prune}")
    assert should_prune == True

    with_starter_actions = [{"code": 60764609}]  # Starter activated
    should_prune = classifier.should_prune_extenders(with_starter_actions)
    print(f"   Starter activated, prune extenders: {should_prune}")
    assert should_prune == False

    # Test 5: Filter by role
    print("\n5. Filter by role:")
    starters_only = classifier.filter_by_role(
        actions,
        allowed_roles={CardRole.STARTER}
    )
    print(f"   Starters only: {[a['name'] for a in starters_only]}")
    assert len(starters_only) == 1
    assert starters_only[0]["name"] == "Engraver"

    # Test 6: Config export/import
    print("\n6. Config export:")
    config = classifier.to_config()
    print(f"   Exported {len(config['cards'])} cards")

    # Test 7: Get cards by role
    print("\n7. Cards by role:")
    starters = classifier.get_cards_by_role(CardRole.STARTER)
    print(f"   Starters: {starters}")
    assert 60764609 in starters
    assert 49867899 in starters

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
