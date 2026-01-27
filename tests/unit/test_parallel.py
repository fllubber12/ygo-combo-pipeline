#!/usr/bin/env python3
"""Unit tests for parallel search module."""

import unittest
import sys
from pathlib import Path
from math import comb

sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "ygo_combo"))

from search.parallel import (
    ParallelConfig,
    ComboResult,
    ParallelResult,
    generate_all_hands,
    estimate_runtime,
)


class TestParallelConfig(unittest.TestCase):
    """Test ParallelConfig initialization."""

    def test_default_workers(self):
        """Default workers = CPU count."""
        import multiprocessing as mp
        config = ParallelConfig(deck=list(range(40)))
        self.assertEqual(config.num_workers, mp.cpu_count())

    def test_custom_workers(self):
        """Custom worker count is respected."""
        config = ParallelConfig(deck=list(range(40)), num_workers=4)
        self.assertEqual(config.num_workers, 4)

    def test_total_hands_calculation(self):
        """Total hands = C(n,k)."""
        config = ParallelConfig(deck=list(range(40)), hand_size=5)
        self.assertEqual(config.total_hands(), comb(40, 5))
        self.assertEqual(config.total_hands(), 658008)

    def test_batch_size_auto(self):
        """Batch size is auto-calculated."""
        config = ParallelConfig(deck=list(range(40)), num_workers=8)
        # Should aim for ~100 batches per worker
        expected = 658008 // (8 * 100)
        self.assertEqual(config.batch_size, expected)

    def test_small_deck(self):
        """Works with small decks."""
        config = ParallelConfig(deck=list(range(10)), hand_size=3)
        self.assertEqual(config.total_hands(), comb(10, 3))
        self.assertEqual(config.total_hands(), 120)


class TestGenerateHands(unittest.TestCase):
    """Test hand generation."""

    def test_count(self):
        """Generates correct number of hands."""
        deck = list(range(10))
        hands = generate_all_hands(deck, 3)
        self.assertEqual(len(hands), comb(10, 3))
        self.assertEqual(len(hands), 120)

    def test_uniqueness(self):
        """All hands are unique."""
        deck = list(range(20))
        hands = generate_all_hands(deck, 4)
        self.assertEqual(len(hands), len(set(hands)))

    def test_sorted_output(self):
        """Hands are generated in sorted order."""
        deck = [5, 3, 1, 4, 2]
        hands = generate_all_hands(deck, 2)
        # First hand should be (1, 2), not (5, 3)
        self.assertEqual(hands[0], (1, 2))

    def test_hand_size(self):
        """Each hand has correct size."""
        deck = list(range(15))
        hands = generate_all_hands(deck, 5)
        for hand in hands:
            self.assertEqual(len(hand), 5)

    def test_deterministic(self):
        """Same deck produces same hands."""
        deck = list(range(20))
        hands1 = generate_all_hands(deck, 4)
        hands2 = generate_all_hands(deck, 4)
        self.assertEqual(hands1, hands2)


class TestEstimateRuntime(unittest.TestCase):
    """Test runtime estimation."""

    def test_basic_estimate(self):
        """Estimate returns expected fields."""
        estimate = estimate_runtime(
            deck_size=40,
            hand_size=5,
            num_workers=8,
            ms_per_hand=100.0,
        )

        self.assertIn("total_hands", estimate)
        self.assertIn("estimated_seconds", estimate)
        self.assertIn("estimated_hours", estimate)
        self.assertIn("hands_per_second", estimate)

        self.assertEqual(estimate["total_hands"], 658008)

    def test_scaling_with_workers(self):
        """More workers = faster estimate."""
        est_4 = estimate_runtime(deck_size=40, num_workers=4, ms_per_hand=100)
        est_8 = estimate_runtime(deck_size=40, num_workers=8, ms_per_hand=100)

        # 8 workers should be ~2x faster than 4
        self.assertAlmostEqual(
            est_4["estimated_seconds"] / est_8["estimated_seconds"],
            2.0,
            places=1
        )

    def test_scaling_with_ms_per_hand(self):
        """Slower hands = longer estimate."""
        est_fast = estimate_runtime(deck_size=40, num_workers=8, ms_per_hand=50)
        est_slow = estimate_runtime(deck_size=40, num_workers=8, ms_per_hand=100)

        self.assertAlmostEqual(
            est_slow["estimated_seconds"] / est_fast["estimated_seconds"],
            2.0,
            places=1
        )


class TestComboResult(unittest.TestCase):
    """Test ComboResult dataclass."""

    def test_creation(self):
        """ComboResult can be created."""
        result = ComboResult(
            hand=(1, 2, 3, 4, 5),
            terminal_boards=["abc123", "def456"],
            best_score=85.0,
            paths_explored=100,
            depth_reached=15,
            duration_ms=50.5,
        )

        self.assertEqual(result.hand, (1, 2, 3, 4, 5))
        self.assertEqual(len(result.terminal_boards), 2)
        self.assertEqual(result.best_score, 85.0)

    def test_empty_result(self):
        """ComboResult handles empty terminal list."""
        result = ComboResult(
            hand=(1, 2, 3, 4, 5),
            terminal_boards=[],
            best_score=0.0,
            paths_explored=0,
            depth_reached=0,
            duration_ms=1.0,
        )

        self.assertEqual(len(result.terminal_boards), 0)
        self.assertEqual(result.best_score, 0.0)


class TestParallelResult(unittest.TestCase):
    """Test ParallelResult dataclass."""

    def test_creation(self):
        """ParallelResult can be created."""
        result = ParallelResult(
            total_hands=658008,
            total_terminals=5000,
            total_paths=1000000,
            best_hand=(1, 2, 3, 4, 5),
            best_score=100.0,
            duration_seconds=3600.0,
            worker_stats={},
            terminal_distribution={0: 100, 1: 500, 2: 300},
        )

        self.assertEqual(result.total_hands, 658008)
        self.assertEqual(result.total_terminals, 5000)

    def test_no_best_hand(self):
        """ParallelResult handles None best_hand."""
        result = ParallelResult(
            total_hands=100,
            total_terminals=0,
            total_paths=0,
            best_hand=None,
            best_score=0.0,
            duration_seconds=1.0,
            worker_stats={},
        )

        self.assertIsNone(result.best_hand)


if __name__ == "__main__":
    unittest.main(verbosity=2)
