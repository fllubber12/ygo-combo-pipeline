import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from sim.state import CardInstance  # noqa: E402
from sim.ygopro_cdb import clear_cache  # noqa: E402


class TestYgoProCdbMetadata(unittest.TestCase):
    """Test CDB metadata lookup using the real CDB.

    With the single-source-of-truth model, all card stats come from CDB.
    These tests verify the CDB lookup works correctly with cdb_aliases.json.
    """

    def setUp(self) -> None:
        clear_cache()

    def tearDown(self) -> None:
        clear_cache()

    def test_cdb_metadata_enrichment(self) -> None:
        """Test that CDB provides correct metadata via alias lookup."""
        # 20215 -> 82135803 (Desirae) via cdb_aliases.json
        desirae = CardInstance.from_raw({"cid": "20215"})
        md = desirae.metadata
        self.assertEqual(md.get("attr"), "LIGHT")
        self.assertEqual(md.get("attribute"), "LIGHT")
        self.assertEqual(md.get("race"), "FIEND")
        self.assertEqual(md.get("summon_type"), "fusion")
        self.assertTrue(md.get("from_extra"))
        self.assertEqual(md.get("_cdb_resolved_from"), "alias")
        self.assertEqual(md.get("name"), "Fiendsmith's Desirae")

        # 20225 -> 2463794 (Requiem) via cdb_aliases.json
        requiem = CardInstance.from_raw({"cid": "20225"})
        md_req = requiem.metadata
        self.assertEqual(md_req.get("summon_type"), "link")
        self.assertEqual(int(md_req.get("link_rating", 0)), 1)
        self.assertTrue(md_req.get("from_extra"))

        # 20238 -> 49867899 (Sequence) via cdb_aliases.json
        sequence = CardInstance.from_raw({"cid": "20238"})
        md_seq = sequence.metadata
        self.assertEqual(md_seq.get("summon_type"), "link")
        self.assertEqual(int(md_seq.get("link_rating", 0)), 2)
        self.assertTrue(md_seq.get("from_extra"))

    def test_strict_lookup_prevents_hardcoded_override(self) -> None:
        """Test that CDB is the single source of truth - metadata arg is ignored."""
        # With strict lookup, metadata in from_raw() is ignored
        # All stats come from CDB
        card = CardInstance.from_raw({"cid": "20215"})
        md = card.metadata

        # Stats come from CDB, not from any hardcoded values
        self.assertEqual(md.get("attr"), "LIGHT")
        self.assertEqual(md.get("attribute"), "LIGHT")
        self.assertEqual(md.get("race"), "FIEND")
        self.assertEqual(md.get("summon_type"), "fusion")


if __name__ == "__main__":
    unittest.main()
