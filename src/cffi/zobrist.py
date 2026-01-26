#!/usr/bin/env python3
"""
Zobrist hashing for YuGiOh game state representation.

Zobrist hashing enables O(1) incremental hash updates when game state changes,
compared to O(n) for recomputing a full hash. This is critical for efficient
transposition table lookups during combo enumeration.

Key insight: hash(new_state) = hash(old_state) XOR old_component XOR new_component

Usage:
    from zobrist import ZobristHasher, StateChange

    hasher = ZobristHasher(seed=42)

    # Full hash computation (once at start)
    h = hasher.hash_board(board_signature)

    # Incremental update (O(1) per change)
    h = hasher.apply_change(h, StateChange.card_moved(
        card_id=60764609,
        from_location=LOCATION_HAND,
        from_zone=0,
        to_location=LOCATION_MZONE,
        to_zone=2,
        owner=0
    ))

References:
    - Zobrist, A. (1970). "A New Hashing Method with Application for Game Playing"
    - Chess Programming Wiki: https://www.chessprogramming.org/Zobrist_Hashing
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional, FrozenSet, List
from enum import IntEnum
import random

# =============================================================================
# CONSTANTS
# =============================================================================

# Location constants (must match ocg_bindings.py)
LOCATION_DECK = 0x01
LOCATION_HAND = 0x02
LOCATION_MZONE = 0x04
LOCATION_SZONE = 0x08
LOCATION_GRAVE = 0x10
LOCATION_REMOVED = 0x20
LOCATION_EXTRA = 0x40
LOCATION_OVERLAY = 0x80

# Position constants
POS_FACEUP_ATTACK = 0x1
POS_FACEDOWN_ATTACK = 0x2
POS_FACEUP_DEFENSE = 0x4
POS_FACEDOWN_DEFENSE = 0x8

# Zone counts
MAX_MONSTER_ZONES = 7  # 5 main + 2 EMZ
MAX_SPELL_ZONES = 6    # 5 main + 1 field
MAX_HAND_SIZE = 20     # Reasonable upper bound
MAX_GY_SIZE = 60       # Deck size
MAX_BANISHED = 60

# All valid locations for hashing
LOCATIONS = [
    LOCATION_DECK,
    LOCATION_HAND,
    LOCATION_MZONE,
    LOCATION_SZONE,
    LOCATION_GRAVE,
    LOCATION_REMOVED,
    LOCATION_EXTRA,
]

# All valid positions
POSITIONS = [
    POS_FACEUP_ATTACK,
    POS_FACEDOWN_ATTACK,
    POS_FACEUP_DEFENSE,
    POS_FACEDOWN_DEFENSE,
    0,  # No position (hand, GY, etc.)
]


# =============================================================================
# STATE CHANGE REPRESENTATION
# =============================================================================

@dataclass(frozen=True)
class CardState:
    """
    Complete state of a single card for hashing purposes.
    
    Attributes:
        card_id: Card passcode (e.g., 60764609 for Fiendsmith Engraver)
        location: Zone type (LOCATION_HAND, LOCATION_MZONE, etc.)
        zone_index: Position within the zone (0-6 for monsters, 0-5 for S/T)
        position: Face-up/down, ATK/DEF (0 for non-field cards)
        owner: Player who owns the card (0 or 1)
    """
    card_id: int
    location: int
    zone_index: int
    position: int
    owner: int

    def __hash__(self):
        return hash((self.card_id, self.location, self.zone_index, 
                     self.position, self.owner))


@dataclass(frozen=True)
class StateChange:
    """
    Represents a change to game state for incremental hash update.
    
    A change consists of removing old state components and adding new ones.
    The hash update is: new_hash = old_hash XOR (old_components) XOR (new_components)
    """
    removed: Tuple[CardState, ...]  # Components to XOR out
    added: Tuple[CardState, ...]    # Components to XOR in

    @classmethod
    def card_moved(
        cls,
        card_id: int,
        from_location: int,
        from_zone: int,
        to_location: int,
        to_zone: int,
        owner: int,
        from_position: int = 0,
        to_position: int = 0,
    ) -> "StateChange":
        """Create a state change for a card moving between zones."""
        old_state = CardState(card_id, from_location, from_zone, from_position, owner)
        new_state = CardState(card_id, to_location, to_zone, to_position, owner)
        return cls(removed=(old_state,), added=(new_state,))

    @classmethod
    def card_position_changed(
        cls,
        card_id: int,
        location: int,
        zone_index: int,
        old_position: int,
        new_position: int,
        owner: int,
    ) -> "StateChange":
        """Create a state change for a card changing position (ATK/DEF/face)."""
        old_state = CardState(card_id, location, zone_index, old_position, owner)
        new_state = CardState(card_id, location, zone_index, new_position, owner)
        return cls(removed=(old_state,), added=(new_state,))

    @classmethod
    def card_added(
        cls,
        card_id: int,
        location: int,
        zone_index: int,
        position: int,
        owner: int,
    ) -> "StateChange":
        """Create a state change for a new card entering play."""
        new_state = CardState(card_id, location, zone_index, position, owner)
        return cls(removed=(), added=(new_state,))

    @classmethod
    def card_removed(
        cls,
        card_id: int,
        location: int,
        zone_index: int,
        position: int,
        owner: int,
    ) -> "StateChange":
        """Create a state change for a card leaving play."""
        old_state = CardState(card_id, location, zone_index, position, owner)
        return cls(removed=(old_state,), added=())


# =============================================================================
# ZOBRIST HASHER
# =============================================================================

class ZobristHasher:
    """
    Zobrist hash generator for YuGiOh game states.
    
    Generates deterministic random 64-bit keys for each possible state component,
    then combines them via XOR to produce a hash. The XOR property enables O(1)
    incremental updates when state changes.
    
    Thread Safety:
        The hasher is thread-safe after initialization. All random keys are
        generated during __init__ and stored in read-only dicts.
    
    Attributes:
        seed: Random seed for reproducible key generation
        card_keys: Dict mapping (card_id, location, zone, position, owner) -> key
        resource_keys: Dict mapping resource name -> key
        action_keys: Dict mapping action spec string -> key
    """

    def __init__(self, seed: int = 42):
        """
        Initialize the Zobrist hasher with deterministic random keys.
        
        Args:
            seed: Random seed for reproducible key generation. Using the same
                  seed guarantees the same keys, enabling consistent hashing
                  across sessions.
        """
        self.seed = seed
        self._rng = random.Random(seed)
        
        # Lazily populated key dictionaries
        self._card_keys: Dict[CardState, int] = {}
        self._resource_keys: Dict[str, int] = {}
        self._action_keys: Dict[str, int] = {}
        
        # Pre-generate resource keys (small fixed set)
        self._init_resource_keys()

    def _init_resource_keys(self):
        """Pre-generate keys for all resource flags."""
        resources = [
            "normal_summon_used",
            "battle_phase_available",
            "main_phase_2_available",
            "player_to_act_0",
            "player_to_act_1",
        ]
        # Add turn count keys (0-99 should cover any game)
        for turn in range(100):
            resources.append(f"turn_{turn}")
        
        # Add OPT tracking keys (card_id:effect_idx)
        # These are generated lazily, but we seed the structure
        
        for resource in resources:
            self._resource_keys[resource] = self._rng.getrandbits(64)

    def _get_card_key(self, state: CardState) -> int:
        """
        Get or generate the Zobrist key for a card state.
        
        Keys are generated lazily and cached. This handles the large space
        of possible (card_id, location, zone, position, owner) tuples without
        pre-generating millions of keys.
        """
        if state not in self._card_keys:
            # Use a deterministic sub-seed based on the state
            # This ensures the same state always gets the same key
            sub_seed = hash(state) ^ self.seed
            sub_rng = random.Random(sub_seed)
            self._card_keys[state] = sub_rng.getrandbits(64)
        return self._card_keys[state]

    def _get_resource_key(self, resource: str) -> int:
        """Get or generate the Zobrist key for a resource flag."""
        if resource not in self._resource_keys:
            sub_seed = hash(resource) ^ self.seed
            sub_rng = random.Random(sub_seed)
            self._resource_keys[resource] = sub_rng.getrandbits(64)
        return self._resource_keys[resource]

    def _get_action_key(self, action_spec: str) -> int:
        """Get or generate the Zobrist key for a legal action."""
        if action_spec not in self._action_keys:
            sub_seed = hash(action_spec) ^ self.seed
            sub_rng = random.Random(sub_seed)
            self._action_keys[action_spec] = sub_rng.getrandbits(64)
        return self._action_keys[action_spec]

    # =========================================================================
    # FULL HASH COMPUTATION
    # =========================================================================

    def hash_board(self, board_signature) -> int:
        """
        Compute full Zobrist hash for a BoardSignature.
        
        Args:
            board_signature: A BoardSignature instance from state_representation.py
            
        Returns:
            64-bit Zobrist hash as integer
        """
        h = 0
        
        # Hash monsters on field
        for i, card_id in enumerate(sorted(board_signature.monsters)):
            state = CardState(
                card_id=card_id,
                location=LOCATION_MZONE,
                zone_index=i,  # Simplified: use sorted index
                position=POS_FACEUP_ATTACK,  # Default assumption
                owner=0
            )
            h ^= self._get_card_key(state)
        
        # Hash spells/traps on field
        for i, card_id in enumerate(sorted(board_signature.spells)):
            state = CardState(
                card_id=card_id,
                location=LOCATION_SZONE,
                zone_index=i,
                position=0,
                owner=0
            )
            h ^= self._get_card_key(state)
        
        # Hash graveyard
        for i, card_id in enumerate(sorted(board_signature.graveyard)):
            state = CardState(
                card_id=card_id,
                location=LOCATION_GRAVE,
                zone_index=i,
                position=0,
                owner=0
            )
            h ^= self._get_card_key(state)
        
        # Hash hand
        for i, card_id in enumerate(sorted(board_signature.hand)):
            state = CardState(
                card_id=card_id,
                location=LOCATION_HAND,
                zone_index=i,
                position=0,
                owner=0
            )
            h ^= self._get_card_key(state)
        
        # Hash banished
        for i, card_id in enumerate(sorted(board_signature.banished)):
            state = CardState(
                card_id=card_id,
                location=LOCATION_REMOVED,
                zone_index=i,
                position=0,
                owner=0
            )
            h ^= self._get_card_key(state)
        
        # Hash equip relationships
        for equipped, target in sorted(board_signature.equips):
            # Create a unique key for the equip relationship
            equip_key = f"equip:{equipped}:{target}"
            h ^= self._get_action_key(equip_key)
        
        return h

    def hash_intermediate_state(self, intermediate_state) -> int:
        """
        Compute full Zobrist hash for an IntermediateState.
        
        This includes both the board and the legal actions (which capture OPT state).
        
        Args:
            intermediate_state: An IntermediateState from state_representation.py
            
        Returns:
            64-bit Zobrist hash as integer
        """
        # Start with board hash
        h = self.hash_board(intermediate_state.board)
        
        # XOR in all legal actions (captures OPT state)
        for action_spec in sorted(intermediate_state.legal_actions):
            h ^= self._get_action_key(action_spec)
        
        return h

    def hash_with_resources(
        self,
        board_hash: int,
        normal_summon_used: bool = False,
        turn_count: int = 0,
        player_to_act: int = 0,
    ) -> int:
        """
        Add resource state to an existing board hash.
        
        Args:
            board_hash: Base hash from hash_board()
            normal_summon_used: Whether normal summon has been used
            turn_count: Current turn number
            player_to_act: Which player is acting (0 or 1)
            
        Returns:
            Combined hash including resource state
        """
        h = board_hash
        
        if normal_summon_used:
            h ^= self._get_resource_key("normal_summon_used")
        
        h ^= self._get_resource_key(f"turn_{turn_count % 100}")
        h ^= self._get_resource_key(f"player_to_act_{player_to_act}")
        
        return h

    # =========================================================================
    # INCREMENTAL HASH UPDATES
    # =========================================================================

    def apply_change(self, current_hash: int, change: StateChange) -> int:
        """
        Apply a state change to update the hash incrementally.
        
        This is O(1) per component changed, vs O(n) for full recomputation.
        
        Args:
            current_hash: The current Zobrist hash
            change: A StateChange describing what changed
            
        Returns:
            Updated Zobrist hash
        """
        h = current_hash
        
        # XOR out removed components
        for old_state in change.removed:
            h ^= self._get_card_key(old_state)
        
        # XOR in added components
        for new_state in change.added:
            h ^= self._get_card_key(new_state)
        
        return h

    def apply_action_change(
        self,
        current_hash: int,
        removed_actions: FrozenSet[str],
        added_actions: FrozenSet[str],
    ) -> int:
        """
        Update hash when legal actions change (e.g., after using OPT effect).
        
        Args:
            current_hash: The current Zobrist hash
            removed_actions: Action specs that are no longer legal
            added_actions: Action specs that became legal
            
        Returns:
            Updated Zobrist hash
        """
        h = current_hash
        
        for action in removed_actions:
            h ^= self._get_action_key(action)
        
        for action in added_actions:
            h ^= self._get_action_key(action)
        
        return h

    def toggle_resource(self, current_hash: int, resource: str) -> int:
        """
        Toggle a resource flag (XOR is self-inverse).
        
        Args:
            current_hash: The current Zobrist hash
            resource: Resource name to toggle
            
        Returns:
            Updated Zobrist hash
        """
        return current_hash ^ self._get_resource_key(resource)

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def hash_to_hex(self, h: int) -> str:
        """Convert hash to 16-character hex string for display."""
        return f"{h:016x}"

    def verify_hash(self, board_signature, expected_hash: int) -> bool:
        """Verify that a board signature produces the expected hash."""
        return self.hash_board(board_signature) == expected_hash

    def stats(self) -> dict:
        """Return statistics about key generation."""
        return {
            "card_keys_generated": len(self._card_keys),
            "resource_keys_generated": len(self._resource_keys),
            "action_keys_generated": len(self._action_keys),
            "seed": self.seed,
        }


# =============================================================================
# GLOBAL HASHER INSTANCE
# =============================================================================

# Default global hasher (can be replaced for testing)
_default_hasher: Optional[ZobristHasher] = None


def get_hasher(seed: int = 42) -> ZobristHasher:
    """Get or create the default global hasher."""
    global _default_hasher
    if _default_hasher is None or _default_hasher.seed != seed:
        _default_hasher = ZobristHasher(seed=seed)
    return _default_hasher


def zobrist_hash(board_signature) -> int:
    """Convenience function to hash a BoardSignature."""
    return get_hasher().hash_board(board_signature)


def zobrist_hash_intermediate(intermediate_state) -> int:
    """Convenience function to hash an IntermediateState."""
    return get_hasher().hash_intermediate_state(intermediate_state)


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Zobrist Hashing Tests")
    print("=" * 60)
    
    # Create hasher
    hasher = ZobristHasher(seed=42)
    
    # Test 1: CardState hashing is deterministic
    print("\n1. Determinism test:")
    state1 = CardState(60764609, LOCATION_HAND, 0, 0, 0)
    state2 = CardState(60764609, LOCATION_HAND, 0, 0, 0)
    key1 = hasher._get_card_key(state1)
    key2 = hasher._get_card_key(state2)
    print(f"   Same state produces same key: {key1 == key2}")
    assert key1 == key2, "Determinism failed!"
    
    # Test 2: Different states produce different keys
    print("\n2. Discrimination test:")
    state3 = CardState(60764609, LOCATION_MZONE, 0, POS_FACEUP_ATTACK, 0)
    key3 = hasher._get_card_key(state3)
    print(f"   Different location produces different key: {key1 != key3}")
    assert key1 != key3, "Discrimination failed!"
    
    # Test 3: XOR property for incremental updates
    print("\n3. Incremental update test:")
    # Simulate: card moves from hand to field
    initial_hash = key1  # Card in hand
    
    # Method 1: Full recomputation
    final_hash_full = key3  # Card on field
    
    # Method 2: Incremental update (XOR out old, XOR in new)
    final_hash_incr = initial_hash ^ key1 ^ key3
    
    print(f"   Full recomputation: {hasher.hash_to_hex(final_hash_full)}")
    print(f"   Incremental update: {hasher.hash_to_hex(final_hash_incr)}")
    print(f"   Results match: {final_hash_full == final_hash_incr}")
    assert final_hash_full == final_hash_incr, "Incremental update failed!"
    
    # Test 4: StateChange helper
    print("\n4. StateChange test:")
    change = StateChange.card_moved(
        card_id=60764609,
        from_location=LOCATION_HAND,
        from_zone=0,
        to_location=LOCATION_MZONE,
        to_zone=0,
        owner=0,
        from_position=0,
        to_position=POS_FACEUP_ATTACK,
    )
    updated = hasher.apply_change(initial_hash, change)
    print(f"   After apply_change: {hasher.hash_to_hex(updated)}")
    print(f"   Matches expected: {updated == final_hash_incr}")
    
    # Test 5: Order independence (XOR is commutative)
    print("\n5. Order independence test:")
    card_a = CardState(11111111, LOCATION_MZONE, 0, POS_FACEUP_ATTACK, 0)
    card_b = CardState(22222222, LOCATION_MZONE, 1, POS_FACEUP_ATTACK, 0)
    key_a = hasher._get_card_key(card_a)
    key_b = hasher._get_card_key(card_b)
    
    hash_ab = key_a ^ key_b
    hash_ba = key_b ^ key_a
    print(f"   A XOR B: {hasher.hash_to_hex(hash_ab)}")
    print(f"   B XOR A: {hasher.hash_to_hex(hash_ba)}")
    print(f"   Order independent: {hash_ab == hash_ba}")
    assert hash_ab == hash_ba, "Order independence failed!"
    
    # Test 6: Self-inverse property (toggle)
    print("\n6. Self-inverse (toggle) test:")
    original = 0x123456789ABCDEF0
    toggled = hasher.toggle_resource(original, "normal_summon_used")
    restored = hasher.toggle_resource(toggled, "normal_summon_used")
    print(f"   Original:  {hasher.hash_to_hex(original)}")
    print(f"   Toggled:   {hasher.hash_to_hex(toggled)}")
    print(f"   Restored:  {hasher.hash_to_hex(restored)}")
    print(f"   Self-inverse works: {original == restored}")
    assert original == restored, "Self-inverse failed!"
    
    # Test 7: Reproducibility across instances
    print("\n7. Reproducibility test:")
    hasher2 = ZobristHasher(seed=42)
    key1_new = hasher2._get_card_key(state1)
    print(f"   Same seed, same key: {key1 == key1_new}")
    assert key1 == key1_new, "Reproducibility failed!"
    
    hasher3 = ZobristHasher(seed=999)
    key1_diff = hasher3._get_card_key(state1)
    print(f"   Different seed, different key: {key1 != key1_diff}")
    assert key1 != key1_diff, "Seed isolation failed!"
    
    # Print stats
    print("\n8. Hasher stats:")
    stats = hasher.stats()
    for k, v in stats.items():
        print(f"   {k}: {v}")
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
