"""
Duel creation and setup utilities.

Functions for loading deck libraries and creating fresh duels with proper setup.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Support both relative imports (package) and absolute imports (sys.path)
try:
    from .bindings import (
        ffi,
        LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA,
        POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
    )
    from .interface import (
        preload_utility_scripts,
        py_card_reader, py_card_reader_done, py_script_reader, py_log_handler,
    )
    from .paths import LOCKED_LIBRARY_PATH
except ImportError:
    from engine.bindings import (
        ffi,
        LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA,
        POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
    )
    from engine.interface import (
        preload_utility_scripts,
        py_card_reader, py_card_reader_done, py_script_reader, py_log_handler,
    )
    from engine.paths import LOCKED_LIBRARY_PATH

logger = logging.getLogger(__name__)

# Constants path (same directory as locked library)
CONSTANTS_PATH = LOCKED_LIBRARY_PATH.parent / "constants.json"


def _load_constants() -> Dict[str, Any]:
    """Load pipeline constants from config/constants.json."""
    if not CONSTANTS_PATH.exists():
        raise FileNotFoundError(
            f"constants.json not found at {CONSTANTS_PATH}. "
            "This file is required - do not use hardcoded card IDs."
        )
    with open(CONSTANTS_PATH) as f:
        return json.load(f)


# Load constants on module import
_CONSTANTS = _load_constants()

# Starting state - loaded from config (verified against cards.cdb)
ENGRAVER = _CONSTANTS["default_hand"]["starter"]  # Fiendsmith Engraver
HOLACTIE = _CONSTANTS["default_hand"]["filler"]   # Holactie the Creator of Light


def load_locked_library() -> Dict[str, Any]:
    """Load the verified locked library.

    Returns:
        Dict containing card library with metadata

    Raises:
        FileNotFoundError: If locked library file doesn't exist
    """
    if not LOCKED_LIBRARY_PATH.exists():
        raise FileNotFoundError(f"Locked library not found: {LOCKED_LIBRARY_PATH}")

    with open(LOCKED_LIBRARY_PATH) as f:
        library = json.load(f)

    meta = library.get("_meta", {})
    if not meta.get("verified", False):
        logger.warning("Locked library not yet verified!")
    if library.get("_LOCKED", False):
        logger.info("Using LOCKED library - do not modify without user approval")

    return library


def get_deck_lists(library: Dict[str, Any]) -> Tuple[List[int], List[int]]:
    """Extract main deck and extra deck card lists from library.

    Args:
        library: Loaded library dict from load_locked_library()

    Returns:
        Tuple of (main_deck_passcodes, extra_deck_passcodes)
    """
    main_deck: List[int] = []
    extra_deck: List[int] = []

    for passcode_str, card in library["cards"].items():
        passcode = int(passcode_str)
        if card["is_extra_deck"]:
            extra_deck.append(passcode)
        else:
            main_deck.append(passcode)

    return main_deck, extra_deck


def create_duel(lib, main_deck_cards: List[int], extra_deck_cards: List[int],
                starting_hand: Optional[List[int]] = None):
    """Create a fresh duel with the starting state.

    Args:
        lib: CFFI library handle
        main_deck_cards: List of main deck passcodes
        extra_deck_cards: List of extra deck passcodes
        starting_hand: Optional list of 5 passcodes for starting hand.
                       If None, uses default [ENGRAVER, HOLACTIE, HOLACTIE, HOLACTIE, HOLACTIE]

    Returns:
        Duel handle for use with OCG_* functions

    Raises:
        RuntimeError: If duel creation fails
    """
    options = ffi.new("OCG_DuelOptions*")

    # Fixed seed for reproducibility
    options.seed[0] = 12345
    options.seed[1] = 67890
    options.seed[2] = 11111
    options.seed[3] = 22222

    options.flags = (5 << 16)  # MR5

    # Player 0 (us)
    options.team1.startingLP = 8000
    options.team1.startingDrawCount = 0  # Hand set manually
    options.team1.drawCountPerTurn = 0   # No draws during combo

    # Player 1 (opponent - does nothing)
    options.team2.startingLP = 8000
    options.team2.startingDrawCount = 5
    options.team2.drawCountPerTurn = 1

    # Callbacks
    options.cardReader = py_card_reader
    options.scriptReader = py_script_reader
    options.logHandler = py_log_handler
    options.cardReaderDone = py_card_reader_done

    duel_ptr = ffi.new("OCG_Duel*")
    result = lib.OCG_CreateDuel(duel_ptr, options)

    if result != 0:
        raise RuntimeError(f"Failed to create duel: {result}")

    duel = duel_ptr[0]
    preload_utility_scripts(lib, duel)

    # === HAND: Use provided hand or default ===
    if starting_hand is not None:
        hand_cards = list(starting_hand)
        # Pad with HOLACTIE if less than 5 cards
        while len(hand_cards) < 5:
            hand_cards.append(HOLACTIE)
        # Truncate if more than 5 cards
        hand_cards = hand_cards[:5]
    else:
        # Default: 1 Engraver + 4 Holactie (original behavior)
        hand_cards = [ENGRAVER, HOLACTIE, HOLACTIE, HOLACTIE, HOLACTIE]

    for i, code in enumerate(hand_cards):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_HAND
        card_info.seq = i
        card_info.pos = POS_FACEUP_ATTACK
        lib.OCG_DuelNewCard(duel, card_info)

    # === MAIN DECK ===
    # Include all main deck cards, pad to 40 with Holactie
    deck = list(main_deck_cards)
    while len(deck) < 40:
        deck.append(HOLACTIE)

    for i, code in enumerate(deck):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_DECK
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        lib.OCG_DuelNewCard(duel, card_info)

    # === EXTRA DECK ===
    for i, code in enumerate(extra_deck_cards):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_EXTRA
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        lib.OCG_DuelNewCard(duel, card_info)

    # === OPPONENT DECK (Holactie filler) ===
    for i in range(40):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 1
        card_info.duelist = 0
        card_info.code = HOLACTIE
        card_info.con = 1
        card_info.loc = LOCATION_DECK
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        lib.OCG_DuelNewCard(duel, card_info)

    return duel


__all__ = [
    'ENGRAVER',
    'HOLACTIE',
    'load_locked_library',
    'get_deck_lists',
    'create_duel',
]
