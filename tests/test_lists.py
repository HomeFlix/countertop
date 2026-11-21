"""Lists kept on this dashboard: each list has its own items, existing items carry over, and the daily reset.

Run with: python3 tests/test_lists.py
"""

import importlib.util
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
TMP = TemporaryDirectory()
os.environ["COUNTERTOP_DATA"] = TMP.name
spec = importlib.util.spec_from_file_location("countertop", ROOT / "tools" / "countertop.py")
ct = importlib.util.module_from_spec(spec)
sys.argv = ["countertop.py"]
spec.loader.exec_module(ct)

OLD = {"items": [{"id": "a1", "text": "Milk", "done": False}, {"id": "a2", "text": "Eggs", "done": True}],
       "note": "Party on Friday", "updated": 1700000000}


class LocalListsTest(unittest.TestCase):
    def setUp(self):
        ct.LISTS_FILE.unlink(missing_ok=True)
        ct.NOTES.parent.mkdir(parents=True, exist_ok=True)
        ct.NOTES.write_text(json.dumps(OLD))
        lists = [{"id": "groc", "name": "Grocery", "kind": "This dashboard"},
                 {"id": "chores", "name": "Chores", "kind": "This dashboard", "daily": True}]
        self.sources = mock.patch.object(ct, "sources_load", return_value={"lists": lists})
        self.sources.start()
        self.addCleanup(self.sources.stop)

    def test_existing_items_carry_over(self):
        # the List tile and the phone page show what was on the list before the update
        for d in (ct.notes_view(), ct.local_list_view("groc")):
            self.assertEqual([i["text"] for i in d["items"]], ["Milk", "Eggs"])
            self.assertEqual(d["note"], "Party on Friday")
            self.assertFalse(d["readonly"])
        ct.local_list_apply("groc", {"op": "add", "text": "Bread"})
        self.assertEqual([i["text"] for i in ct.notes_view()["items"]], ["Milk", "Eggs", "Bread"])
        # the old file is left as it was
        self.assertEqual(json.loads(ct.NOTES.read_text()), OLD)

    def test_lists_are_separate(self):
        ct.local_list_apply("groc", {"op": "add", "text": "Bread"})
        ct.local_list_apply("chores", {"op": "clear"})
        ct.local_list_apply("chores", {"op": "add", "text": "Feed the cat"})
        self.assertEqual([i["text"] for i in ct.local_list_view("chores")["items"]], ["Feed the cat"])
        self.assertIn("Bread", [i["text"] for i in ct.local_list_view("groc")["items"]])

    def test_phone_page_edits_first_list(self):
        ct.notes_apply({"op": "add", "text": "Butter"})
        self.assertIn("Butter", [i["text"] for i in ct.local_list_view("groc")["items"]])

    def test_daily_reset(self):
        ct.local_list_apply("chores", {"op": "clear"})
        ct.local_list_apply("chores", {"op": "add", "text": "Feed the cat"})
        iid = ct.local_list_view("chores")["items"][0]["id"]
        ct.local_list_apply("chores", {"op": "toggle", "id": iid})
        ct.local_list_apply("groc", {"op": "toggle", "id": "a1"})
        self.assertTrue(ct.local_list_view("chores")["items"][0]["done"])
        with mock.patch.object(ct, "_today", return_value="2099-01-01"):
            self.assertFalse(ct.local_list_view("chores")["items"][0]["done"])     # daily list: ticks cleared
            self.assertTrue(ct.local_list_view("groc")["items"][0]["done"])        # other lists keep theirs
            self.assertEqual(len(ct.local_list_view("chores")["items"]), 1)        # items stay

    def test_not_a_dashboard_list(self):
        self.assertIsNone(ct.local_list_source("nope"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
