"""Library previews: a layout tried on the screen replaces only pages, tiles and look, ends on time, and is never saved.

Run with: python3 tests/test_trial.py
"""

import importlib.util
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

PAGES = [{"id": "main", "name": "Main", "on": True, "cols": 48, "slots": [{"id": "s0", "x": 0, "y": 0, "w": 48, "h": 32, "mod": "t0"}]}]
TILES = [{"id": "t0", "type": "note", "settings": {"text": ["Hello"]}}]


class TrialTest(unittest.TestCase):
    def tearDown(self):
        ct.trial_stop()
        ct.TRIALS.clear()

    def test_preview_changes_only_layout_and_look(self):
        out = ct.trial_add({"pages": PAGES, "tiles": TILES, "look": {"accent": "#ff0000", "items": ["x"]}, "name": "Test"})
        cfg = ct.trial_apply(ct.config_load(), out["id"])
        m = cfg["modules"]
        self.assertEqual(m["pages"]["settings"]["items"], PAGES)
        self.assertEqual(m["tiles"]["settings"]["items"], TILES)
        self.assertEqual(m["look"]["settings"]["accent"], "#ff0000")
        self.assertNotEqual(m["look"]["settings"]["items"], ["x"])      # other looks and the schedule stay as saved
        self.assertNotIn("until", out)                                   # a preview isn't on the screen
        self.assertIsNone(ct.trial_screen())

    def test_screen_trial_ends_and_changes_version(self):
        self.assertEqual(ct.trial_version(), 0)
        out = ct.trial_add({"pages": PAGES, "tiles": TILES, "look": {}, "name": "Test", "screen": True, "seconds": 60})
        live = ct.trial_screen()
        self.assertEqual(live["id"], out["id"])
        self.assertGreater(ct.trial_version(), 0)
        with mock.patch.object(ct.time, "time", return_value=live["until"] + 1):
            self.assertIsNone(ct.trial_screen())
            self.assertEqual(ct.trial_version(), 0)

    def test_stop_and_limits(self):
        ct.trial_add({"pages": PAGES, "tiles": TILES, "look": {}, "screen": True, "seconds": 99999})
        self.assertLessEqual(ct.TRIAL_SCREEN["until"] - ct.time.time(), 601)
        ct.trial_stop()
        self.assertIsNone(ct.trial_screen())
        with self.assertRaises(ValueError):
            ct.trial_add({"pages": [], "tiles": [], "look": {}})        # no main page
        with self.assertRaises(ValueError):
            ct.trial_add({"pages": "nope", "tiles": []})

    def test_nothing_written(self):
        before = ct.CONFIG_FILE.read_text() if ct.CONFIG_FILE.exists() else None
        ct.trial_add({"pages": PAGES, "tiles": TILES, "look": {}, "screen": True})
        after = ct.CONFIG_FILE.read_text() if ct.CONFIG_FILE.exists() else None
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
