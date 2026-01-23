import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from combos.endboard_evaluator import evaluate_endboard  # noqa: E402


class TestEndboardEvaluator(unittest.TestCase):
    def test_caesar_has_s(self):
        snapshot = {
            "zones": {
                "hand": [],
                "field": ["D/D/D Wave High King Caesar"],
                "gy": [],
                "banished": [],
                "deck": [],
                "extra": [],
            }
        }
        result = evaluate_endboard(snapshot)
        self.assertEqual(result["rank_key"][0], True)

    def test_desirae_has_a(self):
        snapshot = {
            "zones": {
                "hand": [],
                "field": ["Fiendsmith's Desirae"],
                "gy": [],
                "banished": [],
                "deck": [],
                "extra": [],
            }
        }
        result = evaluate_endboard(snapshot)
        self.assertEqual(result["rank_key"][1], True)

    def test_kyrie_gy_counts_b(self):
        snapshot = {
            "zones": {
                "hand": [],
                "field": [],
                "gy": ["Fiendsmith Kyrie"],
                "banished": [],
                "deck": [],
                "extra": [],
            }
        }
        result = evaluate_endboard(snapshot)
        self.assertEqual(result["rank_key"][2], 1)

    def test_paradise_gy_counts_b(self):
        snapshot = {
            "zones": {
                "hand": [],
                "field": [],
                "gy": ["Fiendsmith in Paradise"],
                "banished": [],
                "deck": [],
                "extra": [],
            }
        }
        result = evaluate_endboard(snapshot)
        self.assertEqual(result["rank_key"][2], 1)


if __name__ == "__main__":
    unittest.main()
