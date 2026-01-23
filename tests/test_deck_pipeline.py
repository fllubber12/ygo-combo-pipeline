import unittest
try:
    import pandas as pd  # noqa: F401
except Exception as e:
    raise unittest.SkipTest(f"Skipping deck pipeline tests (missing pandas): {e}")

try:
    import openpyxl  # noqa: F401
except Exception as e:
    raise unittest.SkipTest(f"Skipping deck pipeline tests (missing openpyxl): {e}")

import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

import decklist_pipeline as dp  # noqa: E402


class TestDeckParsing(unittest.TestCase):
    def test_parse_ydk(self):
        text = """#main\n20196\n20196\n#extra\n20225\n!side\n20241\n"""
        parsed = dp.parse_ydk(text)
        self.assertEqual(parsed["main"]["20196"], 2)
        self.assertEqual(parsed["extra"]["20225"], 1)
        self.assertEqual(parsed["side"]["20241"], 1)

    def test_parse_plain_text_variants(self):
        text = """3x Fiendsmith Engraver\nFiendsmith's Tract x2\nFiendsmith's Sanct 1\nx1 Fiendsmith Kyrie\n"""
        parsed = dp.parse_plain_text(text)
        self.assertEqual(parsed["main"]["Fiendsmith Engraver"], 3)
        self.assertEqual(parsed["main"]["Fiendsmith's Tract"], 2)
        self.assertEqual(parsed["main"]["Fiendsmith's Sanct"], 1)
        self.assertEqual(parsed["main"]["Fiendsmith Kyrie"], 1)

    def test_normalize_name(self):
        value = "Fiendsmith\u2019s Tract"
        self.assertEqual(dp.normalize_name(value), "Fiendsmith's Tract")

    def test_unresolved_fails(self):
        clean_path = repo_root / "data_processed" / "Fiendsmith_Master_Card_Library_CLEAN.xlsx"
        library = dp.load_card_library(clean_path)
        parsed = {"main": {"Unknown Card": 1}, "extra": {}, "side": {}}
        with self.assertRaises(dp.DeckResolutionError):
            dp.normalize_deck("bad_deck", {"game": "TCG"}, parsed, library)

    def test_normalization_match(self):
        clean_path = repo_root / "data_processed" / "Fiendsmith_Master_Card_Library_CLEAN.xlsx"
        library = dp.load_card_library(clean_path)
        parsed = {"main": {"Fiendsmith\u2019s Tract": 1}, "extra": {}, "side": {}}
        deck = dp.normalize_deck("good_deck", {"game": "TCG"}, parsed, library)
        self.assertEqual(deck["main"][0]["name"], "Fiendsmith's Tract")


if __name__ == "__main__":
    unittest.main()
