#!/usr/bin/env python3
"""Unit tests for ML encoding module."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "cffi"))

from ml_encoding import (
    EncodingConfig, CardFeatures, GlobalFeatures, ActionFeatures,
    CardLocation, CardPosition, CardAttribute, CardType, ActionType,
    StateEncoder, ActionEncoder, HistoryBuffer, ObservationEncoder,
    encode_combo_path, create_training_batch,
)


class TestEncodingConfig(unittest.TestCase):
    """Test EncodingConfig dataclass."""

    def test_default_values(self):
        """Default values are set correctly."""
        config = EncodingConfig()
        self.assertEqual(config.max_cards, 160)
        self.assertEqual(config.card_feature_dim, 41)
        self.assertEqual(config.global_feature_dim, 23)
        self.assertEqual(config.history_length, 16)
        self.assertEqual(config.action_feature_dim, 14)

    def test_custom_values(self):
        """Custom values are accepted."""
        config = EncodingConfig(
            max_cards=100,
            history_length=8,
            normalize_stats=False,
        )
        self.assertEqual(config.max_cards, 100)
        self.assertEqual(config.history_length, 8)
        self.assertFalse(config.normalize_stats)

    def test_normalization_constants(self):
        """Normalization constants have sensible defaults."""
        config = EncodingConfig()
        self.assertEqual(config.max_atk, 10000)
        self.assertEqual(config.max_def, 10000)
        self.assertEqual(config.max_lp, 8000)
        self.assertEqual(config.max_level, 12)


class TestCardLocation(unittest.TestCase):
    """Test CardLocation enum."""

    def test_location_values(self):
        """Location values are distinct integers."""
        locations = [
            CardLocation.DECK, CardLocation.HAND, CardLocation.MONSTER_ZONE,
            CardLocation.SPELL_ZONE, CardLocation.GRAVEYARD, CardLocation.BANISHED,
        ]
        values = [loc.value for loc in locations]
        self.assertEqual(len(values), len(set(values)))  # All unique

    def test_unknown_highest(self):
        """UNKNOWN has highest value (for padding)."""
        self.assertGreater(CardLocation.UNKNOWN, CardLocation.DECK)
        self.assertGreater(CardLocation.UNKNOWN, CardLocation.HAND)


class TestCardFeatures(unittest.TestCase):
    """Test CardFeatures dataclass."""

    def test_default_values(self):
        """Default values create valid features."""
        card = CardFeatures()
        self.assertEqual(card.card_id, 0)
        self.assertEqual(card.location, CardLocation.UNKNOWN)
        self.assertEqual(card.atk, 0.0)

    def test_to_vector_length(self):
        """to_vector returns correct length."""
        card = CardFeatures(card_id=12345)
        vec = card.to_vector()
        self.assertEqual(len(vec), 41)

    def test_to_vector_normalized(self):
        """to_vector normalizes values to [0,1] range."""
        card = CardFeatures(
            card_id=60764609,
            location=CardLocation.HAND,
            level=4,
            atk=0.5,  # Pre-normalized
        )
        vec = card.to_vector()

        # All values should be in [0,1] range
        for v in vec:
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_from_card_data(self):
        """from_card_data parses correctly."""
        data = {
            "code": 60764609,
            "location": 0x02,  # LOC_HAND
            "sequence": 2,
            "owner": 0,
            "atk": 2000,
            "def": 1500,
            "level": 4,
        }
        card = CardFeatures.from_card_data(data)

        self.assertEqual(card.card_id, 60764609)
        self.assertEqual(card.location, CardLocation.HAND)
        self.assertEqual(card.sequence, 2)
        self.assertEqual(card.atk, 2000 / 10000)  # Normalized

    def test_from_card_data_normalization(self):
        """from_card_data normalizes ATK/DEF correctly."""
        config = EncodingConfig(max_atk=5000, max_def=5000)
        data = {"code": 1, "atk": 5000, "def": 2500}

        card = CardFeatures.from_card_data(data, config)

        self.assertEqual(card.atk, 1.0)  # 5000/5000
        self.assertEqual(card.defense, 0.5)  # 2500/5000

    def test_parse_location(self):
        """_parse_location handles all location codes."""
        self.assertEqual(CardFeatures._parse_location(0x01), CardLocation.DECK)
        self.assertEqual(CardFeatures._parse_location(0x02), CardLocation.HAND)
        self.assertEqual(CardFeatures._parse_location(0x04), CardLocation.MONSTER_ZONE)
        self.assertEqual(CardFeatures._parse_location(0x08), CardLocation.SPELL_ZONE)
        self.assertEqual(CardFeatures._parse_location(0x10), CardLocation.GRAVEYARD)
        self.assertEqual(CardFeatures._parse_location(0x20), CardLocation.BANISHED)
        self.assertEqual(CardFeatures._parse_location(0x40), CardLocation.EXTRA_DECK)

    def test_parse_position(self):
        """_parse_position handles position codes."""
        self.assertEqual(CardFeatures._parse_position(0x1), CardPosition.FACE_UP_ATTACK)
        self.assertEqual(CardFeatures._parse_position(0x4), CardPosition.FACE_UP_DEFENSE)
        self.assertEqual(CardFeatures._parse_position(0x8), CardPosition.FACE_DOWN_DEFENSE)

    def test_link_markers_encoding(self):
        """Link markers are encoded as 8 bits."""
        card = CardFeatures(link_markers=0b10101010)
        vec = card.to_vector()

        # Link markers are at indices 17-24
        markers = vec[17:25]
        self.assertEqual(markers[0], 0.0)  # bit 0
        self.assertEqual(markers[1], 1.0)  # bit 1
        self.assertEqual(markers[2], 0.0)  # bit 2
        self.assertEqual(markers[3], 1.0)  # bit 3


class TestGlobalFeatures(unittest.TestCase):
    """Test GlobalFeatures dataclass."""

    def test_default_values(self):
        """Default values create valid features."""
        glob = GlobalFeatures()
        self.assertEqual(glob.turn_count, 1)
        self.assertEqual(glob.lp_p0, 1.0)
        self.assertEqual(glob.hand_count_p0, 5)

    def test_to_vector_length(self):
        """to_vector returns correct length."""
        glob = GlobalFeatures()
        vec = glob.to_vector()
        self.assertEqual(len(vec), 23)

    def test_to_vector_normalized(self):
        """to_vector normalizes values appropriately."""
        glob = GlobalFeatures(
            turn_count=10,
            lp_p0=0.5,
            lp_p1=0.75,
        )
        vec = glob.to_vector()

        # Turn count normalized to 10/20 = 0.5
        self.assertEqual(vec[0], 0.5)

    def test_from_game_state(self):
        """from_game_state parses correctly."""
        state = {
            "turn": 5,
            "phase": 2,
            "lp_p0": 6000,
            "lp_p1": 8000,
            "normal_summon_used": True,
        }
        glob = GlobalFeatures.from_game_state(state)

        self.assertEqual(glob.turn_count, 5)
        self.assertEqual(glob.phase, 2)
        self.assertEqual(glob.lp_p0, 6000 / 8000)  # Normalized
        self.assertTrue(glob.normal_summon_used)

    def test_from_game_state_list_lp(self):
        """from_game_state handles LP as list."""
        state = {
            "lp": [6000, 7000],
            "turn": 1,
        }
        glob = GlobalFeatures.from_game_state(state)

        self.assertEqual(glob.lp_p0, 6000 / 8000)
        self.assertEqual(glob.lp_p1, 7000 / 8000)


class TestActionFeatures(unittest.TestCase):
    """Test ActionFeatures dataclass."""

    def test_default_values(self):
        """Default values create valid features."""
        action = ActionFeatures()
        self.assertEqual(action.action_type, ActionType.NONE)
        self.assertEqual(action.card_id, 0)

    def test_to_vector_length(self):
        """to_vector returns correct length."""
        action = ActionFeatures()
        vec = action.to_vector()
        self.assertEqual(len(vec), 14)

    def test_from_action_dict_activate(self):
        """from_action_dict parses activate action."""
        data = {"type": "activate", "code": 60764609, "location": 0x02}
        action = ActionFeatures.from_action_dict(data)

        self.assertEqual(action.action_type, ActionType.ACTIVATE)
        self.assertEqual(action.card_id, 60764609)

    def test_from_action_dict_spsummon(self):
        """from_action_dict parses special summon action."""
        data = {"type": "spsummon", "code": 2463794}
        action = ActionFeatures.from_action_dict(data)

        self.assertEqual(action.action_type, ActionType.SPECIAL_SUMMON)

    def test_from_action_dict_to_ep(self):
        """from_action_dict parses to_ep action."""
        data = {"to_ep": True}
        action = ActionFeatures.from_action_dict(data)

        self.assertEqual(action.action_type, ActionType.TO_END_PHASE)


class TestStateEncoder(unittest.TestCase):
    """Test StateEncoder class."""

    def setUp(self):
        self.encoder = StateEncoder()
        self.config = EncodingConfig()

    def test_encode_state_shapes(self):
        """encode_state returns correct shapes."""
        state = {"turn": 1, "phase": 2}
        cards = [{"code": 12345, "location": 0x02}]

        encoded = self.encoder.encode_state(state, cards)

        expected_card_len = self.config.max_cards * self.config.card_feature_dim
        self.assertEqual(len(encoded["card_features"]), expected_card_len)
        self.assertEqual(len(encoded["global_features"]), self.config.global_feature_dim)

    def test_encode_state_padding(self):
        """encode_state pads to max_cards."""
        state = {"turn": 1}
        cards = [{"code": 1}]  # Only 1 card

        encoded = self.encoder.encode_state(state, cards)

        # Should be padded to max_cards * features
        expected_len = self.config.max_cards * self.config.card_feature_dim
        self.assertEqual(len(encoded["card_features"]), expected_len)

    def test_encode_state_truncation(self):
        """encode_state truncates to max_cards."""
        config = EncodingConfig(max_cards=2)
        encoder = StateEncoder(config)

        state = {"turn": 1}
        cards = [{"code": i} for i in range(10)]  # 10 cards

        encoded = encoder.encode_state(state, cards)

        # Should be truncated to 2 * features
        expected_len = 2 * config.card_feature_dim
        self.assertEqual(len(encoded["card_features"]), expected_len)

    def test_batch_encode(self):
        """batch_encode handles multiple states."""
        states = [
            {"turn": 1, "cards": [{"code": 1}]},
            {"turn": 2, "cards": [{"code": 2}]},
            {"turn": 3, "cards": [{"code": 3}]},
        ]

        batched = self.encoder.batch_encode(states)

        self.assertEqual(len(batched["card_features"]), 3)
        self.assertEqual(len(batched["global_features"]), 3)

    def test_get_output_shapes(self):
        """get_output_shapes returns correct shapes."""
        shapes = self.encoder.get_output_shapes()

        self.assertEqual(shapes["card_features"], (160 * 41,))
        self.assertEqual(shapes["global_features"], (23,))


class TestActionEncoder(unittest.TestCase):
    """Test ActionEncoder class."""

    def setUp(self):
        self.encoder = ActionEncoder()

    def test_encode_action(self):
        """encode_action returns feature vector."""
        action = {"type": "activate", "code": 12345}
        vec = self.encoder.encode_action(action)

        self.assertEqual(len(vec), 14)

    def test_encode_actions(self):
        """encode_actions handles multiple actions."""
        actions = [
            {"type": "activate", "code": 1},
            {"type": "spsummon", "code": 2},
        ]
        vecs = self.encoder.encode_actions(actions)

        self.assertEqual(len(vecs), 2)
        self.assertEqual(len(vecs[0]), 14)

    def test_encode_idle_data(self):
        """encode_idle_data handles all action types."""
        idle_data = {
            "activatable": [{"code": 1}, {"code": 2}],
            "spsummon": [{"code": 3}],
            "to_ep": True,
        }

        encoded = self.encoder.encode_idle_data(idle_data)

        self.assertIn("activatable", encoded)
        self.assertIn("spsummon", encoded)
        self.assertIn("to_ep", encoded)
        self.assertEqual(len(encoded["activatable"]), 2)

    def test_encode_history(self):
        """encode_history pads/truncates correctly."""
        config = EncodingConfig(history_length=4)
        encoder = ActionEncoder(config)

        # Fewer actions than history length
        history = [{"type": "activate", "code": 1}]
        encoded = encoder.encode_history(history)

        self.assertEqual(len(encoded), 4)  # Padded

    def test_encode_history_truncation(self):
        """encode_history truncates long history."""
        config = EncodingConfig(history_length=2)
        encoder = ActionEncoder(config)

        # More actions than history length
        history = [{"code": i} for i in range(5)]
        encoded = encoder.encode_history(history)

        self.assertEqual(len(encoded), 2)  # Truncated


class TestHistoryBuffer(unittest.TestCase):
    """Test HistoryBuffer class."""

    def setUp(self):
        self.config = EncodingConfig(history_length=4)
        self.buffer = HistoryBuffer(self.config)

    def test_add_action(self):
        """add_action increases buffer size."""
        self.assertEqual(len(self.buffer), 0)

        self.buffer.add_action({"type": "activate", "code": 1})

        self.assertEqual(len(self.buffer), 1)

    def test_add_action_circular(self):
        """add_action maintains max length."""
        for i in range(10):
            self.buffer.add_action({"code": i})

        self.assertEqual(len(self.buffer), 4)  # Max history_length

    def test_clear(self):
        """clear empties buffer."""
        self.buffer.add_action({"code": 1})
        self.buffer.clear()

        self.assertEqual(len(self.buffer), 0)

    def test_to_features(self):
        """to_features returns padded features."""
        self.buffer.add_action({"code": 1})

        features = self.buffer.to_features()

        self.assertEqual(len(features), 4)  # Padded to history_length
        self.assertEqual(len(features[0]), 14)  # Action feature dim

    def test_to_features_empty(self):
        """to_features handles empty buffer."""
        features = self.buffer.to_features()

        self.assertEqual(len(features), 4)  # All padding


class TestObservationEncoder(unittest.TestCase):
    """Test ObservationEncoder class."""

    def setUp(self):
        self.encoder = ObservationEncoder()

    def test_encode(self):
        """encode returns all feature types."""
        state = {"turn": 1}
        cards = [{"code": 12345}]

        obs = self.encoder.encode(state, cards)

        self.assertIn("card_features", obs)
        self.assertIn("global_features", obs)
        self.assertIn("history_features", obs)

    def test_record_action(self):
        """record_action adds to history."""
        self.encoder.record_action({"code": 1})

        self.assertEqual(len(self.encoder.history_buffer), 1)

    def test_reset(self):
        """reset clears history."""
        self.encoder.record_action({"code": 1})
        self.encoder.reset()

        self.assertEqual(len(self.encoder.history_buffer), 0)

    def test_get_observation_space(self):
        """get_observation_space returns shapes."""
        space = self.encoder.get_observation_space()

        self.assertEqual(space["card_features"], (160, 41))
        self.assertEqual(space["global_features"], (23,))
        self.assertEqual(space["history_features"], (16, 14))


class TestEncodeComboPath(unittest.TestCase):
    """Test encode_combo_path function."""

    def test_encode_path(self):
        """encode_combo_path encodes full path."""
        path = [
            {
                "state": {"turn": 1},
                "cards": [{"code": 1}],
                "action": {"type": "activate", "code": 1},
            },
            {
                "state": {"turn": 1},
                "cards": [{"code": 2}],
                "action": {"type": "spsummon", "code": 2},
            },
        ]

        encoded = encode_combo_path(path)

        self.assertEqual(len(encoded), 2)
        self.assertIn("card_features", encoded[0])
        self.assertIn("action", encoded[0])


class TestCreateTrainingBatch(unittest.TestCase):
    """Test create_training_batch function."""

    def test_create_batch(self):
        """create_training_batch combines multiple paths."""
        paths = [
            [{"state": {}, "cards": [], "action": {"code": 1}}],
            [{"state": {}, "cards": [], "action": {"code": 2}}],
        ]

        batch = create_training_batch(paths)

        self.assertIn("observations", batch)
        self.assertIn("actions", batch)
        self.assertIn("path_indices", batch)
        self.assertEqual(len(batch["observations"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
