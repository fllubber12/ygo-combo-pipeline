"""
YGO Combo Pipeline: Exhaustive Yu-Gi-Oh! Combo Enumeration.

This package provides Python bindings to the ygopro-core OCG library,
enabling programmatic duel simulation and combo path analysis.

Submodules:
    engine   - Core OCG bindings, interface, and state representation
    search   - Search algorithms (IDDFS, parallel, transposition tables)
    cards    - Card validation and role classification
    encoding - ML-compatible state encoding
    utils    - Utility functions (Zobrist hashing)
    enumeration - Message parsing and response building

Usage:
    from ygo_combo.engine import ffi, load_library
    from ygo_combo.search import IterativeDeepeningSearch, SearchConfig
    from ygo_combo.cards import CardValidator
"""

from .engine.bindings import (
    ffi,
    load_library,
    get_lib,
    # Location constants
    LOCATION_DECK,
    LOCATION_HAND,
    LOCATION_MZONE,
    LOCATION_SZONE,
    LOCATION_GRAVE,
    LOCATION_REMOVED,
    LOCATION_EXTRA,
    LOCATION_OVERLAY,
    LOCATION_ONFIELD,
    # Position constants
    POS_FACEUP_ATTACK,
    POS_FACEDOWN_ATTACK,
    POS_FACEUP_DEFENSE,
    POS_FACEDOWN_DEFENSE,
    POS_FACEUP,
    POS_FACEDOWN,
    # Duel flags
    DUEL_FLAGS_MR5,
)

# Shared types
from .types import Action, TerminalState

# Ranking
from .ranking import ComboScore, ComboRanker, SortKey, rank_terminals

# Sampling
from .sampling import (
    StratifiedSampler,
    SamplingConfig,
    SamplingResult,
    HandComposition,
    sample_hands,
)

__all__ = [
    # Bindings
    "ffi",
    "load_library",
    "get_lib",
    # Location constants
    "LOCATION_DECK",
    "LOCATION_HAND",
    "LOCATION_MZONE",
    "LOCATION_SZONE",
    "LOCATION_GRAVE",
    "LOCATION_REMOVED",
    "LOCATION_EXTRA",
    "LOCATION_OVERLAY",
    "LOCATION_ONFIELD",
    # Position constants
    "POS_FACEUP_ATTACK",
    "POS_FACEDOWN_ATTACK",
    "POS_FACEUP_DEFENSE",
    "POS_FACEDOWN_DEFENSE",
    "POS_FACEUP",
    "POS_FACEDOWN",
    "DUEL_FLAGS_MR5",
    # Shared types
    "Action",
    "TerminalState",
    # Ranking
    "ComboScore",
    "ComboRanker",
    "SortKey",
    "rank_terminals",
    # Sampling
    "StratifiedSampler",
    "SamplingConfig",
    "SamplingResult",
    "HandComposition",
    "sample_hands",
]
