"""
Tests for the checkpoint module.

Tests save/load round-trip, schema compatibility, and engine restoration.
"""

import pytest
import tempfile
import json
import gzip
from pathlib import Path
from datetime import datetime

from src.ygo_combo.checkpoint import (
    Checkpoint,
    CheckpointMetadata,
    CheckpointConfig,
    CheckpointProgress,
    TranspositionTableState,
    CHECKPOINT_SCHEMA_VERSION,
    save_checkpoint,
    load_checkpoint,
    create_checkpoint_from_engine,
    restore_engine_from_checkpoint,
    CheckpointManager,
)
from src.ygo_combo.search.transposition import TranspositionTable, TranspositionEntry


class TestCheckpointMetadata:
    """Test CheckpointMetadata dataclass."""

    def test_default_timestamp(self):
        """Metadata should auto-populate timestamp."""
        meta = CheckpointMetadata()
        assert meta.timestamp != ""
        assert "T" in meta.timestamp  # ISO format

    def test_custom_values(self):
        """Metadata should accept custom values."""
        meta = CheckpointMetadata(
            version="2.0.0",
            schema_version=2,
            timestamp="2026-01-26T12:00:00Z",
            description="Test checkpoint",
        )
        assert meta.version == "2.0.0"
        assert meta.schema_version == 2
        assert meta.timestamp == "2026-01-26T12:00:00Z"
        assert meta.description == "Test checkpoint"


class TestCheckpointConfig:
    """Test CheckpointConfig dataclass."""

    def test_all_fields(self):
        """Config should store all enumeration configuration."""
        cfg = CheckpointConfig(
            main_deck=[1, 2, 3],
            extra_deck=[4, 5, 6],
            starting_hand=[1, 2],
            dedupe_boards=True,
            dedupe_intermediate=False,
            prioritize_cards=[1],
            max_depth=25,
            max_paths=1000,
        )
        assert cfg.main_deck == [1, 2, 3]
        assert cfg.extra_deck == [4, 5, 6]
        assert cfg.starting_hand == [1, 2]
        assert cfg.dedupe_boards is True
        assert cfg.dedupe_intermediate is False
        assert cfg.prioritize_cards == [1]
        assert cfg.max_depth == 25
        assert cfg.max_paths == 1000


class TestCheckpointProgress:
    """Test CheckpointProgress dataclass."""

    def test_all_counters(self):
        """Progress should store all enumeration counters."""
        prog = CheckpointProgress(
            paths_explored=1000,
            max_depth_seen=17,
            duplicate_boards_skipped=100,
            intermediate_states_pruned=50,
            terminals_found=15,
        )
        assert prog.paths_explored == 1000
        assert prog.max_depth_seen == 17
        assert prog.duplicate_boards_skipped == 100
        assert prog.intermediate_states_pruned == 50
        assert prog.terminals_found == 15


class TestTranspositionTableState:
    """Test TranspositionTableState dataclass."""

    def test_empty_entries(self):
        """TranspositionTableState should handle empty entries."""
        tt_state = TranspositionTableState(
            max_size=1000000,
            hits=100,
            misses=200,
            stores=300,
            overwrites=50,
            evictions=0,
            evicted_entries=0,
            entries={},
        )
        assert tt_state.max_size == 1000000
        assert tt_state.hits == 100
        assert len(tt_state.entries) == 0

    def test_with_entries(self):
        """TranspositionTableState should store entries."""
        entries = {
            "12345": {
                "state_hash": "12345",
                "best_terminal_hash": "67890",
                "best_terminal_value": 0.75,
                "creation_depth": 10,
                "visit_count": 3,
            }
        }
        tt_state = TranspositionTableState(
            max_size=1000000,
            hits=100,
            misses=200,
            stores=300,
            overwrites=50,
            evictions=0,
            evicted_entries=0,
            entries=entries,
        )
        assert len(tt_state.entries) == 1
        assert tt_state.entries["12345"]["best_terminal_value"] == 0.75


class TestCheckpoint:
    """Test Checkpoint class."""

    def test_to_dict_empty(self):
        """Empty checkpoint should serialize."""
        cp = Checkpoint()
        data = cp.to_dict()
        assert "metadata" in data
        assert "config" in data
        assert "progress" in data
        assert "terminals" in data
        assert data["terminals"] == []

    def test_to_dict_with_data(self):
        """Checkpoint with data should serialize completely."""
        cp = Checkpoint()
        cp.metadata = CheckpointMetadata(description="Test")
        cp.config = CheckpointConfig(
            main_deck=[1],
            extra_deck=[2],
            starting_hand=[1],
            dedupe_boards=True,
            dedupe_intermediate=True,
            prioritize_cards=[],
            max_depth=25,
            max_paths=None,
        )
        cp.progress = CheckpointProgress(
            paths_explored=100,
            max_depth_seen=10,
            duplicate_boards_skipped=5,
            intermediate_states_pruned=3,
            terminals_found=2,
        )
        cp.seen_board_sigs = {"sig1", "sig2"}
        cp.terminals = [{"test": "terminal"}]

        data = cp.to_dict()
        assert data["metadata"]["description"] == "Test"
        assert data["config"]["main_deck"] == [1]
        assert data["progress"]["paths_explored"] == 100
        assert set(data["seen_board_sigs"]) == {"sig1", "sig2"}
        assert len(data["terminals"]) == 1

    def test_from_dict_round_trip(self):
        """Checkpoint should survive to_dict/from_dict round trip."""
        original = Checkpoint()
        original.metadata = CheckpointMetadata(
            version="1.0.0",
            schema_version=1,
            description="Round trip test",
        )
        original.config = CheckpointConfig(
            main_deck=[60764609, 81275020],
            extra_deck=[12345678],
            starting_hand=[60764609],
            dedupe_boards=True,
            dedupe_intermediate=False,
            prioritize_cards=[60764609],
            max_depth=30,
            max_paths=5000,
        )
        original.progress = CheckpointProgress(
            paths_explored=500,
            max_depth_seen=15,
            duplicate_boards_skipped=20,
            intermediate_states_pruned=10,
            terminals_found=8,
        )
        original.seen_board_sigs = {"hash1", "hash2", "hash3"}
        original.failed_at_context = {"123": [1, 2, 3], "456": [4, 5]}

        # Round trip
        data = original.to_dict()
        restored = Checkpoint.from_dict(data)

        # Verify
        assert restored.metadata.description == "Round trip test"
        assert restored.config.main_deck == [60764609, 81275020]
        assert restored.config.max_paths == 5000
        assert restored.progress.paths_explored == 500
        assert restored.seen_board_sigs == {"hash1", "hash2", "hash3"}
        assert restored.failed_at_context == {"123": [1, 2, 3], "456": [4, 5]}

    def test_from_dict_version_check(self):
        """Loading newer schema version should raise error."""
        data = {
            "metadata": {
                "schema_version": CHECKPOINT_SCHEMA_VERSION + 1,
            }
        }
        with pytest.raises(ValueError, match="newer than supported"):
            Checkpoint.from_dict(data)


class TestSaveLoadCheckpoint:
    """Test save_checkpoint and load_checkpoint functions."""

    def test_save_uncompressed(self):
        """Save checkpoint as uncompressed JSON."""
        cp = Checkpoint()
        cp.metadata = CheckpointMetadata(description="Uncompressed test")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_checkpoint"
            saved_path = save_checkpoint(cp, path, compress=False)

            assert saved_path.exists()
            assert saved_path.suffix == ".json"

            # Verify it's valid JSON
            with open(saved_path) as f:
                data = json.load(f)
            assert data["metadata"]["description"] == "Uncompressed test"

    def test_save_compressed(self):
        """Save checkpoint as gzipped JSON."""
        cp = Checkpoint()
        cp.metadata = CheckpointMetadata(description="Compressed test")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_checkpoint"
            saved_path = save_checkpoint(cp, path, compress=True)

            assert saved_path.exists()
            assert str(saved_path).endswith(".json.gz")

            # Verify it's valid gzipped JSON
            with gzip.open(saved_path, "rt") as f:
                data = json.load(f)
            assert data["metadata"]["description"] == "Compressed test"

    def test_save_without_transposition(self):
        """Save checkpoint without transposition table."""
        cp = Checkpoint()
        cp.transposition_table = TranspositionTableState(
            max_size=1000000,
            hits=100,
            misses=200,
            stores=300,
            overwrites=50,
            evictions=0,
            evicted_entries=0,
            entries={"key": {"data": "value"}},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_checkpoint"
            saved_path = save_checkpoint(
                cp, path, compress=False, include_transposition=False
            )

            with open(saved_path) as f:
                data = json.load(f)
            assert data["transposition_table"] is None

    def test_load_checkpoint(self):
        """Load checkpoint from file."""
        cp = Checkpoint()
        cp.metadata = CheckpointMetadata(description="Load test")
        cp.progress = CheckpointProgress(
            paths_explored=999,
            max_depth_seen=20,
            duplicate_boards_skipped=50,
            intermediate_states_pruned=25,
            terminals_found=10,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Save
            path = Path(tmpdir) / "test_checkpoint"
            saved_path = save_checkpoint(cp, path, compress=True)

            # Load
            loaded = load_checkpoint(saved_path)

            assert loaded.metadata.description == "Load test"
            assert loaded.progress.paths_explored == 999
            assert loaded.progress.terminals_found == 10

    def test_load_nonexistent_raises(self):
        """Loading non-existent checkpoint should raise."""
        with pytest.raises(FileNotFoundError):
            load_checkpoint(Path("/nonexistent/checkpoint.json"))

    def test_save_load_round_trip_with_all_data(self):
        """Complete round trip with all checkpoint data."""
        cp = Checkpoint()
        cp.metadata = CheckpointMetadata(
            version="1.0.0",
            schema_version=1,
            description="Full round trip",
        )
        cp.config = CheckpointConfig(
            main_deck=[1, 2, 3, 4, 5],
            extra_deck=[10, 20, 30],
            starting_hand=[1, 2, 3, 4, 5],
            dedupe_boards=True,
            dedupe_intermediate=True,
            prioritize_cards=[1, 2],
            max_depth=25,
            max_paths=10000,
        )
        cp.progress = CheckpointProgress(
            paths_explored=5000,
            max_depth_seen=18,
            duplicate_boards_skipped=200,
            intermediate_states_pruned=100,
            terminals_found=25,
        )
        cp.transposition_table = TranspositionTableState(
            max_size=1000000,
            hits=3000,
            misses=2000,
            stores=4000,
            overwrites=100,
            evictions=0,
            evicted_entries=0,
            entries={
                "hash1": {
                    "state_hash": "hash1",
                    "best_terminal_hash": "term1",
                    "best_terminal_value": 0.8,
                    "creation_depth": 5,
                    "visit_count": 10,
                },
                "hash2": {
                    "state_hash": "hash2",
                    "best_terminal_hash": "term2",
                    "best_terminal_value": 0.6,
                    "creation_depth": 8,
                    "visit_count": 5,
                },
            },
        )
        cp.seen_board_sigs = {"sig1", "sig2", "sig3"}
        cp.terminal_boards = {
            "board1": [{"test": "data1"}],
            "board2": [{"test": "data2a"}, {"test": "data2b"}],
        }
        cp.terminals = [{"terminal": 1}, {"terminal": 2}]
        cp.failed_at_context = {"ctx1": [100, 200], "ctx2": [300]}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Save compressed
            path = Path(tmpdir) / "full_checkpoint"
            saved_path = save_checkpoint(cp, path, compress=True)

            # Load
            loaded = load_checkpoint(saved_path)

            # Verify everything
            assert loaded.metadata.description == "Full round trip"
            assert loaded.config.main_deck == [1, 2, 3, 4, 5]
            assert loaded.config.max_paths == 10000
            assert loaded.progress.paths_explored == 5000
            assert loaded.progress.terminals_found == 25
            assert loaded.transposition_table.hits == 3000
            assert len(loaded.transposition_table.entries) == 2
            assert loaded.seen_board_sigs == {"sig1", "sig2", "sig3"}
            assert len(loaded.terminal_boards) == 2
            assert len(loaded.terminals) == 2
            assert loaded.failed_at_context == {"ctx1": [100, 200], "ctx2": [300]}


class TestCheckpointManager:
    """Test CheckpointManager class."""

    def test_should_checkpoint_by_paths(self):
        """Manager should trigger checkpoint after interval paths."""

        class MockEngine:
            paths_explored = 0

        manager = CheckpointManager(
            checkpoint_dir=Path("/tmp"),
            interval_paths=100,
        )
        engine = MockEngine()

        # Should not checkpoint at 0
        assert not manager.should_checkpoint(engine)

        # Should not checkpoint at 50
        engine.paths_explored = 50
        assert not manager.should_checkpoint(engine)

        # Should checkpoint at 100
        engine.paths_explored = 100
        assert manager.should_checkpoint(engine)

    def test_save_creates_file(self):
        """Manager save should create checkpoint file."""

        class MockEngine:
            paths_explored = 500
            max_depth_seen = 15
            duplicate_boards_skipped = 10
            intermediate_states_pruned = 5
            main_deck = [1, 2, 3]
            extra_deck = [10, 20]
            _starting_hand = [1, 2]
            dedupe_boards = True
            dedupe_intermediate = True
            prioritize_cards = set()
            prioritize_order = []
            terminals = []
            seen_board_sigs = set()
            terminal_boards = {}
            failed_at_context = {}
            transposition_table = TranspositionTable(max_size=1000)

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                checkpoint_dir=Path(tmpdir),
                interval_paths=100,
                max_checkpoints=3,
            )
            engine = MockEngine()

            saved_path = manager.save(engine, prefix="test")

            assert saved_path.exists()
            assert "test_" in saved_path.name
            assert "500paths" in saved_path.name

    def test_cleanup_old_checkpoints(self):
        """Manager should remove old checkpoints beyond limit."""

        class MockEngine:
            paths_explored = 0
            max_depth_seen = 0
            duplicate_boards_skipped = 0
            intermediate_states_pruned = 0
            main_deck = [1]
            extra_deck = [2]
            _starting_hand = [1]
            dedupe_boards = True
            dedupe_intermediate = True
            prioritize_cards = set()
            prioritize_order = []
            terminals = []
            seen_board_sigs = set()
            terminal_boards = {}
            failed_at_context = {}
            transposition_table = TranspositionTable(max_size=100)

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                checkpoint_dir=Path(tmpdir),
                interval_paths=100,
                max_checkpoints=2,
                compress=False,  # Faster for testing
            )
            engine = MockEngine()

            # Create 4 checkpoints
            for i in range(4):
                engine.paths_explored = (i + 1) * 100
                manager._last_checkpoint_paths = 0  # Force checkpoint
                manager.save(engine, prefix="cleanup_test")

            # Should only have 2 checkpoints
            checkpoints = list(Path(tmpdir).glob("cleanup_test_*.json"))
            assert len(checkpoints) == 2

    def test_get_latest_checkpoint(self):
        """Manager should find most recent checkpoint."""

        class MockEngine:
            paths_explored = 100
            max_depth_seen = 5
            duplicate_boards_skipped = 0
            intermediate_states_pruned = 0
            main_deck = [1]
            extra_deck = [2]
            _starting_hand = [1]
            dedupe_boards = True
            dedupe_intermediate = True
            prioritize_cards = set()
            prioritize_order = []
            terminals = []
            seen_board_sigs = set()
            terminal_boards = {}
            failed_at_context = {}
            transposition_table = TranspositionTable(max_size=100)

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                checkpoint_dir=Path(tmpdir),
                interval_paths=100,
                max_checkpoints=5,
            )
            engine = MockEngine()

            # Create checkpoint
            manager._last_checkpoint_paths = 0
            manager.save(engine, prefix="latest_test")

            # Get latest
            latest = manager.get_latest_checkpoint(prefix="latest_test")
            assert latest is not None
            assert "latest_test" in latest.name

    def test_load_latest(self):
        """Manager should load most recent checkpoint."""

        class MockEngine:
            paths_explored = 777
            max_depth_seen = 12
            duplicate_boards_skipped = 5
            intermediate_states_pruned = 3
            main_deck = [1, 2, 3]
            extra_deck = [4, 5]
            _starting_hand = [1, 2]
            dedupe_boards = True
            dedupe_intermediate = False
            prioritize_cards = set()
            prioritize_order = []
            terminals = []
            seen_board_sigs = {"sig1"}
            terminal_boards = {}
            failed_at_context = {}
            transposition_table = TranspositionTable(max_size=100)

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                checkpoint_dir=Path(tmpdir),
                interval_paths=100,
            )
            engine = MockEngine()

            # Create checkpoint
            manager._last_checkpoint_paths = 0
            manager.save(engine, prefix="load_latest")

            # Load latest
            loaded = manager.load_latest(prefix="load_latest")
            assert loaded is not None
            assert loaded.progress.paths_explored == 777
            assert loaded.progress.max_depth_seen == 12
            assert "sig1" in loaded.seen_board_sigs

    def test_no_latest_returns_none(self):
        """Manager should return None if no checkpoints exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(checkpoint_dir=Path(tmpdir))
            assert manager.get_latest_checkpoint() is None
            assert manager.load_latest() is None


class TestCreateCheckpointFromEngine:
    """Test create_checkpoint_from_engine function."""

    def test_captures_all_state(self):
        """Function should capture all engine state."""

        class MockEngine:
            paths_explored = 1234
            max_depth_seen = 20
            duplicate_boards_skipped = 100
            intermediate_states_pruned = 50
            main_deck = [1, 2, 3, 4, 5]
            extra_deck = [10, 20, 30]
            _starting_hand = [1, 2, 3]
            dedupe_boards = True
            dedupe_intermediate = True
            prioritize_cards = {1}
            prioritize_order = [1]
            terminals = []
            seen_board_sigs = {"sig1", "sig2"}
            terminal_boards = {}
            failed_at_context = {123: {1, 2}, 456: {3}}
            transposition_table = TranspositionTable(max_size=500)

        engine = MockEngine()
        engine.transposition_table.hits = 1000
        engine.transposition_table.misses = 500

        cp = create_checkpoint_from_engine(engine, "Test capture")

        assert cp.metadata.description == "Test capture"
        assert cp.config.main_deck == [1, 2, 3, 4, 5]
        assert cp.config.starting_hand == [1, 2, 3]
        assert cp.progress.paths_explored == 1234
        assert cp.progress.max_depth_seen == 20
        assert cp.transposition_table.hits == 1000
        assert cp.seen_board_sigs == {"sig1", "sig2"}
        # Note: dict keys become strings, set values become lists
        assert "123" in cp.failed_at_context
        assert set(cp.failed_at_context["123"]) == {1, 2}


class TestRestoreEngineFromCheckpoint:
    """Test restore_engine_from_checkpoint function."""

    def test_restores_progress(self):
        """Restore should update engine progress counters."""

        class MockEngine:
            paths_explored = 0
            max_depth_seen = 0
            duplicate_boards_skipped = 0
            intermediate_states_pruned = 0
            main_deck = [1, 2, 3]
            extra_deck = [10, 20]
            _starting_hand = None
            dedupe_boards = False
            dedupe_intermediate = False
            prioritize_cards = set()
            prioritize_order = []
            terminals = []
            seen_board_sigs = set()
            terminal_boards = {}
            failed_at_context = {}
            transposition_table = TranspositionTable(max_size=100)

        # Create checkpoint with progress
        cp = Checkpoint()
        cp.config = CheckpointConfig(
            main_deck=[1, 2, 3],
            extra_deck=[10, 20],
            starting_hand=[1, 2],
            dedupe_boards=True,
            dedupe_intermediate=True,
            prioritize_cards=[1],
            max_depth=25,
            max_paths=1000,
        )
        cp.progress = CheckpointProgress(
            paths_explored=500,
            max_depth_seen=15,
            duplicate_boards_skipped=50,
            intermediate_states_pruned=25,
            terminals_found=10,
        )
        cp.seen_board_sigs = {"sig1", "sig2"}
        cp.failed_at_context = {"123": [1, 2]}

        engine = MockEngine()
        restore_engine_from_checkpoint(engine, cp)

        # Verify progress restored
        assert engine.paths_explored == 500
        assert engine.max_depth_seen == 15
        assert engine.duplicate_boards_skipped == 50
        assert engine.intermediate_states_pruned == 25
        assert engine._starting_hand == [1, 2]
        assert engine.dedupe_boards is True
        assert engine.dedupe_intermediate is True
        assert engine.prioritize_cards == {1}
        assert engine.seen_board_sigs == {"sig1", "sig2"}
        assert 123 in engine.failed_at_context
        assert engine.failed_at_context[123] == {1, 2}

    def test_restores_transposition_table(self):
        """Restore should rebuild transposition table."""

        class MockEngine:
            paths_explored = 0
            max_depth_seen = 0
            duplicate_boards_skipped = 0
            intermediate_states_pruned = 0
            main_deck = [1, 2]
            extra_deck = [3, 4]
            _starting_hand = None
            dedupe_boards = True
            dedupe_intermediate = True
            prioritize_cards = set()
            prioritize_order = []
            terminals = []
            seen_board_sigs = set()
            terminal_boards = {}
            failed_at_context = {}
            transposition_table = TranspositionTable(max_size=100)

        # Create checkpoint with transposition table
        cp = Checkpoint()
        cp.config = CheckpointConfig(
            main_deck=[1, 2],
            extra_deck=[3, 4],
            starting_hand=[1],
            dedupe_boards=True,
            dedupe_intermediate=True,
            prioritize_cards=[],
            max_depth=25,
            max_paths=None,
        )
        cp.transposition_table = TranspositionTableState(
            max_size=500000,
            hits=1000,
            misses=500,
            stores=1500,
            overwrites=50,
            evictions=0,
            evicted_entries=0,
            entries={
                "12345": {
                    "state_hash": "12345",
                    "best_terminal_hash": "67890",
                    "best_terminal_value": 0.75,
                    "creation_depth": 10,
                    "visit_count": 5,
                },
            },
        )

        engine = MockEngine()
        restore_engine_from_checkpoint(engine, cp)

        # Verify transposition table restored
        assert engine.transposition_table.max_size == 500000
        assert engine.transposition_table.hits == 1000
        assert engine.transposition_table.misses == 500
        assert len(engine.transposition_table.table) == 1

        # Verify entry contents
        entry = engine.transposition_table.table.get(12345) or engine.transposition_table.table.get("12345")
        assert entry is not None
        assert entry.best_terminal_value == 0.75
        assert entry.creation_depth == 10
        assert entry.visit_count == 5

    def test_deck_mismatch_raises(self):
        """Restore should raise if deck doesn't match."""

        class MockEngine:
            main_deck = [1, 2, 3]
            extra_deck = [10, 20]

        cp = Checkpoint()
        cp.config = CheckpointConfig(
            main_deck=[4, 5, 6],  # Different deck
            extra_deck=[10, 20],
            starting_hand=[],
            dedupe_boards=True,
            dedupe_intermediate=True,
            prioritize_cards=[],
            max_depth=25,
            max_paths=None,
        )

        engine = MockEngine()
        with pytest.raises(ValueError, match="Main deck mismatch"):
            restore_engine_from_checkpoint(engine, cp)

    def test_save_restore_round_trip(self):
        """Complete round trip: engine -> checkpoint -> file -> checkpoint -> engine."""

        class MockEngine:
            paths_explored = 789
            max_depth_seen = 18
            duplicate_boards_skipped = 30
            intermediate_states_pruned = 15
            main_deck = [60764609, 81275020]
            extra_deck = [12345678]
            _starting_hand = [60764609]
            dedupe_boards = True
            dedupe_intermediate = True
            prioritize_cards = {60764609}
            prioritize_order = [60764609]
            terminals = []
            seen_board_sigs = {"board_sig_1", "board_sig_2"}
            terminal_boards = {}
            failed_at_context = {999: {111, 222}}
            transposition_table = TranspositionTable(max_size=1000)

        original_engine = MockEngine()
        original_engine.transposition_table.hits = 500
        original_engine.transposition_table.misses = 250

        # Add an entry to transposition table
        original_engine.transposition_table.table["test_hash"] = TranspositionEntry(
            state_hash="test_hash",
            best_terminal_hash="best_hash",
            best_terminal_value=0.9,
            creation_depth=12,
            visit_count=7,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create checkpoint from original engine
            cp = create_checkpoint_from_engine(original_engine, "Round trip test")

            # Save to file
            path = Path(tmpdir) / "round_trip"
            saved_path = save_checkpoint(cp, path, compress=True)

            # Load from file
            loaded_cp = load_checkpoint(saved_path)

            # Create new engine and restore
            class NewMockEngine:
                paths_explored = 0
                max_depth_seen = 0
                duplicate_boards_skipped = 0
                intermediate_states_pruned = 0
                main_deck = [60764609, 81275020]
                extra_deck = [12345678]
                _starting_hand = None
                dedupe_boards = False
                dedupe_intermediate = False
                prioritize_cards = set()
                prioritize_order = []
                terminals = []
                seen_board_sigs = set()
                terminal_boards = {}
                failed_at_context = {}
                transposition_table = TranspositionTable(max_size=100)

            restored_engine = NewMockEngine()
            restore_engine_from_checkpoint(restored_engine, loaded_cp)

            # Verify state matches original
            assert restored_engine.paths_explored == 789
            assert restored_engine.max_depth_seen == 18
            assert restored_engine.duplicate_boards_skipped == 30
            assert restored_engine._starting_hand == [60764609]
            assert restored_engine.dedupe_boards is True
            assert restored_engine.prioritize_cards == {60764609}
            assert restored_engine.seen_board_sigs == {"board_sig_1", "board_sig_2"}
            assert 999 in restored_engine.failed_at_context
            assert restored_engine.failed_at_context[999] == {111, 222}

            # Verify transposition table
            assert restored_engine.transposition_table.hits == 500
            assert len(restored_engine.transposition_table.table) == 1
