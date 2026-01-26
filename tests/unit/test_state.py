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

import sys
import unittest
from pathlib import Path

# Add src/cffi to path for imports
sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "cffi"))

from state_representation import (
    BoardSignature, IntermediateState, ActionSpec,
    evaluate_board_quality,
)
from transposition_table import TranspositionTable, TranspositionEntry
from ocg_bindings import LOCATION_HAND, LOCATION_MZONE, LOCATION_GRAVE

# Card passcode constants for test clarity
CAESAR = 79559912           # D/D/D Wave High King Caesar
REQUIEM = 2463794           # Fiendsmith's Requiem (Link-1)
ENGRAVER = 60764609         # Fiendsmith Engraver
SEQUENCE = 49867899         # Fiendsmith's Sequence
SP_LITTLE_KNIGHT = 29301450 # S:P Little Knight
HOLACTIE = 10000040         # Holactie the Creator of Light


class TestBoardSignature(unittest.TestCase):
    """Test BoardSignature hashing and equality."""

    def test_hash_determinism(self):
        """Same board state produces same hash every time."""
        board_state = {
            "player0": {
                "monsters": [
                    {"code": CAESAR, "name": "Caesar"},
                    {"code": REQUIEM, "name": "Requiem"},
                ],
                "spells": [],
                "graveyard": [{"code": ENGRAVER, "name": "Engraver"}],
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
                "monsters": [{"code": CAESAR}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }
        board2 = {
            "player0": {
                "monsters": [{"code": REQUIEM}],
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
                "monsters": [{"code": ENGRAVER}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }
        # Same card in GY
        board2 = {
            "player0": {
                "monsters": [],
                "spells": [], "graveyard": [{"code": ENGRAVER}], "hand": [],
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
                "monsters": [{"code": CAESAR}, {"code": REQUIEM}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }
        board2 = {
            "player0": {
                "monsters": [{"code": REQUIEM}, {"code": CAESAR}],
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
                "monsters": [{"code": CAESAR, "zone_index": 0}],
                "spells": [{"code": REQUIEM, "equip_target": 0}],  # Requiem equipped
                "graveyard": [], "hand": [], "banished": [], "extra": [],
            }
        }
        # Same cards, no equip
        board2 = {
            "player0": {
                "monsters": [{"code": CAESAR, "zone_index": 0}],
                "spells": [{"code": REQUIEM}],  # Requiem not equipped
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
                {"code": ENGRAVER, "loc": LOCATION_HAND, "desc": 0},
                {"code": ENGRAVER, "loc": LOCATION_GRAVE, "desc": 2},
            ],
            "spsummon": [{"code": REQUIEM}],
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
        self.assertIn(f"act:{ENGRAVER}:0", actions)
        self.assertIn(f"act:{ENGRAVER}:2", actions)
        self.assertIn(f"ss:{REQUIEM}", actions)
        self.assertIn("ns:12345678", actions)
        self.assertIn("mset:11111111", actions)
        self.assertIn("sset:22222222", actions)
        self.assertIn("pass", actions)

    def test_hash_includes_legal_actions(self):
        """Different legal actions produce different hashes."""
        board_state = {
            "player0": {
                "monsters": [{"code": CAESAR}],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }

        # State with one activatable
        idle1 = {
            "activatable": [{"code": ENGRAVER, "loc": LOCATION_HAND, "desc": 0}],
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
            "activatable": [{"code": ENGRAVER, "loc": LOCATION_HAND, "desc": 0}],
            "spsummon": [{"code": REQUIEM}],
            "to_ep": True,
        }
        board_state = {
            "player0": {
                "monsters": [{"code": CAESAR}],
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
        act = ActionSpec.activate(ENGRAVER, 0, LOCATION_HAND)
        self.assertEqual(act.spec, f"act:{ENGRAVER}:0")
        self.assertEqual(act.action_type, "activate")

        ss = ActionSpec.special_summon(REQUIEM)
        self.assertEqual(ss.spec, f"ss:{REQUIEM}")
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
        act1 = ActionSpec.activate(ENGRAVER, 0, LOCATION_HAND)
        act2 = ActionSpec.activate(ENGRAVER, 0, LOCATION_GRAVE)  # Different loc

        # Should be equal because spec only includes code:effect_idx
        self.assertEqual(act1.spec, act2.spec)
        self.assertEqual(act1, act2)


class TestBoardEvaluation(unittest.TestCase):
    """Test board quality evaluation."""

    def test_boss_detection(self):
        """Boss monsters are detected."""
        board = {
            "player0": {
                "monsters": [{"code": CAESAR}],  # Caesar
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
                    {"code": CAESAR},  # Caesar
                    {"code": SP_LITTLE_KNIGHT},  # S:P Little Knight
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

    def test_tier_a_boundary(self):
        """A-tier: score 70-99 (one boss + non-boss monsters)."""
        # Use Desirae (boss but NOT interaction piece) to avoid double-counting
        DESIRAE = 82135803  # Fiendsmith's Desirae - boss only
        # 1 boss (50 + 5) + 3 unique non-boss monsters (15) = 70
        a_board = {
            "player0": {
                "monsters": [
                    {"code": DESIRAE},     # Boss only (50 + 5 = 55)
                    {"code": 3000001},     # Non-boss (5)
                    {"code": 3000002},     # Non-boss (5)
                    {"code": 3000003},     # Non-boss (5) = total 70
                ],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }

        sig = BoardSignature.from_board_state(a_board)
        eval_result = evaluate_board_quality(sig)

        self.assertEqual(eval_result["tier"], "A")
        self.assertGreaterEqual(eval_result["score"], 70)
        self.assertLess(eval_result["score"], 100)

    def test_tier_b_boundary(self):
        """B-tier: score 40-69 (monsters only, no boss)."""
        # 8 unique non-boss monsters = 8 * 5 = 40
        # Using unique passcodes to avoid set deduplication
        b_board = {
            "player0": {
                "monsters": [{"code": 1000000 + i} for i in range(8)],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }

        sig = BoardSignature.from_board_state(b_board)
        eval_result = evaluate_board_quality(sig)

        self.assertEqual(eval_result["tier"], "B")
        self.assertGreaterEqual(eval_result["score"], 40)
        self.assertLess(eval_result["score"], 70)

    def test_tier_c_boundary(self):
        """C-tier: score 20-39 (minimal board presence)."""
        # 4 unique non-boss monsters = 4 * 5 = 20
        c_board = {
            "player0": {
                "monsters": [{"code": 2000000 + i} for i in range(4)],
                "spells": [], "graveyard": [], "hand": [],
                "banished": [], "extra": [],
            }
        }

        sig = BoardSignature.from_board_state(c_board)
        eval_result = evaluate_board_quality(sig)

        self.assertEqual(eval_result["tier"], "C")
        self.assertGreaterEqual(eval_result["score"], 20)
        self.assertLess(eval_result["score"], 40)


class TestTranspositionTable(unittest.TestCase):
    """Test transposition table operations."""

    def test_store_and_lookup(self):
        """Basic store and lookup works."""
        tt = TranspositionTable()

        entry = TranspositionEntry(
            state_hash="abc123",
            best_terminal_hash="terminal_xyz",
            best_terminal_value=85.0,
            creation_depth=3,
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
                    {"code": CAESAR, "name": "Caesar", "zone_index": 0},
                    {"code": REQUIEM, "name": "Requiem", "zone_index": 1},
                ],
                "spells": [],
                "graveyard": [
                    {"code": ENGRAVER, "name": "Engraver"},
                    {"code": SEQUENCE, "name": "Sequence"},
                ],
                "hand": [{"code": HOLACTIE, "name": "Holactie"}],
                "banished": [],
                "extra": [],
            }
        }

        idle_data = {
            "activatable": [
                {"code": CAESAR, "loc": LOCATION_MZONE, "desc": 1},  # Caesar effect
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
            creation_depth=0,
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
