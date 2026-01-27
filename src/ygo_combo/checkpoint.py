"""
Checkpointing for combo enumeration.

Allows saving and resuming long-running enumeration processes.
"""

import json
import gzip
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Set

# Schema version for compatibility checking
CHECKPOINT_SCHEMA_VERSION = 1


@dataclass
class CheckpointMetadata:
    """Metadata about the checkpoint."""
    version: str = "1.0.0"
    schema_version: int = CHECKPOINT_SCHEMA_VERSION
    timestamp: str = ""
    description: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class CheckpointConfig:
    """Configuration captured at checkpoint time."""
    main_deck: List[int]
    extra_deck: List[int]
    starting_hand: List[int]
    dedupe_boards: bool
    dedupe_intermediate: bool
    prioritize_cards: List[int]
    max_depth: int
    max_paths: Optional[int]


@dataclass
class CheckpointProgress:
    """Progress counters at checkpoint time."""
    paths_explored: int
    max_depth_seen: int
    duplicate_boards_skipped: int
    intermediate_states_pruned: int
    terminals_found: int


@dataclass
class TranspositionTableState:
    """Serializable state of the transposition table."""
    max_size: int
    hits: int
    misses: int
    stores: int
    overwrites: int
    evictions: int
    evicted_entries: int
    # entries is a dict: str(hash) -> entry dict
    # We convert int hashes to string keys for JSON compatibility
    entries: Dict[str, Dict]


class Checkpoint:
    """
    Complete checkpoint state for resuming enumeration.

    The checkpoint captures all mutable state needed to resume
    enumeration from exactly where it left off.
    """

    def __init__(self):
        self.metadata = CheckpointMetadata()
        self.config: Optional[CheckpointConfig] = None
        self.progress: Optional[CheckpointProgress] = None
        self.transposition_table: Optional[TranspositionTableState] = None
        self.seen_board_sigs: Set[str] = set()
        self.terminal_boards: Dict[str, List[Dict]] = {}
        self.terminals: List[Dict] = []
        self.failed_at_context: Dict[str, List[int]] = {}

    def to_dict(self) -> Dict:
        """Convert checkpoint to JSON-serializable dictionary."""
        return {
            "metadata": asdict(self.metadata),
            "config": asdict(self.config) if self.config else None,
            "progress": asdict(self.progress) if self.progress else None,
            "transposition_table": asdict(self.transposition_table) if self.transposition_table else None,
            "seen_board_sigs": list(self.seen_board_sigs),
            "terminal_boards": self.terminal_boards,
            "terminals": self.terminals,
            "failed_at_context": self.failed_at_context,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Checkpoint":
        """Reconstruct checkpoint from dictionary."""
        checkpoint = cls()

        # Metadata
        meta = data.get("metadata", {})
        checkpoint.metadata = CheckpointMetadata(
            version=meta.get("version", "1.0.0"),
            schema_version=meta.get("schema_version", 1),
            timestamp=meta.get("timestamp", ""),
            description=meta.get("description", ""),
        )

        # Validate schema version
        if checkpoint.metadata.schema_version > CHECKPOINT_SCHEMA_VERSION:
            raise ValueError(
                f"Checkpoint schema version {checkpoint.metadata.schema_version} "
                f"is newer than supported version {CHECKPOINT_SCHEMA_VERSION}. "
                "Please update the software."
            )

        # Config
        cfg = data.get("config")
        if cfg:
            checkpoint.config = CheckpointConfig(
                main_deck=cfg.get("main_deck", []),
                extra_deck=cfg.get("extra_deck", []),
                starting_hand=cfg.get("starting_hand", []),
                dedupe_boards=cfg.get("dedupe_boards", True),
                dedupe_intermediate=cfg.get("dedupe_intermediate", True),
                prioritize_cards=cfg.get("prioritize_cards", []),
                max_depth=cfg.get("max_depth", 25),
                max_paths=cfg.get("max_paths"),
            )

        # Progress
        prog = data.get("progress")
        if prog:
            checkpoint.progress = CheckpointProgress(
                paths_explored=prog.get("paths_explored", 0),
                max_depth_seen=prog.get("max_depth_seen", 0),
                duplicate_boards_skipped=prog.get("duplicate_boards_skipped", 0),
                intermediate_states_pruned=prog.get("intermediate_states_pruned", 0),
                terminals_found=prog.get("terminals_found", 0),
            )

        # Transposition table
        tt = data.get("transposition_table")
        if tt:
            checkpoint.transposition_table = TranspositionTableState(
                max_size=tt.get("max_size", 1_000_000),
                hits=tt.get("hits", 0),
                misses=tt.get("misses", 0),
                stores=tt.get("stores", 0),
                overwrites=tt.get("overwrites", 0),
                evictions=tt.get("evictions", 0),
                evicted_entries=tt.get("evicted_entries", 0),
                entries=tt.get("entries", {}),
            )

        # Sets and dictionaries
        checkpoint.seen_board_sigs = set(data.get("seen_board_sigs", []))
        checkpoint.terminal_boards = data.get("terminal_boards", {})
        checkpoint.terminals = data.get("terminals", [])
        checkpoint.failed_at_context = data.get("failed_at_context", {})

        return checkpoint


def save_checkpoint(
    checkpoint: Checkpoint,
    path: Path,
    compress: bool = True,
    include_transposition: bool = True,
) -> Path:
    """
    Save a checkpoint to disk.

    Args:
        checkpoint: The checkpoint to save.
        path: Path to save to (without extension).
        compress: Whether to gzip compress the output (recommended for large TT).
        include_transposition: Whether to include the transposition table.
                              Set False to reduce checkpoint size significantly.

    Returns:
        Path to the saved checkpoint file.
    """
    data = checkpoint.to_dict()

    # Optionally exclude transposition table to reduce size
    if not include_transposition:
        data["transposition_table"] = None

    # Determine final path
    if compress:
        final_path = Path(str(path) + ".json.gz")
        with gzip.open(final_path, "wt", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    else:
        final_path = Path(str(path) + ".json")
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    return final_path


def load_checkpoint(path: Path) -> Checkpoint:
    """
    Load a checkpoint from disk.

    Args:
        path: Path to the checkpoint file.

    Returns:
        Loaded Checkpoint object.

    Raises:
        FileNotFoundError: If checkpoint file doesn't exist.
        ValueError: If checkpoint schema is incompatible.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")

    # Detect compression from extension
    if path.suffix == ".gz" or str(path).endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

    return Checkpoint.from_dict(data)


def create_checkpoint_from_engine(engine, description: str = "") -> Checkpoint:
    """
    Create a checkpoint from an EnumerationEngine instance.

    Args:
        engine: The EnumerationEngine to checkpoint.
        description: Optional description for this checkpoint.

    Returns:
        Checkpoint object ready to be saved.
    """
    from .combo_enumeration import MAX_DEPTH, MAX_PATHS

    checkpoint = Checkpoint()

    # Metadata
    checkpoint.metadata = CheckpointMetadata(description=description)

    # Config
    checkpoint.config = CheckpointConfig(
        main_deck=list(engine.main_deck),
        extra_deck=list(engine.extra_deck),
        starting_hand=list(engine._starting_hand) if engine._starting_hand else [],
        dedupe_boards=engine.dedupe_boards,
        dedupe_intermediate=engine.dedupe_intermediate,
        prioritize_cards=list(engine.prioritize_order),
        max_depth=MAX_DEPTH,
        max_paths=MAX_PATHS,
    )

    # Progress
    checkpoint.progress = CheckpointProgress(
        paths_explored=engine.paths_explored,
        max_depth_seen=engine.max_depth_seen,
        duplicate_boards_skipped=engine.duplicate_boards_skipped,
        intermediate_states_pruned=engine.intermediate_states_pruned,
        terminals_found=len(engine.terminals),
    )

    # Transposition table
    tt = engine.transposition_table
    entries = {}
    for hash_key, entry in tt.table.items():
        # Convert int hashes to string for JSON
        str_key = str(hash_key)
        entries[str_key] = {
            "state_hash": str(entry.state_hash) if isinstance(entry.state_hash, int) else entry.state_hash,
            "best_terminal_hash": str(entry.best_terminal_hash) if isinstance(entry.best_terminal_hash, int) else entry.best_terminal_hash,
            "best_terminal_value": entry.best_terminal_value,
            "creation_depth": entry.creation_depth,
            "visit_count": entry.visit_count,
        }

    checkpoint.transposition_table = TranspositionTableState(
        max_size=tt.max_size,
        hits=tt.hits,
        misses=tt.misses,
        stores=tt.stores,
        overwrites=tt.overwrites,
        evictions=tt.evictions,
        evicted_entries=tt.evicted_entries,
        entries=entries,
    )

    # Seen board signatures
    checkpoint.seen_board_sigs = set(engine.seen_board_sigs)

    # Terminal boards (convert TerminalState to dict)
    checkpoint.terminal_boards = {}
    for board_hash, terminals in engine.terminal_boards.items():
        checkpoint.terminal_boards[board_hash] = [
            t.to_dict() if hasattr(t, 'to_dict') else t for t in terminals
        ]

    # Terminals list
    checkpoint.terminals = [
        t.to_dict() if hasattr(t, 'to_dict') else t for t in engine.terminals
    ]

    # Failed context tracking
    checkpoint.failed_at_context = {
        str(k): list(v) for k, v in engine.failed_at_context.items()
    }

    return checkpoint


def restore_engine_from_checkpoint(engine, checkpoint: Checkpoint):
    """
    Restore an EnumerationEngine's state from a checkpoint.

    Note: This does NOT restore the game engine state (lib, duels, etc).
    It only restores the enumeration progress tracking.

    Args:
        engine: The EnumerationEngine to restore into.
        checkpoint: The checkpoint to restore from.

    Raises:
        ValueError: If checkpoint config doesn't match engine config.
    """
    from .types import TerminalState, Action
    from .search.transposition import TranspositionTable, TranspositionEntry

    cfg = checkpoint.config
    if cfg:
        # Validate config matches
        if cfg.main_deck != list(engine.main_deck):
            raise ValueError("Main deck mismatch between checkpoint and engine")
        if cfg.extra_deck != list(engine.extra_deck):
            raise ValueError("Extra deck mismatch between checkpoint and engine")

        # Restore starting hand
        engine._starting_hand = cfg.starting_hand if cfg.starting_hand else None
        engine.dedupe_boards = cfg.dedupe_boards
        engine.dedupe_intermediate = cfg.dedupe_intermediate
        engine.prioritize_cards = set(cfg.prioritize_cards)
        engine.prioritize_order = list(cfg.prioritize_cards)

    # Restore progress
    prog = checkpoint.progress
    if prog:
        engine.paths_explored = prog.paths_explored
        engine.max_depth_seen = prog.max_depth_seen
        engine.duplicate_boards_skipped = prog.duplicate_boards_skipped
        engine.intermediate_states_pruned = prog.intermediate_states_pruned

    # Restore transposition table
    tt_state = checkpoint.transposition_table
    if tt_state:
        engine.transposition_table = TranspositionTable(max_size=tt_state.max_size)
        engine.transposition_table.hits = tt_state.hits
        engine.transposition_table.misses = tt_state.misses
        engine.transposition_table.stores = tt_state.stores
        engine.transposition_table.overwrites = tt_state.overwrites
        engine.transposition_table.evictions = tt_state.evictions
        engine.transposition_table.evicted_entries = tt_state.evicted_entries

        for str_key, entry_data in tt_state.entries.items():
            # Reconstruct hash key (try int first, fall back to string)
            try:
                hash_key = int(str_key)
            except ValueError:
                hash_key = str_key

            # Reconstruct state_hash
            state_hash = entry_data["state_hash"]
            try:
                state_hash = int(state_hash)
            except (ValueError, TypeError):
                pass  # Keep as string

            # Reconstruct best_terminal_hash
            best_terminal_hash = entry_data["best_terminal_hash"]
            try:
                best_terminal_hash = int(best_terminal_hash)
            except (ValueError, TypeError):
                pass  # Keep as string

            entry = TranspositionEntry(
                state_hash=state_hash,
                best_terminal_hash=best_terminal_hash,
                best_terminal_value=entry_data["best_terminal_value"],
                creation_depth=entry_data["creation_depth"],
                visit_count=entry_data["visit_count"],
            )
            engine.transposition_table.table[hash_key] = entry

    # Restore seen board signatures
    engine.seen_board_sigs = set(checkpoint.seen_board_sigs)

    # Restore terminals (reconstruct TerminalState objects)
    engine.terminals = []
    for t_dict in checkpoint.terminals:
        # Reconstruct Action objects
        action_sequence = []
        for a_dict in t_dict.get("action_sequence", []):
            action = Action(
                action_type=a_dict["action_type"],
                message_type=a_dict["message_type"],
                response_value=a_dict["response_value"],
                response_bytes=bytes.fromhex(a_dict["response_bytes"]),
                description=a_dict["description"],
                card_code=a_dict.get("card_code"),
                card_name=a_dict.get("card_name"),
                context_hash=a_dict.get("context_hash"),
            )
            action_sequence.append(action)

        terminal = TerminalState(
            action_sequence=action_sequence,
            board_state=t_dict["board_state"],
            depth=t_dict["depth"],
            state_hash=t_dict["state_hash"],
            termination_reason=t_dict["termination_reason"],
            board_hash=t_dict.get("board_hash"),
        )
        engine.terminals.append(terminal)

    # Restore terminal_boards grouping
    engine.terminal_boards = {}
    for board_hash, term_list in checkpoint.terminal_boards.items():
        engine.terminal_boards[board_hash] = []
        for t_dict in term_list:
            # Reconstruct Action objects
            action_sequence = []
            for a_dict in t_dict.get("action_sequence", []):
                action = Action(
                    action_type=a_dict["action_type"],
                    message_type=a_dict["message_type"],
                    response_value=a_dict["response_value"],
                    response_bytes=bytes.fromhex(a_dict["response_bytes"]),
                    description=a_dict["description"],
                    card_code=a_dict.get("card_code"),
                    card_name=a_dict.get("card_name"),
                    context_hash=a_dict.get("context_hash"),
                )
                action_sequence.append(action)

            terminal = TerminalState(
                action_sequence=action_sequence,
                board_state=t_dict["board_state"],
                depth=t_dict["depth"],
                state_hash=t_dict["state_hash"],
                termination_reason=t_dict["termination_reason"],
                board_hash=t_dict.get("board_hash"),
            )
            engine.terminal_boards[board_hash].append(terminal)

    # Restore failed context tracking
    engine.failed_at_context = {}
    for str_key, codes in checkpoint.failed_at_context.items():
        try:
            hash_key = int(str_key)
        except ValueError:
            hash_key = hash(str_key)  # Fall back to re-hashing
        engine.failed_at_context[hash_key] = set(codes)


class CheckpointManager:
    """
    Manager for automatic periodic checkpointing.

    Usage:
        manager = CheckpointManager(
            checkpoint_dir=Path("./checkpoints"),
            interval_paths=1000,  # Checkpoint every 1000 paths
        )

        # In enumeration loop:
        if manager.should_checkpoint(engine):
            manager.save(engine, "auto")
    """

    def __init__(
        self,
        checkpoint_dir: Path,
        interval_paths: int = 1000,
        interval_seconds: Optional[float] = None,
        max_checkpoints: int = 5,
        compress: bool = True,
        include_transposition: bool = True,
    ):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoints.
            interval_paths: Save checkpoint every N paths explored.
            interval_seconds: Alternative: save every N seconds (if set).
            max_checkpoints: Maximum number of checkpoints to keep (oldest deleted).
            compress: Whether to compress checkpoint files.
            include_transposition: Whether to include transposition table.
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.interval_paths = interval_paths
        self.interval_seconds = interval_seconds
        self.max_checkpoints = max_checkpoints
        self.compress = compress
        self.include_transposition = include_transposition

        self._last_checkpoint_paths = 0
        self._last_checkpoint_time = datetime.now()
        self._checkpoint_count = 0

    def should_checkpoint(self, engine) -> bool:
        """Check if a checkpoint should be saved now."""
        # Check paths interval
        paths_since = engine.paths_explored - self._last_checkpoint_paths
        if paths_since >= self.interval_paths:
            return True

        # Check time interval
        if self.interval_seconds is not None:
            elapsed = (datetime.now() - self._last_checkpoint_time).total_seconds()
            if elapsed >= self.interval_seconds:
                return True

        return False

    def save(self, engine, prefix: str = "checkpoint") -> Path:
        """
        Save a checkpoint for the engine.

        Args:
            engine: The EnumerationEngine to checkpoint.
            prefix: Prefix for the checkpoint filename.

        Returns:
            Path to the saved checkpoint.
        """
        # Create checkpoint
        checkpoint = create_checkpoint_from_engine(
            engine,
            description=f"Auto-checkpoint at {engine.paths_explored} paths",
        )

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}_{engine.paths_explored}paths"
        path = self.checkpoint_dir / filename

        # Save
        saved_path = save_checkpoint(
            checkpoint,
            path,
            compress=self.compress,
            include_transposition=self.include_transposition,
        )

        # Update tracking
        self._last_checkpoint_paths = engine.paths_explored
        self._last_checkpoint_time = datetime.now()
        self._checkpoint_count += 1

        # Cleanup old checkpoints
        self._cleanup_old_checkpoints(prefix)

        return saved_path

    def _cleanup_old_checkpoints(self, prefix: str):
        """Remove old checkpoints beyond max_checkpoints limit."""
        # Find all checkpoints with this prefix
        pattern = f"{prefix}_*.json*"
        checkpoints = sorted(
            self.checkpoint_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        # Remove old ones
        for old_checkpoint in checkpoints[self.max_checkpoints:]:
            old_checkpoint.unlink()

    def get_latest_checkpoint(self, prefix: str = "checkpoint") -> Optional[Path]:
        """Get the most recent checkpoint file."""
        pattern = f"{prefix}_*.json*"
        checkpoints = sorted(
            self.checkpoint_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return checkpoints[0] if checkpoints else None

    def load_latest(self, prefix: str = "checkpoint") -> Optional[Checkpoint]:
        """Load the most recent checkpoint."""
        path = self.get_latest_checkpoint(prefix)
        if path:
            return load_checkpoint(path)
        return None
