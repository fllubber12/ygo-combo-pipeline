#!/usr/bin/env python3
"""Unit tests for card role classification module."""

import unittest
import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "ygo_combo"))

from cards.roles import (
    CardRole, CardClassification, CardRoleClassifier,
    create_fiendsmith_classifier, get_fiendsmith_classifications,
)


class TestCardRole(unittest.TestCase):
    """Test CardRole enum."""

    def test_role_ordering(self):
        """Roles have correct priority ordering."""
        self.assertLess(CardRole.STARTER.value, CardRole.EXTENDER.value)
        self.assertLess(CardRole.EXTENDER.value, CardRole.PAYOFF.value)
        self.assertLess(CardRole.PAYOFF.value, CardRole.UTILITY.value)
        self.assertLess(CardRole.UTILITY.value, CardRole.GARNET.value)

    def test_role_names(self):
        """Role names are accessible."""
        self.assertEqual(CardRole.STARTER.name, "STARTER")
        self.assertEqual(CardRole.UNKNOWN.name, "UNKNOWN")


class TestCardClassification(unittest.TestCase):
    """Test CardClassification dataclass."""

    def test_effective_priority_no_boost(self):
        """Effective priority equals role value without boost."""
        classification = CardClassification(
            passcode=12345,
            role=CardRole.STARTER,
        )
        self.assertEqual(classification.effective_priority(), CardRole.STARTER.value)

    def test_effective_priority_with_boost(self):
        """Effective priority includes boost."""
        classification = CardClassification(
            passcode=12345,
            role=CardRole.PAYOFF,
            priority_boost=-2,
        )
        self.assertEqual(
            classification.effective_priority(),
            CardRole.PAYOFF.value - 2
        )

    def test_tags_immutable(self):
        """Tags are immutable frozenset."""
        classification = CardClassification(
            passcode=12345,
            role=CardRole.STARTER,
            tags=frozenset(["tag1", "tag2"]),
        )
        self.assertIsInstance(classification.tags, frozenset)


class TestCardRoleClassifier(unittest.TestCase):
    """Test CardRoleClassifier."""

    def setUp(self):
        self.classifier = create_fiendsmith_classifier()

    def test_get_role_known(self):
        """Get role for classified card."""
        role = self.classifier.get_role(60764609)  # Engraver
        self.assertEqual(role, CardRole.STARTER)

    def test_get_role_unknown(self):
        """Get role for unclassified card."""
        role = self.classifier.get_role(99999999)
        self.assertEqual(role, CardRole.UNKNOWN)

    def test_get_classification(self):
        """Get full classification."""
        classification = self.classifier.get_classification(60764609)
        self.assertIsNotNone(classification)
        self.assertEqual(classification.role, CardRole.STARTER)
        self.assertIn("fiendsmith", classification.tags)

    def test_get_priority(self):
        """Get effective priority."""
        priority = self.classifier.get_priority(60764609)
        self.assertEqual(priority, CardRole.STARTER.value)

    def test_get_cards_by_role(self):
        """Get all cards with a role."""
        starters = self.classifier.get_cards_by_role(CardRole.STARTER)
        self.assertIn(60764609, starters)  # Engraver
        self.assertIn(49867899, starters)  # Sequence

    def test_prioritize_actions(self):
        """Actions sorted by role priority."""
        actions = [
            {"code": 79559912},  # PAYOFF (Caesar)
            {"code": 60764609},  # STARTER (Engraver)
            {"code": 2463794},   # EXTENDER (Requiem)
        ]

        sorted_actions = self.classifier.prioritize_actions(actions)

        # STARTER should come first
        self.assertEqual(sorted_actions[0]["code"], 60764609)

    def test_prioritize_idle_actions(self):
        """Idle data action lists are sorted."""
        idle_data = {
            "activatable": [
                {"code": 79559912},
                {"code": 60764609},
            ],
            "spsummon": [
                {"code": 2463794},
            ],
            "to_ep": True,
        }

        result = self.classifier.prioritize_idle_actions(idle_data)

        # First activatable should be starter
        self.assertEqual(result["activatable"][0]["code"], 60764609)
        # to_ep unchanged
        self.assertTrue(result["to_ep"])

    def test_should_prune_extenders_no_starter(self):
        """Prune extenders when no starter activated."""
        actions = [{"code": 2463794}]  # Only extender
        self.assertTrue(self.classifier.should_prune_extenders(actions))

    def test_should_prune_extenders_with_starter(self):
        """Don't prune extenders when starter activated."""
        actions = [{"code": 60764609}]  # Starter
        self.assertFalse(self.classifier.should_prune_extenders(actions))

    def test_filter_by_role(self):
        """Filter actions by role."""
        actions = [
            {"code": 60764609},  # STARTER
            {"code": 79559912},  # PAYOFF
            {"code": 10000040},  # GARNET
        ]

        starters = self.classifier.filter_by_role(
            actions,
            allowed_roles={CardRole.STARTER}
        )

        self.assertEqual(len(starters), 1)
        self.assertEqual(starters[0]["code"], 60764609)

    def test_stats(self):
        """Stats returned correctly."""
        stats = self.classifier.stats()
        self.assertIn("total_classified", stats)
        self.assertIn("by_role", stats)
        self.assertGreater(stats["total_classified"], 0)


class TestClassifierConfig(unittest.TestCase):
    """Test config loading/saving."""

    def test_to_config(self):
        """Export to config format."""
        classifier = create_fiendsmith_classifier()
        config = classifier.to_config()

        self.assertIn("cards", config)
        self.assertIn("60764609", config["cards"])
        self.assertEqual(config["cards"]["60764609"]["role"], "STARTER")

    def test_from_config(self):
        """Load from config file."""
        config = {
            "cards": {
                "12345": {
                    "role": "STARTER",
                    "tags": ["test"],
                    "notes": "Test card",
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            temp_path = f.name

        try:
            classifier = CardRoleClassifier.from_config(Path(temp_path))
            role = classifier.get_role(12345)
            self.assertEqual(role, CardRole.STARTER)
        finally:
            Path(temp_path).unlink()

    def test_from_config_missing_file(self):
        """Missing config file returns empty classifier."""
        classifier = CardRoleClassifier.from_config(Path("/nonexistent/path.json"))
        self.assertEqual(classifier.stats()["total_classified"], 0)

    def test_save_config(self):
        """Save config to file."""
        classifier = create_fiendsmith_classifier()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            classifier.save_config(Path(temp_path))

            with open(temp_path) as f:
                loaded = json.load(f)

            self.assertIn("cards", loaded)
            self.assertIn("60764609", loaded["cards"])
        finally:
            Path(temp_path).unlink()


class TestFiendsmithClassifications(unittest.TestCase):
    """Test pre-defined Fiendsmith classifications."""

    def test_classifications_exist(self):
        """Pre-defined classifications are populated."""
        classifications = get_fiendsmith_classifications()
        self.assertGreater(len(classifications), 0)

    def test_engraver_is_starter(self):
        """Engraver correctly classified as starter."""
        classifications = get_fiendsmith_classifications()
        self.assertEqual(classifications[60764609].role, CardRole.STARTER)

    def test_caesar_is_payoff(self):
        """Caesar correctly classified as payoff."""
        classifications = get_fiendsmith_classifications()
        self.assertEqual(classifications[79559912].role, CardRole.PAYOFF)

    def test_holactie_is_garnet(self):
        """Holactie correctly classified as garnet."""
        classifications = get_fiendsmith_classifications()
        self.assertEqual(classifications[10000040].role, CardRole.GARNET)


if __name__ == "__main__":
    unittest.main(verbosity=2)
