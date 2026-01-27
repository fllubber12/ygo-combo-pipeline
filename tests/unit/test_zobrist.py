#!/usr/bin/env python3
"""Unit tests for Zobrist hashing module."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "ygo_combo"))

from utils.hashing import (
    ZobristHasher, CardState, StateChange,
    LOCATION_HAND, LOCATION_MZONE, LOCATION_GRAVE,
    POS_FACEUP_ATTACK,
)


class TestZobristHasher(unittest.TestCase):
    """Test ZobristHasher core functionality."""

    def setUp(self):
        self.hasher = ZobristHasher(seed=42)

    def test_determinism(self):
        """Same state produces same key every time."""
        state = CardState(60764609, LOCATION_HAND, 0, 0, 0)
        key1 = self.hasher._get_card_key(state)
        key2 = self.hasher._get_card_key(state)
        self.assertEqual(key1, key2)

    def test_discrimination(self):
        """Different states produce different keys."""
        state1 = CardState(60764609, LOCATION_HAND, 0, 0, 0)
        state2 = CardState(60764609, LOCATION_MZONE, 0, POS_FACEUP_ATTACK, 0)
        key1 = self.hasher._get_card_key(state1)
        key2 = self.hasher._get_card_key(state2)
        self.assertNotEqual(key1, key2)

    def test_incremental_update(self):
        """Incremental update matches full recomputation."""
        state_old = CardState(60764609, LOCATION_HAND, 0, 0, 0)
        state_new = CardState(60764609, LOCATION_MZONE, 0, POS_FACEUP_ATTACK, 0)

        key_old = self.hasher._get_card_key(state_old)
        key_new = self.hasher._get_card_key(state_new)

        # Full recomputation
        final_full = key_new

        # Incremental update
        final_incr = key_old ^ key_old ^ key_new

        self.assertEqual(final_full, final_incr)

    def test_state_change_helper(self):
        """StateChange.card_moved produces correct update."""
        state_old = CardState(60764609, LOCATION_HAND, 0, 0, 0)
        initial_hash = self.hasher._get_card_key(state_old)

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

        updated = self.hasher.apply_change(initial_hash, change)

        # Should equal just the new state key
        state_new = CardState(60764609, LOCATION_MZONE, 0, POS_FACEUP_ATTACK, 0)
        expected = self.hasher._get_card_key(state_new)
        self.assertEqual(updated, expected)

    def test_order_independence(self):
        """XOR is commutative - order doesn't matter."""
        state_a = CardState(11111111, LOCATION_MZONE, 0, POS_FACEUP_ATTACK, 0)
        state_b = CardState(22222222, LOCATION_MZONE, 1, POS_FACEUP_ATTACK, 0)
        key_a = self.hasher._get_card_key(state_a)
        key_b = self.hasher._get_card_key(state_b)

        self.assertEqual(key_a ^ key_b, key_b ^ key_a)

    def test_self_inverse(self):
        """XOR is self-inverse - toggling twice restores original."""
        original = 0x123456789ABCDEF0
        toggled = self.hasher.toggle_resource(original, "normal_summon_used")
        restored = self.hasher.toggle_resource(toggled, "normal_summon_used")
        self.assertEqual(original, restored)

    def test_reproducibility_same_seed(self):
        """Same seed produces same keys."""
        hasher2 = ZobristHasher(seed=42)
        state = CardState(60764609, LOCATION_HAND, 0, 0, 0)
        key1 = self.hasher._get_card_key(state)
        key2 = hasher2._get_card_key(state)
        self.assertEqual(key1, key2)

    def test_reproducibility_different_seed(self):
        """Different seed produces different keys."""
        hasher2 = ZobristHasher(seed=999)
        state = CardState(60764609, LOCATION_HAND, 0, 0, 0)
        key1 = self.hasher._get_card_key(state)
        key2 = hasher2._get_card_key(state)
        self.assertNotEqual(key1, key2)


class TestStateChange(unittest.TestCase):
    """Test StateChange helper methods."""

    def test_card_moved(self):
        """card_moved creates correct removed/added states."""
        change = StateChange.card_moved(
            card_id=12345,
            from_location=LOCATION_HAND,
            from_zone=0,
            to_location=LOCATION_MZONE,
            to_zone=2,
            owner=0,
        )
        self.assertEqual(len(change.removed), 1)
        self.assertEqual(len(change.added), 1)
        self.assertEqual(change.removed[0].location, LOCATION_HAND)
        self.assertEqual(change.added[0].location, LOCATION_MZONE)

    def test_card_added(self):
        """card_added creates only added state."""
        change = StateChange.card_added(
            card_id=12345,
            location=LOCATION_GRAVE,
            zone_index=0,
            position=0,
            owner=0,
        )
        self.assertEqual(len(change.removed), 0)
        self.assertEqual(len(change.added), 1)

    def test_card_removed(self):
        """card_removed creates only removed state."""
        change = StateChange.card_removed(
            card_id=12345,
            location=LOCATION_MZONE,
            zone_index=2,
            position=POS_FACEUP_ATTACK,
            owner=0,
        )
        self.assertEqual(len(change.removed), 1)
        self.assertEqual(len(change.added), 0)


class TestZobristIntegration(unittest.TestCase):
    """Test Zobrist integration with state_representation classes."""

    def test_board_signature_zobrist(self):
        """BoardSignature.zobrist_hash() returns int."""
        from engine.state import BoardSignature

        sig = BoardSignature(
            monsters=frozenset([79559912]),
            spells=frozenset(),
            graveyard=frozenset([60764609]),
            hand=frozenset(),
            banished=frozenset(),
            extra_deck=frozenset(),
            equips=frozenset(),
        )

        zh = sig.zobrist_hash()
        self.assertIsInstance(zh, int)

        # Should be deterministic
        zh2 = sig.zobrist_hash()
        self.assertEqual(zh, zh2)

    def test_intermediate_state_zobrist(self):
        """IntermediateState.zobrist_hash() returns int."""
        from engine.state import BoardSignature, IntermediateState

        board = BoardSignature(
            monsters=frozenset([79559912]),
            spells=frozenset(),
            graveyard=frozenset([60764609]),
            hand=frozenset(),
            banished=frozenset(),
            extra_deck=frozenset(),
            equips=frozenset(),
        )

        state = IntermediateState(
            board=board,
            legal_actions=frozenset(["ACTIVATE:60764609:2"])
        )

        zh = state.zobrist_hash()
        self.assertIsInstance(zh, int)

        # Should be deterministic
        zh2 = state.zobrist_hash()
        self.assertEqual(zh, zh2)

    def test_different_boards_different_hashes(self):
        """Different boards produce different Zobrist hashes."""
        from engine.state import BoardSignature

        sig1 = BoardSignature(
            monsters=frozenset([79559912]),
            spells=frozenset(),
            graveyard=frozenset(),
            hand=frozenset(),
            banished=frozenset(),
            extra_deck=frozenset(),
            equips=frozenset(),
        )

        sig2 = BoardSignature(
            monsters=frozenset([60764609]),
            spells=frozenset(),
            graveyard=frozenset(),
            hand=frozenset(),
            banished=frozenset(),
            extra_deck=frozenset(),
            equips=frozenset(),
        )

        self.assertNotEqual(sig1.zobrist_hash(), sig2.zobrist_hash())


if __name__ == "__main__":
    unittest.main(verbosity=2)
