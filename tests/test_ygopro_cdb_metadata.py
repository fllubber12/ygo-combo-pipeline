import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from sim.state import CardInstance  # noqa: E402
from sim.ygopro_cdb import (  # noqa: E402
    ATTR_DARK,
    ATTR_LIGHT,
    RACE_FIEND,
    TYPE_EFFECT,
    TYPE_FUSION,
    TYPE_LINK,
    TYPE_MONSTER,
    clear_cache,
)


class TestYgoProCdbMetadata(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.NamedTemporaryFile(delete=False, suffix=".cdb")
        self.temp.close()
        conn = sqlite3.connect(self.temp.name)
        try:
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE datas (id INTEGER PRIMARY KEY, type INTEGER, level INTEGER, race INTEGER, attribute INTEGER)"
            )
            cur.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT, desc TEXT)")
            cur.executemany(
                "INSERT INTO datas (id, type, level, race, attribute) VALUES (?, ?, ?, ?, ?)",
                [
                    (999001, TYPE_MONSTER | TYPE_EFFECT | TYPE_FUSION, 8, RACE_FIEND, ATTR_LIGHT),
                    (20225, TYPE_MONSTER | TYPE_EFFECT | TYPE_LINK, 1, RACE_FIEND, ATTR_DARK),
                    (20238, TYPE_MONSTER | TYPE_EFFECT | TYPE_LINK, 2, RACE_FIEND, ATTR_DARK),
                    (20389, TYPE_MONSTER | TYPE_EFFECT, 4, RACE_FIEND, ATTR_DARK),
                ],
            )
            cur.executemany(
                "INSERT INTO texts (id, name, desc) VALUES (?, ?, ?)",
                [
                    (999001, "Fiendsmith's Desirae", ""),
                    (20225, "Fiendsmith's Requiem", ""),
                    (20238, "Fiendsmith's Sequence", ""),
                    (20389, "The Duke of Demise", ""),
                ],
            )
            conn.commit()
        finally:
            conn.close()
        os.environ["YGOPRO_CDB_PATH"] = self.temp.name
        clear_cache()

    def tearDown(self) -> None:
        if os.path.exists(self.temp.name):
            os.remove(self.temp.name)
        os.environ.pop("YGOPRO_CDB_PATH", None)
        clear_cache()

    def test_cdb_metadata_enrichment(self) -> None:
        desirae = CardInstance.from_raw({"cid": "20215", "name": "Fiendsmith's Desirae", "metadata": {}})
        md = desirae.metadata
        self.assertEqual(md.get("attr"), "LIGHT")
        self.assertEqual(md.get("attribute"), "LIGHT")
        self.assertEqual(md.get("race"), "FIEND")
        self.assertEqual(md.get("summon_type"), "fusion")
        self.assertTrue(md.get("from_extra"))
        self.assertEqual(md.get("_cdb_resolved_from"), "name")
        self.assertEqual(md.get("_cdb_resolved_id"), 999001)

        requiem = CardInstance.from_raw({"cid": "20225", "name": "Fiendsmith's Requiem", "metadata": {}})
        md_req = requiem.metadata
        self.assertEqual(md_req.get("summon_type"), "link")
        self.assertEqual(int(md_req.get("link_rating", 0)), 1)
        self.assertTrue(md_req.get("from_extra"))

        sequence = CardInstance.from_raw({"cid": "20238", "name": "Fiendsmith's Sequence", "metadata": {}})
        md_seq = sequence.metadata
        self.assertEqual(md_seq.get("summon_type"), "link")
        self.assertEqual(int(md_seq.get("link_rating", 0)), 2)
        self.assertTrue(md_seq.get("from_extra"))

    def test_merge_only_behavior(self) -> None:
        overridden = CardInstance.from_raw(
            {"cid": "20215", "name": "Fiendsmith's Desirae", "metadata": {"attr": "DARK"}}
        )
        md_over = overridden.metadata
        self.assertEqual(md_over.get("attr"), "DARK")
        self.assertEqual(md_over.get("attribute"), "DARK")

        empty_override = CardInstance.from_raw(
            {"cid": "20215", "name": "Fiendsmith's Desirae", "metadata": {"attr": ""}}
        )
        md_empty = empty_override.metadata
        self.assertEqual(md_empty.get("attr"), "LIGHT")
        self.assertEqual(md_empty.get("attribute"), "LIGHT")


if __name__ == "__main__":
    unittest.main()
