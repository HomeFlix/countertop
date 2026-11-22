"""Community: the gallery's list is read only when asked for, kept for ten minutes, and malformed items are dropped.

Run with: python3 tests/test_community.py
"""

import importlib.util
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parent.parent
TMP = TemporaryDirectory()
os.environ["COUNTERTOP_DATA"] = TMP.name
spec = importlib.util.spec_from_file_location("countertop", ROOT / "tools" / "countertop.py")
ct = importlib.util.module_from_spec(spec)
sys.argv = ["countertop.py"]
spec.loader.exec_module(ct)

INDEX = Path(TMP.name) / "index.json"
THEME = {"countertop": "theme", "format": 1, "name": "Glass", "values": {"tiles": "See-through"}}
EFFECT = {"countertop": "effect", "format": 1, "name": "Hearts", "effect": {"glyphs": ["💕"]}}


def entry(id, kind, item, version=1, **more):
    return dict({"id": id, "kind": kind, "name": item["name"], "description": "", "author": "kizit", "version": version, "updated": "2026-11-22", "item": item}, **more)


def publish(items, revoked=(), **more):
    INDEX.write_text(json.dumps(dict({"countertop": "gallery", "format": 1, "updated": "2026-11-22", "items": items, "revoked": list(revoked)}, **more)))


class CommunityTest(unittest.TestCase):
    def setUp(self):
        os.environ["COUNTERTOP_GALLERY_URL"] = INDEX.as_uri()
        ct.CACHE.update(at=0.0, data=None)

    def test_reads_items_and_the_revoked_list(self):
        publish([entry("themes/glass", "theme", THEME), entry("effects/hearts", "effect", EFFECT, 3)], revoked=["themes/old"])
        d = ct.community_index()
        self.assertEqual([i["id"] for i in d["items"]], ["themes/glass", "effects/hearts"])
        self.assertEqual((d["items"][1]["version"], d["revoked"], d["error"]), (3, ["themes/old"], ""))

    def test_drops_items_that_dont_look_right(self):
        good = entry("themes/glass", "theme", THEME)
        publish([good,
                 entry("themes/../../etc", "theme", THEME),              # not a plain id
                 entry("effects/glass", "theme", THEME),                 # id's folder doesn't match its kind
                 entry("themes/other", "theme", EFFECT),                 # the file inside is another kind
                 entry("themes/zero", "theme", THEME, 0),                # versions start at 1
                 entry("themes/text", "theme", THEME, "2"),
                 {"id": "themes/bare", "kind": "theme"}, "nonsense"])
        self.assertEqual([i["id"] for i in ct.community_index()["items"]], ["themes/glass"])

    def test_kept_for_ten_minutes_until_refreshed(self):
        publish([entry("themes/glass", "theme", THEME)])
        self.assertEqual(len(ct.community_index()["items"]), 1)
        publish([entry("themes/glass", "theme", THEME), entry("effects/hearts", "effect", EFFECT)])
        self.assertEqual(len(ct.community_index()["items"]), 1)          # still the earlier list
        self.assertEqual(len(ct.community_index(refresh=True)["items"]), 2)

    def test_a_failure_keeps_the_last_good_list(self):
        publish([entry("themes/glass", "theme", THEME)])
        ct.community_index()
        INDEX.write_text("not json")
        d = ct.community_index(refresh=True)
        self.assertEqual(len(d["items"]), 1)
        self.assertIn("Showing what was loaded earlier", d["error"])

    def test_a_failure_with_nothing_loaded_says_so(self):
        INDEX.write_text("not json")
        d = ct.community_index()
        self.assertEqual(d["items"], [])
        self.assertIn("Couldn't reach the gallery", d["error"])

    def test_refuses_a_newer_format_and_other_files(self):
        for bad in ({"countertop": "gallery", "format": 2, "items": []}, {"countertop": "layout", "format": 1, "items": []}, []):
            INDEX.write_text(json.dumps(bad))
            ct.CACHE.update(at=0.0, data=None)
            self.assertTrue(ct.community_index()["error"])


if __name__ == "__main__":
    unittest.main()
