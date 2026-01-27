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
# CHECKPOINT TESTS (No engine required)
# =============================================================================

class TestParallelCheckpoint:
    """Test parallel checkpoint save/load functionality."""

    def test_checkpoint_dataclass_creation(self):
        """ParallelCheckpoint should be creatable with all fields."""
        from src.ygo_combo.search.parallel import ParallelCheckpoint

        checkpoint = ParallelCheckpoint(
            version=1,
            timestamp="2026-01-26T12:00:00Z",
            config_hash="abc123",
            completed_hands=[(1, 2, 3), (4, 5, 6)],
            all_terminals=["term_a", "term_b"],
            total_paths=100,
            best_hand=(1, 2, 3),
            best_score=75.0,
            terminal_counts={0: 5, 1: 3, 2: 2},
            results=None,
        )

        assert checkpoint.version == 1
        assert len(checkpoint.completed_hands) == 2
        assert checkpoint.best_score == 75.0

    def test_save_and_load_checkpoint(self, tmp_path):
        """Checkpoint should be saveable and loadable."""
        from src.ygo_combo.search.parallel import (
            ParallelCheckpoint,
            save_parallel_checkpoint,
            load_parallel_checkpoint,
        )

        checkpoint = ParallelCheckpoint(
            version=1,
            timestamp="2026-01-26T12:00:00Z",
            config_hash="test123",
            completed_hands=[(1, 2, 3, 4, 5), (2, 3, 4, 5, 6)],
            all_terminals=["hash_a", "hash_b", "hash_c"],
            total_paths=250,
            best_hand=(2, 3, 4, 5, 6),
            best_score=85.5,
            terminal_counts={0: 10, 1: 5, 2: 3},
            results=None,
        )

        # Save
        path = tmp_path / "test_checkpoint"
        saved_path = save_parallel_checkpoint(checkpoint, path, compress=True)

        assert saved_path.exists()
        assert saved_path.suffix == ".gz"

        # Load
        loaded = load_parallel_checkpoint(saved_path)

        assert loaded.version == checkpoint.version
        assert loaded.config_hash == checkpoint.config_hash
        assert loaded.completed_hands == checkpoint.completed_hands
        assert loaded.all_terminals == checkpoint.all_terminals
        assert loaded.total_paths == checkpoint.total_paths
        assert loaded.best_hand == checkpoint.best_hand
        assert loaded.best_score == checkpoint.best_score
        assert loaded.terminal_counts == checkpoint.terminal_counts

    def test_save_uncompressed(self, tmp_path):
        """Checkpoint should be saveable without compression."""
        from src.ygo_combo.search.parallel import (
            ParallelCheckpoint,
            save_parallel_checkpoint,
            load_parallel_checkpoint,
        )

        checkpoint = ParallelCheckpoint(
            version=1,
            timestamp="2026-01-26T12:00:00Z",
            config_hash="test123",
            completed_hands=[(1, 2, 3)],
            all_terminals=["hash_a"],
            total_paths=50,
            best_hand=(1, 2, 3),
            best_score=50.0,
            terminal_counts={1: 1},
            results=None,
        )

        path = tmp_path / "uncompressed"
        saved_path = save_parallel_checkpoint(checkpoint, path, compress=False)

        assert saved_path.exists()
        assert saved_path.suffix == ".json"

        loaded = load_parallel_checkpoint(saved_path)
        assert loaded.completed_hands == checkpoint.completed_hands

    def test_load_nonexistent_raises(self, tmp_path):
        """Loading nonexistent checkpoint should raise FileNotFoundError."""
        from src.ygo_combo.search.parallel import load_parallel_checkpoint

        with pytest.raises(FileNotFoundError):
            load_parallel_checkpoint(tmp_path / "nonexistent.json")

    def test_config_hash_deterministic(self):
        """Config hash should be deterministic for same config."""
        from src.ygo_combo.search.parallel import ParallelConfig, _config_hash

        config1 = ParallelConfig(
            deck=[1, 2, 3, 4, 5],
            hand_size=3,
            max_depth=25,
            max_paths_per_hand=100,
        )
        config2 = ParallelConfig(
            deck=[1, 2, 3, 4, 5],
            hand_size=3,
            max_depth=25,
            max_paths_per_hand=100,
        )

        assert _config_hash(config1) == _config_hash(config2)

    def test_config_hash_differs_for_different_config(self):
        """Config hash should differ for different configs."""
        from src.ygo_combo.search.parallel import ParallelConfig, _config_hash

        config1 = ParallelConfig(deck=[1, 2, 3], hand_size=3, max_depth=25)
        config2 = ParallelConfig(deck=[1, 2, 3, 4], hand_size=3, max_depth=25)

        assert _config_hash(config1) != _config_hash(config2)

    def test_checkpoint_with_results(self, tmp_path):
        """Checkpoint should optionally include full results."""
        from src.ygo_combo.search.parallel import (
            ParallelCheckpoint,
            save_parallel_checkpoint,
            load_parallel_checkpoint,
        )

        results = [
            {
                "hand": [1, 2, 3, 4, 5],
                "terminal_boards": ["hash_a"],
                "best_score": 50.0,
                "paths_explored": 10,
                "depth_reached": 5,
                "duration_ms": 100.0,
            }
        ]

        checkpoint = ParallelCheckpoint(
            version=1,
            timestamp="2026-01-26T12:00:00Z",
            config_hash="test123",
            completed_hands=[(1, 2, 3, 4, 5)],
            all_terminals=["hash_a"],
            total_paths=10,
            best_hand=(1, 2, 3, 4, 5),
            best_score=50.0,
            terminal_counts={1: 1},
            results=results,
        )

        path = tmp_path / "with_results"
        saved_path = save_parallel_checkpoint(checkpoint, path)

        loaded = load_parallel_checkpoint(saved_path)
        assert loaded.results is not None
        assert len(loaded.results) == 1
        assert loaded.results[0]["best_score"] == 50.0


class TestParallelConfigCheckpointOptions:
    """Test checkpoint-related options in ParallelConfig."""

    def test_default_checkpoint_options(self):
        """Default checkpoint options should be sensible."""
        from src.ygo_combo.search.parallel import ParallelConfig

        config = ParallelConfig(deck=[1, 2, 3, 4, 5])

        assert config.checkpoint_path is None
        assert config.checkpoint_interval == 100
        assert config.resume is True
        assert config.save_results is False

    def test_custom_checkpoint_options(self):
        """Custom checkpoint options should be respected."""
        from src.ygo_combo.search.parallel import ParallelConfig
        from pathlib import Path

        config = ParallelConfig(
            deck=[1, 2, 3, 4, 5],
            checkpoint_path=Path("/tmp/test_checkpoint"),
            checkpoint_interval=50,
            resume=False,
            save_results=True,
        )

        assert config.checkpoint_path == Path("/tmp/test_checkpoint")
        assert config.checkpoint_interval == 50
        assert config.resume is False
        assert config.save_results is True


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
