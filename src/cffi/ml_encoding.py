#!/usr/bin/env python3
"""
ML-compatible state encoding for YuGiOh game states.

Implements ygo-agent compatible feature encoding for future ML integration.
Provides standardized representations suitable for neural network input.

Usage:
    from ml_encoding import StateEncoder, ActionEncoder, EncodingConfig

    config = EncodingConfig(max_cards=160, history_length=16)
    encoder = StateEncoder(config)

    # Encode a game state
    features = encoder.encode_state(board_state)

    # Encode actions for policy network
    action_encoder = ActionEncoder(config)
    action_features = action_encoder.encode_actions(idle_data)

Architecture:
    StateEncoder produces a fixed-size tensor representation:
    - Card features: (max_cards × card_feature_dim)
    - Global features: (global_feature_dim,)
    - History features: (history_length × action_feature_dim)

    This enables batch processing and neural network compatibility.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set
from enum import IntEnum
import struct
import hashlib


# =============================================================================
# CONSTANTS
# =============================================================================

# Card locations (ygo-agent compatible)
class CardLocation(IntEnum):
    """Card location encoding."""
    DECK = 0
    HAND = 1
    MONSTER_ZONE = 2
    SPELL_ZONE = 3
    GRAVEYARD = 4
    BANISHED = 5
    EXTRA_DECK = 6
    FIELD_ZONE = 7
    PENDULUM_ZONE = 8
    UNKNOWN = 9


# Card positions
class CardPosition(IntEnum):
    """Card position encoding."""
    FACE_UP_ATTACK = 0
    FACE_DOWN_ATTACK = 1
    FACE_UP_DEFENSE = 2
    FACE_DOWN_DEFENSE = 3
    FACE_UP = 4
    FACE_DOWN = 5


# Card attributes
class CardAttribute(IntEnum):
    """Card attribute encoding."""
    NONE = 0
    EARTH = 1
    WATER = 2
    FIRE = 3
    WIND = 4
    LIGHT = 5
    DARK = 6
    DIVINE = 7


# Card types (simplified)
class CardType(IntEnum):
    """Card type encoding."""
    MONSTER = 0
    SPELL = 1
    TRAP = 2
    LINK = 3
    XYZ = 4
    SYNCHRO = 5
    FUSION = 6
    PENDULUM = 7
    RITUAL = 8


# Action types
class ActionType(IntEnum):
    """Action type encoding."""
    NONE = 0
    NORMAL_SUMMON = 1
    SPECIAL_SUMMON = 2
    ACTIVATE = 3
    SET = 4
    ATTACK = 5
    CHANGE_POSITION = 6
    TO_BATTLE_PHASE = 7
    TO_END_PHASE = 8
    CHAIN = 9


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class EncodingConfig:
    """
    Configuration for ML encoding.

    Attributes:
        max_cards: Maximum cards to encode (padding for fixed-size tensor).
        card_feature_dim: Features per card.
        global_feature_dim: Global state features.
        history_length: Number of past actions to encode.
        action_feature_dim: Features per action.
        normalize_stats: Normalize ATK/DEF/LP to [0,1] range.
        use_embeddings: Use learned embeddings for card IDs (placeholder).
        include_hidden: Include hidden information (deck order, etc.).
    """
    max_cards: int = 160
    card_feature_dim: int = 41
    global_feature_dim: int = 23
    history_length: int = 16
    action_feature_dim: int = 14
    normalize_stats: bool = True
    use_embeddings: bool = False
    include_hidden: bool = False

    # Normalization constants
    max_atk: int = 10000
    max_def: int = 10000
    max_lp: int = 8000
    max_level: int = 12
    max_counters: int = 20


# =============================================================================
# CARD FEATURES
# =============================================================================

@dataclass
class CardFeatures:
    """
    ML features for a single card (41 features, ygo-agent compatible).

    Encoding:
        - card_id: Unique identifier (for embedding lookup)
        - location: Current zone (categorical, 10 values)
        - sequence: Position within zone (0-indexed)
        - owner: Controlling player (0 or 1)
        - position: ATK/DEF/face-down (categorical, 6 values)
        - attribute: EARTH/WATER/etc (categorical, 8 values)
        - card_type: Monster/Spell/Trap/etc (categorical, 9 values)
        - level: Monster level/rank (1-12)
        - atk: Attack points (normalized)
        - defense: Defense points (normalized)
        - link_rating: Link monster rating (0-8)
        - counters: Spell counters etc
        - negated: Effect negated (binary)
        - targeted: Currently targeted (binary)
        - can_attack: Can attack this turn (binary)
        - attacked: Has attacked this turn (binary)
        - summoned_this_turn: Was summoned this turn (binary)
        - link_markers: 8-bit mask of link arrows
        - pendulum_scale: Pendulum scale value (0-13)
        - is_tuner: Tuner monster (binary)
        - extra: Additional flags packed into remaining features
    """
    card_id: int = 0
    location: int = CardLocation.UNKNOWN
    sequence: int = 0
    owner: int = 0
    position: int = CardPosition.FACE_UP
    attribute: int = CardAttribute.NONE
    card_type: int = CardType.MONSTER
    level: int = 0
    atk: float = 0.0  # Normalized
    defense: float = 0.0  # Normalized
    link_rating: int = 0
    counters: int = 0
    negated: bool = False
    targeted: bool = False
    can_attack: bool = True
    attacked: bool = False
    summoned_this_turn: bool = False
    link_markers: int = 0  # 8-bit mask
    pendulum_scale: int = 0
    is_tuner: bool = False
    # Packed extras
    is_effect: bool = True
    is_xyz_material: bool = False
    overlay_count: int = 0

    def to_vector(self, config: EncodingConfig = None) -> List[float]:
        """
        Convert to feature vector (41 floats).

        Order matches ygo-agent for compatibility.
        """
        config = config or EncodingConfig()

        # Normalize card_id to [0,1] range using hash
        card_id_norm = (self.card_id % 100000000) / 100000000.0

        return [
            card_id_norm,                    # 0: Card ID (normalized)
            self.location / 9.0,             # 1: Location (normalized)
            self.sequence / 7.0,             # 2: Sequence (normalized)
            float(self.owner),               # 3: Owner
            self.position / 5.0,             # 4: Position (normalized)
            self.attribute / 7.0,            # 5: Attribute (normalized)
            self.card_type / 8.0,            # 6: Card type (normalized)
            self.level / config.max_level,   # 7: Level (normalized)
            self.atk,                        # 8: ATK (pre-normalized)
            self.defense,                    # 9: DEF (pre-normalized)
            self.link_rating / 8.0,          # 10: Link rating (normalized)
            min(self.counters, config.max_counters) / config.max_counters,  # 11
            float(self.negated),             # 12: Negated
            float(self.targeted),            # 13: Targeted
            float(self.can_attack),          # 14: Can attack
            float(self.attacked),            # 15: Attacked
            float(self.summoned_this_turn),  # 16: Summoned this turn
            # Link markers as 8 separate bits (17-24)
            float((self.link_markers >> 0) & 1),
            float((self.link_markers >> 1) & 1),
            float((self.link_markers >> 2) & 1),
            float((self.link_markers >> 3) & 1),
            float((self.link_markers >> 4) & 1),
            float((self.link_markers >> 5) & 1),
            float((self.link_markers >> 6) & 1),
            float((self.link_markers >> 7) & 1),
            self.pendulum_scale / 13.0,      # 25: Pendulum scale
            float(self.is_tuner),            # 26: Is tuner
            float(self.is_effect),           # 27: Is effect monster
            float(self.is_xyz_material),     # 28: Is XYZ material
            self.overlay_count / 5.0,        # 29: Overlay count
            # Reserved for future use (30-40)
            0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ]

    @classmethod
    def from_card_data(
        cls,
        card_data: Dict[str, Any],
        config: EncodingConfig = None,
    ) -> "CardFeatures":
        """
        Create CardFeatures from raw card data dict.

        Expected keys: code, location, position, owner, sequence, atk, def, etc.
        """
        config = config or EncodingConfig()

        # Normalize ATK/DEF
        raw_atk = card_data.get("atk", card_data.get("attack", 0)) or 0
        raw_def = card_data.get("def", card_data.get("defense", 0)) or 0

        if config.normalize_stats:
            norm_atk = min(raw_atk, config.max_atk) / config.max_atk
            norm_def = min(raw_def, config.max_def) / config.max_def
        else:
            norm_atk = float(raw_atk)
            norm_def = float(raw_def)

        return cls(
            card_id=card_data.get("code", card_data.get("id", 0)),
            location=cls._parse_location(card_data.get("location", 0)),
            sequence=card_data.get("sequence", card_data.get("seq", 0)),
            owner=card_data.get("owner", card_data.get("controller", 0)),
            position=cls._parse_position(card_data.get("position", 0)),
            attribute=card_data.get("attribute", 0),
            card_type=cls._parse_card_type(card_data.get("type", 0)),
            level=card_data.get("level", card_data.get("rank", 0)),
            atk=norm_atk,
            defense=norm_def,
            link_rating=card_data.get("link_rating", card_data.get("link", 0)),
            counters=card_data.get("counters", 0),
            negated=card_data.get("negated", False),
            is_tuner=bool(card_data.get("type", 0) & 0x1000),  # TYPE_TUNER
        )

    @staticmethod
    def _parse_location(loc: int) -> int:
        """Parse ygopro-core location to CardLocation."""
        # ygopro-core location constants
        LOC_DECK = 0x01
        LOC_HAND = 0x02
        LOC_MZONE = 0x04
        LOC_SZONE = 0x08
        LOC_GRAVE = 0x10
        LOC_REMOVED = 0x20
        LOC_EXTRA = 0x40
        LOC_FZONE = 0x100
        LOC_PZONE = 0x200

        if loc & LOC_DECK:
            return CardLocation.DECK
        elif loc & LOC_HAND:
            return CardLocation.HAND
        elif loc & LOC_MZONE:
            return CardLocation.MONSTER_ZONE
        elif loc & LOC_SZONE:
            return CardLocation.SPELL_ZONE
        elif loc & LOC_GRAVE:
            return CardLocation.GRAVEYARD
        elif loc & LOC_REMOVED:
            return CardLocation.BANISHED
        elif loc & LOC_EXTRA:
            return CardLocation.EXTRA_DECK
        elif loc & LOC_FZONE:
            return CardLocation.FIELD_ZONE
        elif loc & LOC_PZONE:
            return CardLocation.PENDULUM_ZONE
        return CardLocation.UNKNOWN

    @staticmethod
    def _parse_position(pos: int) -> int:
        """Parse ygopro-core position to CardPosition."""
        POS_FACEUP_ATTACK = 0x1
        POS_FACEDOWN_ATTACK = 0x2
        POS_FACEUP_DEFENSE = 0x4
        POS_FACEDOWN_DEFENSE = 0x8
        POS_FACEUP = 0x5
        POS_FACEDOWN = 0xA

        if pos & POS_FACEUP_ATTACK:
            return CardPosition.FACE_UP_ATTACK
        elif pos & POS_FACEDOWN_ATTACK:
            return CardPosition.FACE_DOWN_ATTACK
        elif pos & POS_FACEUP_DEFENSE:
            return CardPosition.FACE_UP_DEFENSE
        elif pos & POS_FACEDOWN_DEFENSE:
            return CardPosition.FACE_DOWN_DEFENSE
        elif pos & POS_FACEUP:
            return CardPosition.FACE_UP
        elif pos & POS_FACEDOWN:
            return CardPosition.FACE_DOWN
        return CardPosition.FACE_UP

    @staticmethod
    def _parse_card_type(type_flags: int) -> int:
        """Parse ygopro-core type flags to CardType."""
        TYPE_MONSTER = 0x1
        TYPE_SPELL = 0x2
        TYPE_TRAP = 0x4
        TYPE_FUSION = 0x40
        TYPE_RITUAL = 0x80
        TYPE_SYNCHRO = 0x2000
        TYPE_XYZ = 0x800000
        TYPE_PENDULUM = 0x1000000
        TYPE_LINK = 0x4000000

        if type_flags & TYPE_LINK:
            return CardType.LINK
        elif type_flags & TYPE_XYZ:
            return CardType.XYZ
        elif type_flags & TYPE_SYNCHRO:
            return CardType.SYNCHRO
        elif type_flags & TYPE_FUSION:
            return CardType.FUSION
        elif type_flags & TYPE_PENDULUM:
            return CardType.PENDULUM
        elif type_flags & TYPE_RITUAL:
            return CardType.RITUAL
        elif type_flags & TYPE_SPELL:
            return CardType.SPELL
        elif type_flags & TYPE_TRAP:
            return CardType.TRAP
        return CardType.MONSTER


# =============================================================================
# GLOBAL FEATURES
# =============================================================================

@dataclass
class GlobalFeatures:
    """
    ML features for global game state (23 features).

    Includes turn count, phase, LP, card counts, etc.
    """
    turn_count: int = 1
    phase: int = 0  # 0=Draw, 1=Standby, 2=Main1, 3=Battle, 4=Main2, 5=End
    current_player: int = 0

    # Player 0 stats
    lp_p0: float = 1.0  # Normalized
    hand_count_p0: int = 5
    deck_count_p0: int = 35
    gy_count_p0: int = 0
    banished_count_p0: int = 0
    extra_count_p0: int = 15

    # Player 1 stats
    lp_p1: float = 1.0
    hand_count_p1: int = 5
    deck_count_p1: int = 35
    gy_count_p1: int = 0
    banished_count_p1: int = 0
    extra_count_p1: int = 15

    # Turn restrictions
    normal_summon_used: bool = False
    can_battle: bool = True

    # Chain state
    chain_depth: int = 0

    # Extra info
    turn_of_player: int = 0  # Whose turn is it
    first_turn: bool = True  # Is this the first turn of the duel

    def to_vector(self, config: EncodingConfig = None) -> List[float]:
        """Convert to feature vector (23 floats)."""
        config = config or EncodingConfig()

        return [
            self.turn_count / 20.0,          # 0: Turn count (normalized)
            self.phase / 5.0,                # 1: Phase (normalized)
            float(self.current_player),       # 2: Current player
            self.lp_p0,                       # 3: LP P0 (pre-normalized)
            self.hand_count_p0 / 10.0,        # 4: Hand P0
            self.deck_count_p0 / 60.0,        # 5: Deck P0
            self.gy_count_p0 / 30.0,          # 6: GY P0
            self.banished_count_p0 / 20.0,    # 7: Banished P0
            self.extra_count_p0 / 15.0,       # 8: Extra P0
            self.lp_p1,                       # 9: LP P1
            self.hand_count_p1 / 10.0,        # 10: Hand P1
            self.deck_count_p1 / 60.0,        # 11: Deck P1
            self.gy_count_p1 / 30.0,          # 12: GY P1
            self.banished_count_p1 / 20.0,    # 13: Banished P1
            self.extra_count_p1 / 15.0,       # 14: Extra P1
            float(self.normal_summon_used),   # 15: Normal summon used
            float(self.can_battle),           # 16: Can battle
            self.chain_depth / 10.0,          # 17: Chain depth
            float(self.turn_of_player),       # 18: Turn of player
            float(self.first_turn),           # 19: First turn
            0.0, 0.0, 0.0,                    # 20-22: Reserved
        ]

    @classmethod
    def from_game_state(
        cls,
        game_state: Dict[str, Any],
        config: EncodingConfig = None,
    ) -> "GlobalFeatures":
        """Create GlobalFeatures from game state dict."""
        config = config or EncodingConfig()

        # Normalize LP
        lp_p0_raw = game_state.get("lp", [8000, 8000])[0] if isinstance(game_state.get("lp"), list) else game_state.get("lp_p0", 8000)
        lp_p1_raw = game_state.get("lp", [8000, 8000])[1] if isinstance(game_state.get("lp"), list) else game_state.get("lp_p1", 8000)

        if config.normalize_stats:
            lp_p0 = min(lp_p0_raw, config.max_lp) / config.max_lp
            lp_p1 = min(lp_p1_raw, config.max_lp) / config.max_lp
        else:
            lp_p0 = float(lp_p0_raw)
            lp_p1 = float(lp_p1_raw)

        return cls(
            turn_count=game_state.get("turn_count", game_state.get("turn", 1)),
            phase=game_state.get("phase", 0),
            current_player=game_state.get("current_player", game_state.get("tp", 0)),
            lp_p0=lp_p0,
            lp_p1=lp_p1,
            hand_count_p0=game_state.get("hand_count_p0", len(game_state.get("hand", []))),
            deck_count_p0=game_state.get("deck_count_p0", game_state.get("deck_count", 35)),
            gy_count_p0=game_state.get("gy_count_p0", len(game_state.get("graveyard", []))),
            banished_count_p0=game_state.get("banished_count_p0", len(game_state.get("banished", []))),
            extra_count_p0=game_state.get("extra_count_p0", game_state.get("extra_count", 15)),
            normal_summon_used=game_state.get("normal_summon_used", False),
            can_battle=game_state.get("can_battle", True),
            chain_depth=game_state.get("chain_depth", 0),
        )


# =============================================================================
# ACTION FEATURES
# =============================================================================

@dataclass
class ActionFeatures:
    """
    ML features for a single action (14 features).

    Used for action history encoding and policy network output.
    """
    action_type: int = ActionType.NONE
    card_id: int = 0
    card_location: int = CardLocation.UNKNOWN
    target_location: int = CardLocation.UNKNOWN
    sequence: int = 0
    response_to: int = 0  # Action being responded to
    chain_link: int = 0
    effect_index: int = 0
    position: int = CardPosition.FACE_UP
    attack_target: int = 0
    # Computed features
    is_mandatory: bool = False
    is_quick: bool = False
    is_chain: bool = False
    reserved: float = 0.0

    def to_vector(self, config: EncodingConfig = None) -> List[float]:
        """Convert to feature vector (14 floats)."""
        return [
            self.action_type / 9.0,           # 0: Action type
            (self.card_id % 100000000) / 100000000.0,  # 1: Card ID
            self.card_location / 9.0,         # 2: Card location
            self.target_location / 9.0,       # 3: Target location
            self.sequence / 7.0,              # 4: Sequence
            self.response_to / 9.0,           # 5: Response to
            self.chain_link / 10.0,           # 6: Chain link
            self.effect_index / 5.0,          # 7: Effect index
            self.position / 5.0,              # 8: Position
            self.attack_target / 7.0,         # 9: Attack target
            float(self.is_mandatory),         # 10: Is mandatory
            float(self.is_quick),             # 11: Is quick
            float(self.is_chain),             # 12: Is chain
            self.reserved,                    # 13: Reserved
        ]

    @classmethod
    def from_action_dict(cls, action: Dict[str, Any]) -> "ActionFeatures":
        """Create ActionFeatures from action dictionary."""
        action_type = ActionType.NONE

        # Determine action type from dict keys/values
        if action.get("type") == "summon" or action.get("summon"):
            action_type = ActionType.NORMAL_SUMMON
        elif action.get("type") == "spsummon" or action.get("spsummon"):
            action_type = ActionType.SPECIAL_SUMMON
        elif action.get("type") == "activate" or action.get("activate"):
            action_type = ActionType.ACTIVATE
        elif action.get("type") == "set" or action.get("set"):
            action_type = ActionType.SET
        elif action.get("type") == "attack":
            action_type = ActionType.ATTACK
        elif action.get("to_bp"):
            action_type = ActionType.TO_BATTLE_PHASE
        elif action.get("to_ep"):
            action_type = ActionType.TO_END_PHASE

        return cls(
            action_type=action_type,
            card_id=action.get("code", action.get("card_id", 0)),
            card_location=CardFeatures._parse_location(action.get("location", 0)),
            sequence=action.get("sequence", action.get("seq", 0)),
            effect_index=action.get("effect_index", action.get("desc", 0)),
        )


# =============================================================================
# STATE ENCODER
# =============================================================================

class StateEncoder:
    """
    Encodes full game state to ML-compatible feature tensors.

    Output shape: (max_cards × card_feature_dim) + (global_feature_dim)
    """

    def __init__(self, config: EncodingConfig = None):
        """Initialize encoder with config."""
        self.config = config or EncodingConfig()

    def encode_state(
        self,
        game_state: Dict[str, Any],
        cards: List[Dict[str, Any]] = None,
    ) -> Dict[str, List[float]]:
        """
        Encode complete game state.

        Args:
            game_state: Global state dict with turn, phase, LP, etc.
            cards: List of card data dicts.

        Returns:
            Dict with 'card_features' (flat list), 'global_features' (list).
        """
        # Encode global features
        global_features = GlobalFeatures.from_game_state(game_state, self.config)
        global_vec = global_features.to_vector(self.config)

        # Encode card features
        cards = cards or game_state.get("cards", [])
        card_vecs = []

        for card_data in cards[:self.config.max_cards]:
            card_features = CardFeatures.from_card_data(card_data, self.config)
            card_vecs.extend(card_features.to_vector(self.config))

        # Pad to max_cards
        padding_needed = self.config.max_cards - len(cards)
        if padding_needed > 0:
            empty_card = CardFeatures()
            empty_vec = empty_card.to_vector(self.config)
            for _ in range(padding_needed):
                card_vecs.extend(empty_vec)

        return {
            "card_features": card_vecs,
            "global_features": global_vec,
        }

    def encode_board_signature(self, board_sig) -> Dict[str, List[float]]:
        """
        Encode a BoardSignature object.

        Args:
            board_sig: BoardSignature from state_representation.py

        Returns:
            Encoded features dict.
        """
        # Convert BoardSignature to game_state dict
        game_state = {
            "hand": list(board_sig.hand),
            "monsters": list(board_sig.monsters),
            "spells": list(board_sig.spells),
            "graveyard": list(board_sig.graveyard),
            "banished": list(board_sig.banished),
            "extra_deck_used": list(board_sig.extra_deck_used),
        }

        # Build cards list from all zones
        cards = []

        # Hand
        for i, code in enumerate(board_sig.hand):
            cards.append({
                "code": code,
                "location": 0x02,  # LOC_HAND
                "sequence": i,
                "owner": 0,
            })

        # Monsters
        for i, code in enumerate(board_sig.monsters):
            cards.append({
                "code": code,
                "location": 0x04,  # LOC_MZONE
                "sequence": i,
                "owner": 0,
                "position": 0x1,  # FACE_UP_ATTACK
            })

        # Spells/Traps
        for i, code in enumerate(board_sig.spells):
            cards.append({
                "code": code,
                "location": 0x08,  # LOC_SZONE
                "sequence": i,
                "owner": 0,
            })

        # Graveyard
        for i, code in enumerate(board_sig.graveyard):
            cards.append({
                "code": code,
                "location": 0x10,  # LOC_GRAVE
                "sequence": i,
                "owner": 0,
            })

        # Banished
        for i, code in enumerate(board_sig.banished):
            cards.append({
                "code": code,
                "location": 0x20,  # LOC_REMOVED
                "sequence": i,
                "owner": 0,
            })

        return self.encode_state(game_state, cards)

    def batch_encode(
        self,
        states: List[Dict[str, Any]],
    ) -> Dict[str, List[List[float]]]:
        """
        Batch encode multiple states.

        Args:
            states: List of game state dicts.

        Returns:
            Dict with batched features.
        """
        all_card_features = []
        all_global_features = []

        for state in states:
            encoded = self.encode_state(state)
            all_card_features.append(encoded["card_features"])
            all_global_features.append(encoded["global_features"])

        return {
            "card_features": all_card_features,
            "global_features": all_global_features,
        }

    def get_output_shapes(self) -> Dict[str, Tuple[int, ...]]:
        """Return output tensor shapes."""
        return {
            "card_features": (self.config.max_cards * self.config.card_feature_dim,),
            "global_features": (self.config.global_feature_dim,),
        }


# =============================================================================
# ACTION ENCODER
# =============================================================================

class ActionEncoder:
    """
    Encodes actions for policy network input/output.
    """

    def __init__(self, config: EncodingConfig = None):
        """Initialize encoder with config."""
        self.config = config or EncodingConfig()

    def encode_action(self, action: Dict[str, Any]) -> List[float]:
        """Encode single action to feature vector."""
        features = ActionFeatures.from_action_dict(action)
        return features.to_vector(self.config)

    def encode_actions(self, actions: List[Dict[str, Any]]) -> List[List[float]]:
        """Encode multiple actions."""
        return [self.encode_action(a) for a in actions]

    def encode_idle_data(self, idle_data: Dict[str, Any]) -> Dict[str, List[List[float]]]:
        """
        Encode all action options from MSG_IDLE data.

        Args:
            idle_data: Parsed idle message with activatable, summonable, etc.

        Returns:
            Dict mapping action type to encoded action lists.
        """
        result = {}

        for action_type in ["activatable", "summonable", "spsummon", "mset", "sset"]:
            actions = idle_data.get(action_type, [])
            if actions:
                result[action_type] = self.encode_actions(actions)

        # Special actions
        if idle_data.get("to_bp"):
            result["to_bp"] = [ActionFeatures(
                action_type=ActionType.TO_BATTLE_PHASE
            ).to_vector()]

        if idle_data.get("to_ep"):
            result["to_ep"] = [ActionFeatures(
                action_type=ActionType.TO_END_PHASE
            ).to_vector()]

        return result

    def encode_history(
        self,
        action_history: List[Dict[str, Any]],
    ) -> List[List[float]]:
        """
        Encode action history (circular buffer style).

        Args:
            action_history: List of recent actions.

        Returns:
            Padded/truncated list of encoded actions.
        """
        # Take last N actions
        recent = action_history[-self.config.history_length:]

        # Encode
        encoded = self.encode_actions(recent)

        # Pad if needed
        padding_needed = self.config.history_length - len(encoded)
        if padding_needed > 0:
            empty = ActionFeatures().to_vector()
            for _ in range(padding_needed):
                encoded.insert(0, empty)  # Pad at start (oldest positions)

        return encoded


# =============================================================================
# HISTORY BUFFER
# =============================================================================

class HistoryBuffer:
    """
    Circular buffer for action history (ygo-agent style).

    Maintains fixed-size history of recent actions for temporal context.
    """

    def __init__(self, config: EncodingConfig = None):
        """Initialize buffer."""
        self.config = config or EncodingConfig()
        self.buffer: List[ActionFeatures] = []
        self.encoder = ActionEncoder(config)

    def add_action(self, action: Dict[str, Any]):
        """Add action to history."""
        features = ActionFeatures.from_action_dict(action)
        self.buffer.append(features)

        # Trim to max length
        if len(self.buffer) > self.config.history_length:
            self.buffer = self.buffer[-self.config.history_length:]

    def clear(self):
        """Clear history."""
        self.buffer = []

    def to_features(self) -> List[List[float]]:
        """
        Get feature vectors for all actions in history.

        Returns:
            List of feature vectors, padded to history_length.
        """
        features = [f.to_vector(self.config) for f in self.buffer]

        # Pad if needed
        padding_needed = self.config.history_length - len(features)
        if padding_needed > 0:
            empty = ActionFeatures().to_vector()
            features = [empty] * padding_needed + features

        return features

    def __len__(self) -> int:
        """Return number of actions in buffer."""
        return len(self.buffer)


# =============================================================================
# COMPLETE OBSERVATION ENCODER
# =============================================================================

class ObservationEncoder:
    """
    Complete observation encoder combining all features.

    Produces ygo-agent compatible observation tensors:
    - Card features: (max_cards, card_feature_dim)
    - Global features: (global_feature_dim,)
    - History features: (history_length, action_feature_dim)
    """

    def __init__(self, config: EncodingConfig = None):
        """Initialize encoder components."""
        self.config = config or EncodingConfig()
        self.state_encoder = StateEncoder(config)
        self.action_encoder = ActionEncoder(config)
        self.history_buffer = HistoryBuffer(config)

    def encode(
        self,
        game_state: Dict[str, Any],
        cards: List[Dict[str, Any]] = None,
    ) -> Dict[str, List[float]]:
        """
        Encode complete observation.

        Args:
            game_state: Global state dict.
            cards: List of card data dicts.

        Returns:
            Dict with all feature arrays.
        """
        # State features
        state_features = self.state_encoder.encode_state(game_state, cards)

        # History features (flattened)
        history_features = self.history_buffer.to_features()
        history_flat = []
        for action_vec in history_features:
            history_flat.extend(action_vec)

        return {
            "card_features": state_features["card_features"],
            "global_features": state_features["global_features"],
            "history_features": history_flat,
        }

    def record_action(self, action: Dict[str, Any]):
        """Record action to history buffer."""
        self.history_buffer.add_action(action)

    def reset(self):
        """Reset encoder state (for new game)."""
        self.history_buffer.clear()

    def get_observation_space(self) -> Dict[str, Tuple[int, ...]]:
        """Return observation space dimensions."""
        return {
            "card_features": (self.config.max_cards, self.config.card_feature_dim),
            "global_features": (self.config.global_feature_dim,),
            "history_features": (self.config.history_length, self.config.action_feature_dim),
        }


# =============================================================================
# BATCH UTILITIES
# =============================================================================

def encode_combo_path(
    path: List[Dict[str, Any]],
    config: EncodingConfig = None,
) -> List[Dict[str, List[float]]]:
    """
    Encode a complete combo path for training data.

    Args:
        path: List of (state, action) pairs in combo sequence.

    Returns:
        List of encoded observations.
    """
    config = config or EncodingConfig()
    encoder = ObservationEncoder(config)

    observations = []

    for step in path:
        state = step.get("state", {})
        cards = step.get("cards", [])
        action = step.get("action", {})

        # Encode observation before action
        obs = encoder.encode(state, cards)
        obs["action"] = encoder.action_encoder.encode_action(action)
        observations.append(obs)

        # Record action for next observation's history
        encoder.record_action(action)

    return observations


def create_training_batch(
    combo_paths: List[List[Dict[str, Any]]],
    config: EncodingConfig = None,
) -> Dict[str, List]:
    """
    Create training batch from multiple combo paths.

    Args:
        combo_paths: List of combo paths.

    Returns:
        Batched training data.
    """
    config = config or EncodingConfig()

    all_observations = []
    all_actions = []
    path_indices = []

    for path_idx, path in enumerate(combo_paths):
        encoded = encode_combo_path(path, config)

        for obs in encoded:
            all_observations.append({
                "card_features": obs["card_features"],
                "global_features": obs["global_features"],
                "history_features": obs["history_features"],
            })
            all_actions.append(obs["action"])
            path_indices.append(path_idx)

    return {
        "observations": all_observations,
        "actions": all_actions,
        "path_indices": path_indices,
    }


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ML Encoding Tests")
    print("=" * 60)

    # Test 1: EncodingConfig
    print("\n1. EncodingConfig:")
    config = EncodingConfig()
    print(f"   max_cards: {config.max_cards}")
    print(f"   card_feature_dim: {config.card_feature_dim}")
    print(f"   global_feature_dim: {config.global_feature_dim}")
    assert config.max_cards == 160
    assert config.card_feature_dim == 41
    print("   OK")

    # Test 2: CardFeatures
    print("\n2. CardFeatures:")
    card = CardFeatures(
        card_id=60764609,
        location=CardLocation.HAND,
        owner=0,
        atk=0.5,
        defense=0.3,
    )
    vec = card.to_vector()
    assert len(vec) == 41
    print(f"   Vector length: {len(vec)}")
    print(f"   First few values: {vec[:5]}")
    print("   OK")

    # Test 3: GlobalFeatures
    print("\n3. GlobalFeatures:")
    global_f = GlobalFeatures(
        turn_count=3,
        phase=2,
        lp_p0=0.75,
    )
    vec = global_f.to_vector()
    assert len(vec) == 23
    print(f"   Vector length: {len(vec)}")
    print("   OK")

    # Test 4: ActionFeatures
    print("\n4. ActionFeatures:")
    action = ActionFeatures(
        action_type=ActionType.ACTIVATE,
        card_id=60764609,
    )
    vec = action.to_vector()
    assert len(vec) == 14
    print(f"   Vector length: {len(vec)}")
    print("   OK")

    # Test 5: StateEncoder
    print("\n5. StateEncoder:")
    encoder = StateEncoder()
    state = {
        "turn": 1,
        "phase": 2,
        "lp_p0": 8000,
        "lp_p1": 8000,
        "cards": [
            {"code": 60764609, "location": 0x02, "sequence": 0},
            {"code": 49867899, "location": 0x02, "sequence": 1},
        ],
    }
    encoded = encoder.encode_state(state)

    expected_card_len = config.max_cards * config.card_feature_dim
    assert len(encoded["card_features"]) == expected_card_len
    assert len(encoded["global_features"]) == config.global_feature_dim
    print(f"   Card features length: {len(encoded['card_features'])}")
    print(f"   Global features length: {len(encoded['global_features'])}")
    print("   OK")

    # Test 6: ActionEncoder
    print("\n6. ActionEncoder:")
    action_enc = ActionEncoder()
    actions = [
        {"type": "activate", "code": 60764609},
        {"type": "spsummon", "code": 2463794},
    ]
    encoded = action_enc.encode_actions(actions)
    assert len(encoded) == 2
    assert len(encoded[0]) == 14
    print(f"   Encoded {len(encoded)} actions")
    print("   OK")

    # Test 7: HistoryBuffer
    print("\n7. HistoryBuffer:")
    buffer = HistoryBuffer()
    buffer.add_action({"type": "activate", "code": 60764609})
    buffer.add_action({"type": "spsummon", "code": 2463794})

    features = buffer.to_features()
    assert len(features) == config.history_length
    print(f"   Buffer length: {len(buffer)}")
    print(f"   Features length: {len(features)}")
    print("   OK")

    # Test 8: ObservationEncoder
    print("\n8. ObservationEncoder:")
    obs_enc = ObservationEncoder()
    obs = obs_enc.encode(state, state["cards"])

    assert "card_features" in obs
    assert "global_features" in obs
    assert "history_features" in obs
    print(f"   Observation keys: {list(obs.keys())}")
    print("   OK")

    # Test 9: CardFeatures.from_card_data
    print("\n9. CardFeatures.from_card_data:")
    card_data = {
        "code": 60764609,
        "location": 0x02,  # HAND
        "sequence": 0,
        "owner": 0,
        "atk": 2000,
        "def": 1500,
        "level": 4,
    }
    card = CardFeatures.from_card_data(card_data)
    assert card.card_id == 60764609
    assert card.location == CardLocation.HAND
    assert card.atk == 2000 / 10000  # Normalized
    print(f"   Card ID: {card.card_id}")
    print(f"   Location: {card.location}")
    print(f"   ATK (normalized): {card.atk}")
    print("   OK")

    # Test 10: Output shapes
    print("\n10. Output shapes:")
    shapes = encoder.get_output_shapes()
    print(f"   Card features: {shapes['card_features']}")
    print(f"   Global features: {shapes['global_features']}")
    assert shapes["card_features"] == (160 * 41,)
    assert shapes["global_features"] == (23,)
    print("   OK")

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
