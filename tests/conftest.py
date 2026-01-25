"""Shared pytest fixtures for ygo-combo-pipeline tests."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "cffi"))


# Card passcode constants for tests
CAESAR = 79559912
REQUIEM = 2463794
ENGRAVER = 60764609
SP_LITTLE_KNIGHT = 29301450
SEQUENCE = 49867899
HOLACTIE = 10000040


@pytest.fixture
def sample_board_state():
    """Sample board state for testing."""
    return {
        "player0": {
            "monsters": [{"code": CAESAR, "name": "Caesar"}],
            "spells": [],
            "graveyard": [{"code": ENGRAVER, "name": "Engraver"}],
            "hand": [],
            "banished": [],
            "extra": [],
        },
        "player1": {
            "monsters": [],
            "spells": [],
            "graveyard": [],
            "hand": [],
            "banished": [],
            "extra": [],
        },
    }


@pytest.fixture
def sample_idle_data():
    """Sample MSG_IDLE data for testing."""
    return {
        "activatable": [
            {"code": ENGRAVER, "loc": 2, "desc": 0},
        ],
        "spsummon": [],
        "summonable": [],
        "mset": [],
        "sset": [],
        "to_ep": True,
    }


@pytest.fixture
def empty_board_state():
    """Empty board state for testing."""
    return {
        "player0": {
            "monsters": [],
            "spells": [],
            "graveyard": [],
            "hand": [],
            "banished": [],
            "extra": [],
        },
        "player1": {
            "monsters": [],
            "spells": [],
            "graveyard": [],
            "hand": [],
            "banished": [],
            "extra": [],
        },
    }
