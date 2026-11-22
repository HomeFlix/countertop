"""Settings safety: upgrades run once and in order, a damaged file is never written over, backups roll.

Run with: python3 tests/test_settings.py
"""

import importlib.util
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
TMP = TemporaryDirectory()
os.environ["COUNTERTOP_DATA"] = TMP.name
spec = importlib.util.spec_from_file_location("countertop", ROOT / "tools" / "countertop.py")
ct = importlib.util.module_from_spec(spec)
sys.argv = ["countertop.py"]
spec.loader.exec_module(ct)

# A settings file from before tiles (v2: one fixed module per tile) and before looks/effects lists.
V2 = {"modules": {
    "general": {"on": True, "settings": {"lat": 38.6, "lon": -90.2}},
    "clock": {"on": True, "settings": {"h24": True}},
    "look": {"on": True, "settings": {"dateFmt": "Long", "items": [{"id": "cozy", "when": {"month": 12}, "values": {}}]}},
    "effects": {"on": True, "settings": {"weather": True, "seasonal": False, "density": 50}},
    "night": {"on": False, "settings": {}},
}}


def reset(data=None, raw=None):
    for f in Path(TMP.name).rglob("*"):
        if f.is_file():
            f.unlink()
    ct.CONFIG_PROBLEM.clear()
    if raw is not None:
        ct.CONFIG_FILE.write_text(raw)
    elif data is not None:
        ct.CONFIG_FILE.write_text(json.dumps(data))


def stored():
    return json.loads(ct.CONFIG_FILE.read_text())


def backups():
    return sorted(ct.BACKUP_DIR.glob("dashboard-*.json")) if ct.BACKUP_DIR.exists() else []


class Upgrades(unittest.TestCase):
    def test_new_install_gets_current_schema(self):
        reset()
        cfg = ct.config_load()
        self.assertEqual(stored()["schema"], ct.CONFIG_SCHEMA)
        self.assertTrue(cfg["modules"]["tiles"]["settings"]["items"])
        self.assertEqual(backups(), [])            # nothing existed to back up

    def test_old_file_is_upgraded_once_with_a_backup_first(self):
        reset(V2)
        ct.config_load()
        s = stored()
        self.assertEqual(s["schema"], ct.CONFIG_SCHEMA)
        self.assertIn("tiles", s["modules"])
        self.assertIn("items", s["modules"]["effects"]["settings"])
        self.assertEqual(s["modules"]["general"]["settings"].get("dateFmt"), "Long")    # moved out of look
        self.assertTrue(any(p.get("id") == "night" for p in s["modules"]["pages"]["settings"]["items"]))
        (b,) = backups()
        self.assertEqual(json.loads(b.read_text()), V2)                               # the original, untouched

    def test_current_file_is_left_alone(self):
        reset()
        ct.config_load()
        before = ct.CONFIG_FILE.read_text()
        ct.config_load()
        self.assertEqual(ct.CONFIG_FILE.read_text(), before)

    def test_unversioned_current_file_is_only_stamped(self):
        reset()
        ct.config_load()
        s = stored()
        del s["schema"]
        reset(s)
        ct.config_load()
        after = stored()
        self.assertEqual(after["schema"], ct.CONFIG_SCHEMA)
        self.assertEqual(after["modules"], s["modules"])


class DamagedFile(unittest.TestCase):
    def test_damaged_file_is_kept_and_last_backup_restored(self):
        reset()
        ct.config_load()
        good = stored()
        good["modules"].setdefault("general", {"on": True, "settings": {}})["settings"]["lat"] = 12.5
        ct.CONFIG_FILE.write_text(json.dumps(good))
        ct.config_backup(force=True)
        ct.CONFIG_FILE.write_text('{"modules": {"general": ')          # cut off mid-write
        cfg = ct.config_load()
        self.assertEqual(cfg["modules"]["general"]["settings"]["lat"], 12.5)
        (kept,) = Path(TMP.name).glob("dashboard.broken-*.json")
        self.assertEqual(kept.read_text(), '{"modules": {"general": ')
        self.assertTrue(ct.CONFIG_PROBLEM["restored"])
        self.assertTrue(any("couldn't be read" in p for p in ct.status_view()["problems"]))

    def test_damaged_file_without_backup_starts_fresh_but_is_kept(self):
        reset(raw="not json at all")
        cfg = ct.config_load()
        self.assertIn("tiles", cfg["modules"])
        (kept,) = Path(TMP.name).glob("dashboard.broken-*.json")
        self.assertEqual(kept.read_text(), "not json at all")
        self.assertEqual(ct.CONFIG_PROBLEM["restored"], "")

    def test_non_object_json_counts_as_damaged(self):
        reset(raw="[]")
        ct.config_load()
        self.assertEqual(len(list(Path(TMP.name).glob("dashboard.broken-*.json"))), 1)


class Backups(unittest.TestCase):
    def test_routine_saves_are_spaced_and_capped(self):
        reset()
        ct.config_load()
        mods = stored()["modules"]
        ct.config_save({"modules": mods}, quiet=True)
        ct.config_save({"modules": mods}, quiet=True)
        self.assertEqual(len(backups()), 1)        # second save inside BACKUP_EVERY: no new copy
        for _ in range(ct.BACKUP_KEEP + 3):
            ct.config_backup(force=True)
        self.assertEqual(len(backups()), ct.BACKUP_KEEP)

    def test_backup_after_quiet_period(self):
        reset()
        ct.config_load()
        mods = stored()["modules"]
        ct.config_save({"modules": mods}, quiet=True)
        (b,) = backups()
        old = time.time() - ct.BACKUP_EVERY - 5
        os.utime(b, (old, old))
        ct.config_save({"modules": mods}, quiet=True)
        self.assertEqual(len(backups()), 2)


class Language(unittest.TestCase):
    def test_defaults_to_automatic_and_keeps_a_chosen_language(self):
        reset()
        self.assertEqual(ct.config_load()["modules"]["general"]["settings"]["lang"], "Automatic")
        mods = ct.config_load()["modules"]
        mods["general"]["settings"]["lang"] = "Français"
        ct.config_save({"modules": mods})
        self.assertEqual(ct.config_load()["modules"]["general"]["settings"]["lang"], "Français")

    def test_every_language_choice_has_a_catalog(self):
        codes = {"English": "en", "Français": "fr"}
        for choice in ct.SCHEMA["general"]["settings"]["lang"]["choices"]:
            if choice == "Automatic" or codes[choice] == "en":
                continue
            json.loads((ROOT / "tools" / "lang" / (codes[choice] + ".json")).read_text())



class Themes(unittest.TestCase):
    def test_everyday_until_a_theme_is_picked_and_the_pick_is_kept(self):
        reset()
        look = ct.config_load()["modules"]["look"]["settings"]
        self.assertEqual(look["use"], "")            # older files have no pick: Everyday shows
        mods = ct.config_load()["modules"]
        mods["look"]["settings"]["items"] = [{"id": "tglass", "name": "Glass", "values": {"tiles": "See-through"}}]
        mods["look"]["settings"]["use"] = "tglass"
        ct.config_save({"modules": mods})
        self.assertEqual(ct.config_load()["modules"]["look"]["settings"]["use"], "tglass")


if __name__ == "__main__":
    unittest.main()
