#!/usr/bin/env python3
"""Unit tests for iterative deepening search module."""

import unittest
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "ygo_combo"))

from search.iddfs import (
    SearchConfig, DepthResult, SearchResult,
    TargetScoreReached, TargetTierReached, TimeBudgetExhausted,
    PathBudgetExhausted, AnyTerminalFound,
    IterativeDeepeningSearch,
)


class TestSearchConfig(unittest.TestCase):
    """Test SearchConfig dataclass."""

    def test_default_values(self):
        """Default values are set correctly."""
        config = SearchConfig()
        self.assertEqual(config.max_depth, 25)
        self.assertEqual(config.min_depth, 1)
        self.assertEqual(config.depth_step, 1)
        self.assertIsNone(config.target_score)
        self.assertIsNone(config.time_budget)

    def test_custom_values(self):
        """Custom values are accepted."""
        config = SearchConfig(
            max_depth=50,
            min_depth=5,
            depth_step=2,
            target_score=100.0,
            time_budget=60.0,
        )
        self.assertEqual(config.max_depth, 50)
        self.assertEqual(config.min_depth, 5)
        self.assertEqual(config.depth_step, 2)
        self.assertEqual(config.target_score, 100.0)
        self.assertEqual(config.time_budget, 60.0)

    def test_terminals_per_depth_default(self):
        """terminals_per_depth has default value."""
        config = SearchConfig()
        self.assertEqual(config.terminals_per_depth, 1000)


class TestStoppingConditions(unittest.TestCase):
    """Test stopping condition classes."""

    def test_target_score_not_reached(self):
        """TargetScoreReached returns False below target."""
        cond = TargetScoreReached(100.0)
        self.assertFalse(cond.should_stop({"best_score": 50}))
        self.assertFalse(cond.should_stop({"best_score": 99}))

    def test_target_score_reached(self):
        """TargetScoreReached returns True at or above target."""
        cond = TargetScoreReached(100.0)
        self.assertTrue(cond.should_stop({"best_score": 100}))
        self.assertTrue(cond.should_stop({"best_score": 150}))

    def test_target_score_reason(self):
        """TargetScoreReached provides reason string."""
        cond = TargetScoreReached(100.0)
        self.assertIn("100", cond.reason())

    def test_target_tier_ordering(self):
        """TargetTierReached respects tier ordering."""
        cond = TargetTierReached("A")
        self.assertFalse(cond.should_stop({"best_tier": "B"}))
        self.assertFalse(cond.should_stop({"best_tier": "C"}))
        self.assertTrue(cond.should_stop({"best_tier": "A"}))
        self.assertTrue(cond.should_stop({"best_tier": "S"}))

    def test_target_tier_s(self):
        """TargetTierReached works for S tier."""
        cond = TargetTierReached("S")
        self.assertFalse(cond.should_stop({"best_tier": "A"}))
        self.assertTrue(cond.should_stop({"best_tier": "S"}))

    def test_path_budget_not_exhausted(self):
        """PathBudgetExhausted returns False below budget."""
        cond = PathBudgetExhausted(1000)
        self.assertFalse(cond.should_stop({"total_paths": 0}))
        self.assertFalse(cond.should_stop({"total_paths": 999}))

    def test_path_budget_exhausted(self):
        """PathBudgetExhausted returns True at or above budget."""
        cond = PathBudgetExhausted(1000)
        self.assertTrue(cond.should_stop({"total_paths": 1000}))
        self.assertTrue(cond.should_stop({"total_paths": 1500}))

    def test_any_terminal_found(self):
        """AnyTerminalFound returns True when terminal exists."""
        cond = AnyTerminalFound()
        self.assertFalse(cond.should_stop({"total_terminals": 0}))
        self.assertTrue(cond.should_stop({"total_terminals": 1}))

    def test_any_terminal_require_boss(self):
        """AnyTerminalFound with require_boss checks boss count."""
        cond = AnyTerminalFound(require_boss=True)
        self.assertFalse(cond.should_stop({"total_terminals": 5, "terminals_with_boss": 0}))
        self.assertTrue(cond.should_stop({"total_terminals": 5, "terminals_with_boss": 1}))


class TestDepthResult(unittest.TestCase):
    """Test DepthResult dataclass."""

    def test_creation(self):
        """DepthResult can be created with required fields."""
        result = DepthResult(
            depth=5,
            terminals_found=10,
            terminals_total=25,
            best_score=85.0,
            best_tier="A",
            paths_explored=1000,
            duration_seconds=1.5,
        )
        self.assertEqual(result.depth, 5)
        self.assertEqual(result.terminals_found, 10)
        self.assertEqual(result.best_tier, "A")

    def test_new_terminals_default(self):
        """DepthResult has empty new_terminals by default."""
        result = DepthResult(
            depth=1, terminals_found=0, terminals_total=0,
            best_score=0, best_tier="brick",
            paths_explored=0, duration_seconds=0,
        )
        self.assertEqual(result.new_terminals, [])


class TestSearchResult(unittest.TestCase):
    """Test SearchResult dataclass."""

    def test_creation(self):
        """SearchResult can be created with required fields."""
        result = SearchResult(
            depths_searched=10,
            total_terminals=50,
            total_paths=5000,
            total_duration=30.0,
            best_score=100.0,
            best_tier="S",
            best_depth=8,
            shortest_combo_depth=5,
            stopped_reason="target_tier_reached",
        )
        self.assertEqual(result.depths_searched, 10)
        self.assertEqual(result.best_tier, "S")
        self.assertEqual(result.shortest_combo_depth, 5)

    def test_optional_shortest_combo(self):
        """SearchResult allows None for shortest_combo_depth."""
        result = SearchResult(
            depths_searched=5,
            total_terminals=0,
            total_paths=100,
            total_duration=1.0,
            best_score=0,
            best_tier="brick",
            best_depth=0,
            shortest_combo_depth=None,
            stopped_reason="max_depth_reached",
        )
        self.assertIsNone(result.shortest_combo_depth)

    def test_default_lists(self):
        """SearchResult has empty lists by default."""
        result = SearchResult(
            depths_searched=1, total_terminals=0, total_paths=0,
            total_duration=0, best_score=0, best_tier="brick",
            best_depth=0, shortest_combo_depth=None,
            stopped_reason="test",
        )
        self.assertEqual(result.depth_results, [])
        self.assertEqual(result.best_terminals, [])


class TestIterativeDeepeningSearch(unittest.TestCase):
    """Test IterativeDeepeningSearch class."""

    def test_init_with_config(self):
        """Search initializes with config."""
        config = SearchConfig(max_depth=10)
        search = IterativeDeepeningSearch(
            engine_factory=lambda: None,
            config=config,
        )
        self.assertEqual(search.config.max_depth, 10)

    def test_stopping_conditions_built(self):
        """Stopping conditions are built from config."""
        config = SearchConfig(
            target_score=100.0,
            target_tier="A",
            path_budget=1000,
        )
        search = IterativeDeepeningSearch(
            engine_factory=lambda: None,
            config=config,
        )
        self.assertEqual(len(search.stopping_conditions), 3)

    def test_no_stopping_conditions(self):
        """No stopping conditions when not configured."""
        config = SearchConfig()
        search = IterativeDeepeningSearch(
            engine_factory=lambda: None,
            config=config,
        )
        self.assertEqual(len(search.stopping_conditions), 0)

    def test_early_stop_adds_condition(self):
        """early_stop_on_any adds AnyTerminalFound condition."""
        config = SearchConfig(early_stop_on_any=True)
        search = IterativeDeepeningSearch(
            engine_factory=lambda: None,
            config=config,
        )
        self.assertEqual(len(search.stopping_conditions), 1)
        self.assertIsInstance(search.stopping_conditions[0], AnyTerminalFound)

    def test_time_budget_condition(self):
        """time_budget adds TimeBudgetExhausted condition."""
        config = SearchConfig(time_budget=60.0)
        search = IterativeDeepeningSearch(
            engine_factory=lambda: None,
            config=config,
        )
        self.assertEqual(len(search.stopping_conditions), 1)
        self.assertIsInstance(search.stopping_conditions[0], TimeBudgetExhausted)


class TestTimeBudgetExhausted(unittest.TestCase):
    """Test TimeBudgetExhausted condition."""

    def test_not_exhausted_immediately(self):
        """Budget is not exhausted immediately."""
        cond = TimeBudgetExhausted(1.0)
        self.assertFalse(cond.should_stop({}))

    def test_exhausted_after_time(self):
        """Budget is exhausted after time passes."""
        cond = TimeBudgetExhausted(0.1)
        time.sleep(0.15)
        self.assertTrue(cond.should_stop({}))

    def test_reason_includes_budget(self):
        """Reason string includes budget value."""
        cond = TimeBudgetExhausted(30.0)
        self.assertIn("30", cond.reason())


if __name__ == "__main__":
    unittest.main(verbosity=2)
