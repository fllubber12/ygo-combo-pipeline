"""
CFFI bindings for ygopro-core (edo9300 fork).

This module provides Python bindings to the OCG Core library,
enabling programmatic duel simulation using the official Yu-Gi-Oh! engine.

Usage:
    from src.cffi import ffi, load_library

    lib = load_library()
    # ... use lib.OCG_* functions
"""

from .ocg_bindings import (
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

__all__ = [
    "ffi",
    "load_library",
    "get_lib",
    "LOCATION_DECK",
    "LOCATION_HAND",
    "LOCATION_MZONE",
    "LOCATION_SZONE",
    "LOCATION_GRAVE",
    "LOCATION_REMOVED",
    "LOCATION_EXTRA",
    "LOCATION_OVERLAY",
    "LOCATION_ONFIELD",
    "POS_FACEUP_ATTACK",
    "POS_FACEDOWN_ATTACK",
    "POS_FACEUP_DEFENSE",
    "POS_FACEDOWN_DEFENSE",
    "POS_FACEUP",
    "POS_FACEDOWN",
    "DUEL_FLAGS_MR5",
]
