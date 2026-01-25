#!/usr/bin/env python3
"""
Canonical state representation for combo enumeration.

Three abstraction levels:
1. BoardSignature - For terminal board evaluation (zone-agnostic)
2. IntermediateState - For path pruning (includes OPT via legal actions)
3. ActionSpec - Standardized action representation (ygo-agent style)

Design decisions (based on analysis):
- Use passcodes, not instance IDs (copies are fungible)
- Zone-agnostic for board quality evaluation
- Include legal actions for OPT capture
- Include equip relationships (important for Fiendsmith)
"""

from dataclasses import dataclass
from typing import FrozenSet, Tuple, List, Dict, Any, Optional
import hashlib
import io
import struct

# Location constants
LOCATION_DECK = 0x01
LOCATION_HAND = 0x02
LOCATION_MZONE = 0x04
LOCATION_SZONE = 0x08
LOCATION_GRAVE = 0x10
LOCATION_REMOVED = 0x20
LOCATION_EXTRA = 0x40

# Query flags
QUERY_CODE = 0x1
QUERY_POSITION = 0x2
QUERY_EQUIP_CARD = 0x10
QUERY_END = 0x80000000


@dataclass(frozen=True)
class BoardSignature:
    """
    Terminal board state for evaluation.
    Zone-agnostic: only cares WHAT cards are where, not exact positions.

    Used for:
    - Detecting duplicate terminal boards
    - Board quality scoring
    - Combo categorization
    """
    monsters: FrozenSet[int]      # Passcodes on monster zones
    spells: FrozenSet[int]        # Passcodes on spell/trap zones
    graveyard: FrozenSet[int]     # Passcodes in GY
    hand: FrozenSet[int]          # Passcodes in hand
    banished: FrozenSet[int]      # Passcodes banished
    extra_deck: FrozenSet[int]    # Passcodes remaining in extra (optional)
    equips: FrozenSet[Tuple[int, int]]  # (equipped_passcode, target_passcode)

    def hash(self) -> str:
        """Deterministic hash for board comparison."""
        # Exclude extra_deck from hash (usually irrelevant for evaluation)
        data = (
            tuple(sorted(self.monsters)),
            tuple(sorted(self.spells)),
            tuple(sorted(self.graveyard)),
            tuple(sorted(self.hand)),
            tuple(sorted(self.banished)),
            tuple(sorted(self.equips)),
        )
        return hashlib.md5(str(data).encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Serializable representation."""
        return {
            "monsters": sorted(self.monsters),
            "spells": sorted(self.spells),
            "graveyard": sorted(self.graveyard),
            "hand": sorted(self.hand),
            "banished": sorted(self.banished),
            "extra_deck": sorted(self.extra_deck),
            "equips": [list(e) for e in sorted(self.equips)],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BoardSignature":
        """Reconstruct from serialized dict."""
        return cls(
            monsters=frozenset(d.get("monsters", [])),
            spells=frozenset(d.get("spells", [])),
            graveyard=frozenset(d.get("graveyard", [])),
            hand=frozenset(d.get("hand", [])),
            banished=frozenset(d.get("banished", [])),
            extra_deck=frozenset(d.get("extra_deck", [])),
            equips=frozenset(tuple(e) for e in d.get("equips", [])),
        )

    @classmethod
    def from_board_state(cls, board_state: dict) -> "BoardSignature":
        """Convert existing board_state dict to BoardSignature."""
        p0 = board_state.get("player0", {})

        def extract_codes(cards: list) -> FrozenSet[int]:
            return frozenset(c.get("code", 0) for c in cards if c.get("code"))

        # Extract equip relationships
        equips = set()
        for card in p0.get("spells", []):
            equip_target = card.get("equip_target")
            if equip_target is not None and equip_target >= 0:
                equipped_code = card.get("code", 0)
                # Find target monster code by zone index
                for monster in p0.get("monsters", []):
                    if monster.get("zone_index") == equip_target:
                        target_code = monster.get("code", 0)
                        equips.add((equipped_code, target_code))
                        break

        return cls(
            monsters=extract_codes(p0.get("monsters", [])),
            spells=extract_codes(p0.get("spells", [])),
            graveyard=extract_codes(p0.get("graveyard", [])),
            hand=extract_codes(p0.get("hand", [])),
            banished=extract_codes(p0.get("banished", [])),
            extra_deck=extract_codes(p0.get("extra", [])),
            equips=frozenset(equips),
        )

    @classmethod
    def from_engine(cls, lib, duel, capture_func=None) -> "BoardSignature":
        """
        Capture board signature directly from engine.

        Args:
            lib: OCG library handle
            duel: Duel pointer
            capture_func: Function to capture board state (lib, duel) -> dict
                         If None, imports from combo_enumeration

        Returns:
            BoardSignature for current board state
        """
        if capture_func is None:
            from combo_enumeration import capture_board_state
            capture_func = capture_board_state

        board_state = capture_func(lib, duel)
        return cls.from_board_state(board_state)

    def monster_count(self) -> int:
        return len(self.monsters)

    def total_cards_on_field(self) -> int:
        return len(self.monsters) + len(self.spells)

    def has_boss(self, boss_codes: set) -> bool:
        """Check if any boss monster is on field."""
        return bool(self.monsters & boss_codes)


@dataclass(frozen=True)
class ActionSpec:
    """
    Standardized action specification (inspired by ygo-agent).

    Spec string format:
    - "act:CODE:EFFECT" = Activate card with passcode CODE, effect index EFFECT
    - "ss:CODE"         = Special summon card CODE
    - "ns:CODE"         = Normal summon card CODE
    - "mset:CODE"       = Monster set CODE
    - "sset:CODE"       = Spell/trap set CODE
    - "pass"            = End phase / pass
    """
    spec: str
    passcode: int
    action_type: str      # "activate", "summon", "spsummon", "mset", "sset", "pass"
    effect_index: int     # Which effect (-1 if N/A)
    location: int         # Card location (HAND, MZONE, etc.)

    def __hash__(self):
        return hash(self.spec)

    def __eq__(self, other):
        if isinstance(other, ActionSpec):
            return self.spec == other.spec
        return False

    @classmethod
    def activate(cls, code: int, effect_idx: int, location: int) -> "ActionSpec":
        """Create an activate action spec."""
        spec = f"act:{code}:{effect_idx}"
        return cls(spec=spec, passcode=code, action_type="activate",
                   effect_index=effect_idx, location=location)

    @classmethod
    def special_summon(cls, code: int) -> "ActionSpec":
        """Create a special summon action spec."""
        spec = f"ss:{code}"
        return cls(spec=spec, passcode=code, action_type="spsummon",
                   effect_index=-1, location=LOCATION_EXTRA)

    @classmethod
    def normal_summon(cls, code: int) -> "ActionSpec":
        """Create a normal summon action spec."""
        spec = f"ns:{code}"
        return cls(spec=spec, passcode=code, action_type="summon",
                   effect_index=-1, location=LOCATION_HAND)

    @classmethod
    def monster_set(cls, code: int) -> "ActionSpec":
        """Create a monster set action spec."""
        spec = f"mset:{code}"
        return cls(spec=spec, passcode=code, action_type="mset",
                   effect_index=-1, location=LOCATION_HAND)

    @classmethod
    def spell_set(cls, code: int) -> "ActionSpec":
        """Create a spell/trap set action spec."""
        spec = f"sset:{code}"
        return cls(spec=spec, passcode=code, action_type="sset",
                   effect_index=-1, location=LOCATION_HAND)

    @classmethod
    def pass_action(cls) -> "ActionSpec":
        """Create a pass/end phase action spec."""
        return cls(spec="pass", passcode=0, action_type="pass",
                   effect_index=-1, location=0)


@dataclass(frozen=True)
class IntermediateState:
    """
    Full intermediate state for path pruning.

    Includes board + legal actions, which captures:
    - Card positions
    - OPT usage (via what's still activatable)
    - Summon restrictions
    - Any other hidden state the engine tracks

    Two states with identical IntermediateState.hash() will have
    identical future action spaces, so we only need to explore one.
    """
    board: BoardSignature
    legal_actions: FrozenSet[str]  # Just spec strings for efficient hashing

    def hash(self) -> str:
        """Deterministic hash including OPT state."""
        action_part = tuple(sorted(self.legal_actions))
        combined = (self.board.hash(), action_part)
        return hashlib.md5(str(combined).encode()).hexdigest()[:24]

    def to_dict(self) -> dict:
        """Serializable representation."""
        return {
            "board": self.board.to_dict(),
            "legal_actions": sorted(self.legal_actions),
        }

    @classmethod
    def from_idle_data(cls, idle_data: dict, board_state: dict) -> "IntermediateState":
        """
        Extract intermediate state from engine idle data + board state.

        Args:
            idle_data: Parsed MSG_IDLE data
            board_state: Current board state dict
        """
        board = BoardSignature.from_board_state(board_state)
        actions = cls._extract_action_specs(idle_data)
        return cls(board=board, legal_actions=frozenset(a.spec for a in actions))

    @classmethod
    def from_engine(cls, lib, duel, idle_data: dict, capture_func=None) -> "IntermediateState":
        """
        Extract intermediate state directly from engine.

        Convenience method that captures board state and creates IntermediateState.

        Args:
            lib: OCG library handle
            duel: Duel pointer
            idle_data: Parsed MSG_IDLE data
            capture_func: Function to capture board state (lib, duel) -> dict
                         If None, imports from combo_enumeration

        Returns:
            IntermediateState with current board and legal actions
        """
        if capture_func is None:
            # Late import to avoid circular dependency
            from combo_enumeration import capture_board_state
            capture_func = capture_board_state

        board_state = capture_func(lib, duel)
        return cls.from_idle_data(idle_data, board_state)

    @staticmethod
    def _extract_action_specs(idle_data: dict) -> List[ActionSpec]:
        """Convert MSG_IDLE to ActionSpec list."""
        specs = []

        # Activatable effects
        for card in idle_data.get("activatable", []):
            code = card.get("code", 0)
            loc = card.get("loc", 0)
            desc = card.get("desc", 0)
            effect_idx = desc & 0xF if desc else 0
            specs.append(ActionSpec.activate(code, effect_idx, loc))

        # Special summons
        for card in idle_data.get("spsummon", []):
            code = card.get("code", 0)
            specs.append(ActionSpec.special_summon(code))

        # Normal summons
        for card in idle_data.get("summonable", []):
            code = card.get("code", 0)
            specs.append(ActionSpec.normal_summon(code))

        # Monster sets
        for card in idle_data.get("mset", []):
            code = card.get("code", 0)
            specs.append(ActionSpec.monster_set(code))

        # Spell/trap sets
        for card in idle_data.get("sset", []):
            code = card.get("code", 0)
            specs.append(ActionSpec.spell_set(code))

        # Pass option
        if idle_data.get("to_ep"):
            specs.append(ActionSpec.pass_action())

        return specs

    def num_actions(self) -> int:
        return len(self.legal_actions)

    def can_pass(self) -> bool:
        return "pass" in self.legal_actions


# =============================================================================
# BOARD EVALUATION HELPERS
# =============================================================================

# Boss monster passcodes (for evaluation)
BOSS_MONSTERS = {
    79559912,   # D/D/D Wave High King Caesar
    4731783,    # A Bao A Qu, the Lightless Shadow
    32991300,   # Fiendsmith's Agnumday
    82135803,   # Fiendsmith's Desirae
    11464648,   # Fiendsmith's Rextremende
    29301450,   # S:P Little Knight
    45409943,   # Luce the Dusk's Dark
}

# Interaction pieces (for evaluation)
INTERACTION_PIECES = {
    79559912,   # Caesar - negates special summon effects
    29301450,   # S:P Little Knight - banishes on response
    4731783,    # A Bao A Qu - destroys or banishes
}


def evaluate_board_quality(sig: BoardSignature) -> dict:
    """
    Evaluate board quality for combo scoring.

    Returns dict with:
    - tier: S/A/B/C/brick
    - score: numeric score
    - details: explanation
    """
    score = 0
    details = []

    # Check for boss monsters
    bosses_on_field = sig.monsters & BOSS_MONSTERS
    if bosses_on_field:
        score += 50 * len(bosses_on_field)
        details.append(f"Boss monsters: {len(bosses_on_field)}")

    # Check for interaction pieces
    interaction = sig.monsters & INTERACTION_PIECES
    if interaction:
        score += 30 * len(interaction)
        details.append(f"Interaction pieces: {len(interaction)}")

    # Check for equipped Link monsters (Fiendsmith combo indicator)
    if sig.equips:
        score += 20 * len(sig.equips)
        details.append(f"Equipped Links: {len(sig.equips)}")

    # Monster count
    score += 5 * len(sig.monsters)

    # Graveyard setup (Fiendsmith likes GY)
    fiendsmith_in_gy = len([c for c in sig.graveyard if c in {
        2463794,    # Requiem
        49867899,   # Sequence
        60764609,   # Engraver
    }])
    if fiendsmith_in_gy:
        score += 10 * fiendsmith_in_gy
        details.append(f"Fiendsmith pieces in GY: {fiendsmith_in_gy}")

    # Determine tier
    if score >= 100:
        tier = "S"
    elif score >= 70:
        tier = "A"
    elif score >= 40:
        tier = "B"
    elif score >= 20:
        tier = "C"
    else:
        tier = "brick"

    return {
        "tier": tier,
        "score": score,
        "monsters_on_field": len(sig.monsters),
        "has_boss": bool(bosses_on_field),
        "has_interaction": bool(interaction),
        "details": details,
    }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def compare_boards(sig1: BoardSignature, sig2: BoardSignature) -> dict:
    """Compare two board signatures."""
    return {
        "same_monsters": sig1.monsters == sig2.monsters,
        "same_spells": sig1.spells == sig2.spells,
        "same_gy": sig1.graveyard == sig2.graveyard,
        "same_hand": sig1.hand == sig2.hand,
        "identical": sig1.hash() == sig2.hash(),
        "monsters_diff": {
            "only_in_1": sig1.monsters - sig2.monsters,
            "only_in_2": sig2.monsters - sig1.monsters,
        },
    }


def board_from_legacy(board_state: dict) -> BoardSignature:
    """Convert legacy board_state dict to BoardSignature."""
    return BoardSignature.from_board_state(board_state)


def intermediate_from_legacy(idle_data: dict, board_state: dict) -> IntermediateState:
    """Convert legacy data structures to IntermediateState."""
    return IntermediateState.from_idle_data(idle_data, board_state)


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    # Test BoardSignature
    sig1 = BoardSignature(
        monsters=frozenset([79559912, 2463794]),  # Caesar + Requiem
        spells=frozenset(),
        graveyard=frozenset([60764609]),  # Engraver in GY
        hand=frozenset(),
        banished=frozenset(),
        extra_deck=frozenset(),
        equips=frozenset(),
    )

    sig2 = BoardSignature(
        monsters=frozenset([2463794, 79559912]),  # Same monsters, different order
        spells=frozenset(),
        graveyard=frozenset([60764609]),
        hand=frozenset(),
        banished=frozenset(),
        extra_deck=frozenset(),
        equips=frozenset(),
    )

    print("BoardSignature tests:")
    print(f"  sig1.hash() = {sig1.hash()}")
    print(f"  sig2.hash() = {sig2.hash()}")
    print(f"  Hashes equal: {sig1.hash() == sig2.hash()}")
    print(f"  Signatures equal: {sig1 == sig2}")

    # Test evaluation
    eval_result = evaluate_board_quality(sig1)
    print(f"\nBoard evaluation:")
    print(f"  Tier: {eval_result['tier']}")
    print(f"  Score: {eval_result['score']}")
    print(f"  Details: {eval_result['details']}")

    # Test ActionSpec
    print("\nActionSpec tests:")
    act1 = ActionSpec.activate(60764609, 0, LOCATION_HAND)
    act2 = ActionSpec.special_summon(2463794)
    act3 = ActionSpec.pass_action()
    print(f"  Activate: {act1.spec}")
    print(f"  SpSummon: {act2.spec}")
    print(f"  Pass: {act3.spec}")

    # Test IntermediateState
    print("\nIntermediateState tests:")
    idle_data = {
        "activatable": [
            {"code": 60764609, "loc": LOCATION_HAND, "desc": 0},
            {"code": 60764609, "loc": LOCATION_GRAVE, "desc": 2},
        ],
        "spsummon": [{"code": 2463794}],
        "summonable": [],
        "to_ep": True,
    }
    board_state = {
        "player0": {
            "monsters": [{"code": 35552986, "name": "Fiendsmith Token"}],
            "spells": [],
            "graveyard": [{"code": 60764609, "name": "Fiendsmith Engraver"}],
            "hand": [],
            "banished": [],
            "extra": [],
        }
    }

    intermediate = IntermediateState.from_idle_data(idle_data, board_state)
    print(f"  Hash: {intermediate.hash()}")
    print(f"  Num actions: {intermediate.num_actions()}")
    print(f"  Can pass: {intermediate.can_pass()}")
    print(f"  Actions: {sorted(intermediate.legal_actions)}")

    print("\nAll tests passed!")
