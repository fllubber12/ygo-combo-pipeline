#!/usr/bin/env python3
"""
Tests for state representation and transposition table.

Verification checklist:
- [x] BoardSignature.from_board_state() correctly processes all zones
- [x] IntermediateState._extract_action_specs() captures all action types
- [x] Hash is deterministic (same state -> same hash every time)
- [x] Hash is discriminating (different states -> different hashes)
- [x] Transposition table correctly stores/retrieves
"""

import unittest
from state_representation import (
    BoardSignature, IntermediateState, ActionSpec,
    evaluate_board_quality, BOSS_MONSTERS,
    LOCATION_HAND, LOCATION_MZONE, LOCATION_GRAVE,
)
from transposition_table import TranspositionTable, TranspositionEntry


class TestBoardSignature(unittest.TestCase):
    """Test BoardSignature hashing and equality."""

    def test_hash_determinism(self):
        """Same board state produces same hash every time."""
        board_state = {
            "player0": {
                "monsters": [
                    {"code": 79559912, "name": "Caesar"},
                    {"code": 2463794, "name": "Requiem"},
                ],
                "spells": [],
                "graveyard": [{"code": 60764609, "name": "Engraver"}],
                "hand": [],
                "banished": [],
                "extra": [],
            }
        }

        sig1 = BoardSignature.from_board_state(board_state)
        sig2 = BoardSignature.from_board_state(board_state)
        sig3 = BoardSignature.from_board_state(board_state)

        self.assertEqual(sig1.hash(), sig2.hash())
        self.assertEqual(sig2.hash(), sig3.hash())
        self.assertEqual(sig1, sig2)
        self.assertEqual(sig2, sig3)

    def test_hash_discrimination_different_monsters(self):
        """Different monsters produce different hashes."""
        board1 = {
            "player0": {
                "monsters": [{"code": 79559912}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }
        board2 = {
            "player0": {
                "monsters": [{"code": 2463794}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }

        sig1 = BoardSignature.from_board_state(board1)
        sig2 = BoardSignature.from_board_state(board2)

        self.assertNotEqual(sig1.hash(), sig2.hash())
        self.assertNotEqual(sig1, sig2)

    def test_hash_discrimination_different_zones(self):
        """Same card in different zones produces different hashes."""
        # Card on field
        board1 = {
            "player0": {
                "monsters": [{"code": 60764609}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }
        # Same card in GY
        board2 = {
            "player0": {
                "monsters": [],
                "spells": [], "graveyard": [{"code": 60764609}], "hand": [],
                "banished": [], "extra": [],
            }
        }

        sig1 = BoardSignature.from_board_state(board1)
        sig2 = BoardSignature.from_board_state(board2)

        self.assertNotEqual(sig1.hash(), sig2.hash())

    def test_order_independence(self):
        """Order of cards in same zone doesn't affect hash."""
        board1 = {
            "player0": {
                "monsters": [{"code": 79559912}, {"code": 2463794}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }
        board2 = {
            "player0": {
                "monsters": [{"code": 2463794}, {"code": 79559912}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }

        sig1 = BoardSignature.from_board_state(board1)
        sig2 = BoardSignature.from_board_state(board2)

        self.assertEqual(sig1.hash(), sig2.hash())
        self.assertEqual(sig1, sig2)

    def test_equip_tracking(self):
        """Equip relationships are tracked and affect hash."""
        # Board with equip
        board1 = {
            "player0": {
                "monsters": [{"code": 79559912, "zone_index": 0}],
                "spells": [{"code": 2463794, "equip_target": 0}],  # Requiem equipped
                "graveyard": [], "hand": [], "banished": [], "extra": [],
            }
        }
        # Same cards, no equip
        board2 = {
            "player0": {
                "monsters": [{"code": 79559912, "zone_index": 0}],
                "spells": [{"code": 2463794}],  # Requiem not equipped
                "graveyard": [], "hand": [], "banished": [], "extra": [],
            }
        }

        sig1 = BoardSignature.from_board_state(board1)
        sig2 = BoardSignature.from_board_state(board2)

        self.assertEqual(len(sig1.equips), 1)
        self.assertEqual(len(sig2.equips), 0)
        self.assertNotEqual(sig1.hash(), sig2.hash())

    def test_empty_board(self):
        """Empty board produces valid signature."""
        board = {
            "player0": {
                "monsters": [], "spells": [], "graveyard": [],
                "hand": [], "banished": [], "extra": [],
            }
        }

        sig = BoardSignature.from_board_state(board)
        self.assertEqual(len(sig.monsters), 0)
        self.assertEqual(len(sig.spells), 0)
        self.assertIsNotNone(sig.hash())


class TestIntermediateState(unittest.TestCase):
    """Test IntermediateState with legal actions."""

    def test_extract_all_action_types(self):
        """All action types are extracted from idle_data."""
        idle_data = {
            "activatable": [
                {"code": 60764609, "loc": LOCATION_HAND, "desc": 0},
                {"code": 60764609, "loc": LOCATION_GRAVE, "desc": 2},
            ],
            "spsummon": [{"code": 2463794}],
            "summonable": [{"code": 12345678}],
            "mset": [{"code": 11111111}],
            "sset": [{"code": 22222222}],
            "to_ep": True,
        }
        board_state = {
            "player0": {
                "monsters": [], "spells": [], "graveyard": [],
                "hand": [], "banished": [], "extra": [],
            }
        }

        state = IntermediateState.from_idle_data(idle_data, board_state)

        # Should have 7 actions: 2 activates + 1 spsummon + 1 summon + 1 mset + 1 sset + 1 pass
        self.assertEqual(state.num_actions(), 7)
        self.assertTrue(state.can_pass())

        # Check specific action specs
        actions = state.legal_actions
        self.assertIn("act:60764609:0", actions)
        self.assertIn("act:60764609:2", actions)
        self.assertIn("ss:2463794", actions)
        self.assertIn("ns:12345678", actions)
        self.assertIn("mset:11111111", actions)
        self.assertIn("sset:22222222", actions)
        self.assertIn("pass", actions)

    def test_hash_includes_legal_actions(self):
        """Different legal actions produce different hashes."""
        board_state = {
            "player0": {
                "monsters": [{"code": 79559912}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }

        # State with one activatable
        idle1 = {
            "activatable": [{"code": 60764609, "loc": LOCATION_HAND, "desc": 0}],
            "spsummon": [],
            "to_ep": True,
        }
        # Same board, different activatable (OPT used)
        idle2 = {
            "activatable": [],
            "spsummon": [],
            "to_ep": True,
        }

        state1 = IntermediateState.from_idle_data(idle1, board_state)
        state2 = IntermediateState.from_idle_data(idle2, board_state)

        # Same board, but different legal actions -> different hash
        self.assertNotEqual(state1.hash(), state2.hash())

    def test_hash_determinism(self):
        """Same state produces same hash."""
        idle_data = {
            "activatable": [{"code": 60764609, "loc": LOCATION_HAND, "desc": 0}],
            "spsummon": [{"code": 2463794}],
            "to_ep": True,
        }
        board_state = {
            "player0": {
                "monsters": [{"code": 79559912}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }

        state1 = IntermediateState.from_idle_data(idle_data, board_state)
        state2 = IntermediateState.from_idle_data(idle_data, board_state)

        self.assertEqual(state1.hash(), state2.hash())


class TestActionSpec(unittest.TestCase):
    """Test ActionSpec creation and hashing."""

    def test_factory_methods(self):
        """Factory methods create correct spec strings."""
        act = ActionSpec.activate(60764609, 0, LOCATION_HAND)
        self.assertEqual(act.spec, "act:60764609:0")
        self.assertEqual(act.action_type, "activate")

        ss = ActionSpec.special_summon(2463794)
        self.assertEqual(ss.spec, "ss:2463794")
        self.assertEqual(ss.action_type, "spsummon")

        ns = ActionSpec.normal_summon(12345678)
        self.assertEqual(ns.spec, "ns:12345678")
        self.assertEqual(ns.action_type, "summon")

        mset = ActionSpec.monster_set(11111111)
        self.assertEqual(mset.spec, "mset:11111111")

        sset = ActionSpec.spell_set(22222222)
        self.assertEqual(sset.spec, "sset:22222222")

        pass_act = ActionSpec.pass_action()
        self.assertEqual(pass_act.spec, "pass")

    def test_equality_by_spec(self):
        """ActionSpecs are equal if their specs match."""
        act1 = ActionSpec.activate(60764609, 0, LOCATION_HAND)
        act2 = ActionSpec.activate(60764609, 0, LOCATION_GRAVE)  # Different loc

        # Should be equal because spec only includes code:effect_idx
        self.assertEqual(act1.spec, act2.spec)
        self.assertEqual(act1, act2)


class TestBoardEvaluation(unittest.TestCase):
    """Test board quality evaluation."""

    def test_boss_detection(self):
        """Boss monsters are detected."""
        board = {
            "player0": {
                "monsters": [{"code": 79559912}],  # Caesar
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }

        sig = BoardSignature.from_board_state(board)
        eval_result = evaluate_board_quality(sig)

        self.assertTrue(eval_result["has_boss"])
        self.assertGreater(eval_result["score"], 0)

    def test_tier_ranking(self):
        """Higher scores get better tiers."""
        # S-tier: Multiple bosses
        s_board = {
            "player0": {
                "monsters": [
                    {"code": 79559912},  # Caesar
                    {"code": 29301450},  # S:P Little Knight
                ],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }

        # Brick: Empty board
        brick_board = {
            "player0": {
                "monsters": [], "spells": [], "graveyard": [],
                "hand": [], "banished": [], "extra": [],
            }
        }

        s_sig = BoardSignature.from_board_state(s_board)
        brick_sig = BoardSignature.from_board_state(brick_board)

        s_eval = evaluate_board_quality(s_sig)
        brick_eval = evaluate_board_quality(brick_sig)

        self.assertEqual(s_eval["tier"], "S")
        self.assertEqual(brick_eval["tier"], "brick")


class TestTranspositionTable(unittest.TestCase):
    """Test transposition table operations."""

    def test_store_and_lookup(self):
        """Basic store and lookup works."""
        tt = TranspositionTable()

        entry = TranspositionEntry(
            state_hash="abc123",
            best_terminal_hash="terminal_xyz",
            best_terminal_value=85.0,
            depth_to_terminal=3,
            visit_count=1,
        )
        tt.store("abc123", entry)

        result = tt.lookup("abc123")
        self.assertIsNotNone(result)
        self.assertEqual(result.best_terminal_value, 85.0)
        self.assertEqual(result.visit_count, 2)  # Incremented on lookup

    def test_miss_returns_none(self):
        """Lookup of unknown key returns None."""
        tt = TranspositionTable()
        result = tt.lookup("nonexistent")
        self.assertIsNone(result)

    def test_hit_miss_tracking(self):
        """Hits and misses are tracked."""
        tt = TranspositionTable()

        tt.lookup("a")  # Miss
        tt.lookup("b")  # Miss

        entry = TranspositionEntry("c", "", 0.0, 0, 1)
        tt.store("c", entry)

        tt.lookup("c")  # Hit
        tt.lookup("c")  # Hit
        tt.lookup("d")  # Miss

        stats = tt.stats()
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 3)
        self.assertAlmostEqual(stats["hit_rate"], 0.4)

    def test_eviction(self):
        """Table evicts entries when full."""
        tt = TranspositionTable(max_size=10)

        # Fill table
        for i in range(10):
            entry = TranspositionEntry(f"state_{i}", "", 0.0, 0, 1)
            tt.store(f"state_{i}", entry)

        self.assertEqual(len(tt.table), 10)

        # Add one more - should trigger eviction
        entry = TranspositionEntry("state_new", "", 0.0, 0, 1)
        tt.store("state_new", entry)

        # Should have evicted some entries
        self.assertLess(len(tt.table), 11)

    def test_visit_count_increments(self):
        """Visit count increments on each lookup."""
        tt = TranspositionTable()

        entry = TranspositionEntry("state_x", "", 0.0, 0, 1)
        tt.store("state_x", entry)

        tt.lookup("state_x")
        tt.lookup("state_x")
        tt.lookup("state_x")

        result = tt.lookup("state_x")
        self.assertEqual(result.visit_count, 5)  # 1 initial + 4 lookups


class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple components."""

    def test_full_flow(self):
        """Test full flow: board -> signature -> hash -> transposition."""
        # Create a realistic board state
        board_state = {
            "player0": {
                "monsters": [
                    {"code": 79559912, "name": "Caesar", "zone_index": 0},
                    {"code": 2463794, "name": "Requiem", "zone_index": 1},
                ],
                "spells": [],
                "graveyard": [
                    {"code": 60764609, "name": "Engraver"},
                    {"code": 49867899, "name": "Sequence"},
                ],
                "hand": [{"code": 10000040, "name": "Holactie"}],
                "banished": [],
                "extra": [],
            }
        }

        idle_data = {
            "activatable": [
                {"code": 79559912, "loc": LOCATION_MZONE, "desc": 1},  # Caesar effect
            ],
            "spsummon": [],
            "to_ep": True,
        }

        # Create intermediate state
        state = IntermediateState.from_idle_data(idle_data, board_state)
        state_hash = state.hash()

        # Store in transposition table
        tt = TranspositionTable()
        entry = TranspositionEntry(
            state_hash=state_hash,
            best_terminal_hash="",
            best_terminal_value=0.0,
            depth_to_terminal=0,
            visit_count=1,
        )
        tt.store(state_hash, entry)

        # Verify lookup works
        cached = tt.lookup(state_hash)
        self.assertIsNotNone(cached)

        # Create same state again - should produce same hash
        state2 = IntermediateState.from_idle_data(idle_data, board_state)
        self.assertEqual(state.hash(), state2.hash())

        # Evaluate the board
        eval_result = evaluate_board_quality(state.board)
        self.assertEqual(eval_result["tier"], "S")  # Caesar + Requiem = good board


if __name__ == "__main__":
    unittest.main(verbosity=2)
