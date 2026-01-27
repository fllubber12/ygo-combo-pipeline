"""
Shared type definitions for combo enumeration.

This module contains fundamental dataclasses used across multiple submodules
to avoid circular import issues.

Types:
    Action: A single action in a combo sequence
    TerminalState: A terminal state reached by PASS
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class Action:
    """A single action in a combo sequence.

    Attributes:
        action_type: Type of action (e.g., "activate", "summon", "select_card")
        message_type: The MSG_* constant that triggered this action
        response_value: The value before packing into bytes
        response_bytes: Raw bytes sent to engine
        description: Human-readable description of the action
        card_code: Passcode of the card involved (if applicable)
        card_name: Name of the card involved (if applicable)
        context_hash: For SELECT_CARD: hash of the prompt context
    """
    action_type: str
    message_type: int
    response_value: Any       # The value before packing
    response_bytes: bytes     # Raw bytes sent to engine
    description: str
    card_code: int = None
    card_name: str = None
    context_hash: int = None  # For SELECT_CARD: hash of the prompt context

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['response_bytes'] = self.response_bytes.hex()
        return d


@dataclass
class TerminalState:
    """A terminal state reached by PASS.

    Represents a complete combo path that ended in a terminal condition
    (PASS action, no legal actions, or max depth reached).

    Attributes:
        action_sequence: List of actions that led to this state
        board_state: Captured board state at termination
        depth: Number of actions taken to reach this state
        state_hash: Hash of the intermediate game state
        termination_reason: Why enumeration stopped ("PASS", "NO_ACTIONS", "MAX_DEPTH")
        board_hash: BoardSignature hash for grouping similar endpoints
    """
    action_sequence: List[Action]
    board_state: Dict
    depth: int
    state_hash: str
    termination_reason: str   # "PASS", "NO_ACTIONS", "MAX_DEPTH"
    board_hash: Optional[str] = None  # BoardSignature hash for grouping

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action_sequence": [a.to_dict() for a in self.action_sequence],
            "board_state": self.board_state,
            "depth": self.depth,
            "state_hash": self.state_hash,
            "termination_reason": self.termination_reason,
            "board_hash": self.board_hash,
        }


__all__ = ['Action', 'TerminalState']
