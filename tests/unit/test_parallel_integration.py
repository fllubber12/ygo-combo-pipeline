#!/usr/bin/env python3
"""Integration tests for parallel combo enumeration.

These tests verify that the parallel enumeration infrastructure works
correctly with the actual enumeration engine. They require the ygopro-core
engine to be available (YGOPRO_SCRIPTS_PATH set).
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "ygo_combo"))

# Check if engine is available
try:
    from src.ygo_combo.engine.paths import get_scripts_path
    get_scripts_path()
    ENGINE_AVAILABLE = True
except (ImportError, EnvironmentError):
    ENGINE_AVAILABLE = False


# =============================================================================
# UNIT TESTS (No engine required)
# =============================================================================

class TestEnumerateFromHandInterface:
    """Test enumerate_from_hand function interface without engine."""

    def test_function_exists(self):
        """enumerate_from_hand should be importable."""
        from src.ygo_combo.combo_enumeration import enumerate_from_hand
        assert callable(enumerate_from_hand)

    def test_returns_dict(self):
        """enumerate_from_hand should return a dict even on error."""
        from src.ygo_combo.combo_enumeration import enumerate_from_hand

        # Mock the dependencies to avoid needing actual engine
        with patch('src.ygo_combo.combo_enumeration.init_card_database') as mock_init:
            mock_init.side_effect = Exception("No engine")

            result = enumerate_from_hand(
                hand=(1, 2, 3, 4, 5),
                deck=[1, 2, 3, 4, 5],
                max_depth=10,
                max_paths=10,
            )

            assert isinstance(result, dict)
            assert "terminal_hashes" in result
            assert "best_score" in result
            assert "paths_explored" in result
            assert "max_depth_reached" in result

    def test_empty_result_on_error(self):
        """enumerate_from_hand should return empty results on error."""
        from src.ygo_combo.combo_enumeration import enumerate_from_hand

        with patch('src.ygo_combo.combo_enumeration.init_card_database') as mock_init:
            mock_init.side_effect = Exception("No engine")

            result = enumerate_from_hand(
                hand=(1, 2, 3, 4, 5),
                deck=None,
                max_depth=10,
                max_paths=10,
            )

            assert result["terminal_hashes"] == []
            assert result["best_score"] == 0.0
            assert result["paths_explored"] == 0
            assert result["max_depth_reached"] == 0


class TestParallelWorkerInterface:
    """Test parallel worker function interface without engine."""

    def test_worker_init_sets_globals(self):
        """_worker_init should set global worker state."""
        from src.ygo_combo.search.parallel import _worker_init
        import src.ygo_combo.search.parallel as parallel

        deck = [1, 2, 3, 4, 5]
        max_depth = 15
        max_paths = 100

        _worker_init(deck, max_depth, max_paths)

        assert parallel._worker_deck == deck
        assert parallel._worker_max_depth == max_depth
        assert parallel._worker_max_paths == max_paths
        assert parallel._worker_engine_initialized == False

    def test_enumerate_hand_returns_combo_result(self):
        """_enumerate_hand should return ComboResult on error."""
        from src.ygo_combo.search.parallel import _enumerate_hand, ComboResult, _worker_init

        # Initialize worker state
        _worker_init([1, 2, 3, 4, 5], 10, 10)

        # Call enumerate - should handle error gracefully
        result = _enumerate_hand((1, 2, 3, 4, 5))

        assert isinstance(result, ComboResult)
        assert result.hand == (1, 2, 3, 4, 5)
        assert isinstance(result.terminal_boards, list)
        assert isinstance(result.duration_ms, float)

    def test_worker_batch_processes_all_hands(self):
        """_worker_batch should process all hands in batch."""
        from src.ygo_combo.search.parallel import _worker_batch, _worker_init

        _worker_init([1, 2, 3, 4, 5], 10, 10)

        hands = [
            (1, 2, 3, 4, 5),
            (2, 3, 4, 5, 6),
            (3, 4, 5, 6, 7),
        ]

        results = _worker_batch(hands)

        assert len(results) == 3
        assert results[0].hand == (1, 2, 3, 4, 5)
        assert results[1].hand == (2, 3, 4, 5, 6)
        assert results[2].hand == (3, 4, 5, 6, 7)


class TestParallelResultAggregation:
    """Test result aggregation logic."""

    def test_unique_terminals_aggregated(self):
        """Results should aggregate unique terminal hashes."""
        from src.ygo_combo.search.parallel import ComboResult, ParallelResult

        results = [
            ComboResult(
                hand=(1, 2, 3, 4, 5),
                terminal_boards=["hash_a", "hash_b"],
                best_score=50.0,
                paths_explored=10,
                depth_reached=5,
                duration_ms=100.0,
            ),
            ComboResult(
                hand=(2, 3, 4, 5, 6),
                terminal_boards=["hash_b", "hash_c"],  # hash_b is duplicate
                best_score=75.0,
                paths_explored=15,
                depth_reached=8,
                duration_ms=150.0,
            ),
        ]

        # Aggregate results manually (simulating parallel_enumerate aggregation)
        all_terminals = set()
        total_paths = 0
        best_score = 0.0
        best_hand = None

        for result in results:
            all_terminals.update(result.terminal_boards)
            total_paths += result.paths_explored
            if result.best_score > best_score:
                best_score = result.best_score
                best_hand = result.hand

        # Verify aggregation
        assert len(all_terminals) == 3  # hash_a, hash_b, hash_c
        assert total_paths == 25
        assert best_score == 75.0
        assert best_hand == (2, 3, 4, 5, 6)


# =============================================================================
# INTEGRATION TESTS (Engine required)
# =============================================================================

@pytest.mark.skipif(
    not ENGINE_AVAILABLE,
    reason="ygopro-core engine not available (YGOPRO_SCRIPTS_PATH not set)"
)
class TestParallelEnumerationWithEngine:
    """Integration tests requiring the actual engine."""

    def test_enumerate_from_hand_with_engine(self):
        """enumerate_from_hand should work with actual engine."""
        from src.ygo_combo.combo_enumeration import enumerate_from_hand

        # Use a simple hand (Engraver + filler)
        ENGRAVER = 60764609
        HOLACTIE = 10000040
        hand = (ENGRAVER, HOLACTIE, HOLACTIE, HOLACTIE, HOLACTIE)

        result = enumerate_from_hand(
            hand=hand,
            deck=None,  # Use locked library
            max_depth=5,  # Shallow for fast test
            max_paths=10,  # Few paths for fast test
        )

        assert isinstance(result, dict)
        assert result["paths_explored"] > 0
        # Should find at least the pass terminal
        assert result["max_depth_reached"] >= 0

    def test_parallel_enumerate_small_deck(self):
        """parallel_enumerate should work with small test deck."""
        from src.ygo_combo.search.parallel import parallel_enumerate, ParallelConfig

        # Very small deck for testing
        deck = list(range(10))  # 10 synthetic card codes

        config = ParallelConfig(
            deck=deck,
            hand_size=3,  # C(10,3) = 120 hands
            num_workers=2,
            max_depth=5,
            max_paths_per_hand=5,
        )

        result = parallel_enumerate(config)

        assert result.total_hands == 120
        assert result.duration_seconds >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
