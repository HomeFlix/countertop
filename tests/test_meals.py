"""Meal ideas: picks by meal and diet, says why with the list and sales, keeps API keys out of errors.

Run with: python3 tests/test_meals.py
"""

import importlib.util
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
TMP = TemporaryDirectory()
os.environ["COUNTERTOP_DATA"] = TMP.name
spec = importlib.util.spec_from_file_location("countertop", ROOT / "tools" / "countertop.py")
ct = importlib.util.module_from_spec(spec)
sys.argv = ["countertop.py"]
spec.loader.exec_module(ct)


def meal(mid, title, cat, ings, steps="Cook it.\r\nServe it."):
    m = {"idMeal": mid, "strMeal": title, "strCategory": cat, "strArea": "American", "strInstructions": steps,
         "strMealThumb": "https://www.themealdb.com/images/media/meals/%s.jpg" % mid, "strSource": ""}
    for n, (mea, ing) in enumerate(ings, 1):
        m["strIngredient%d" % n], m["strMeasure%d" % n] = ing, mea
    return m


MEALS = {
    "1": meal("1", "Pancakes", "Breakfast", [["1 cup", "Flour"], ["2", "Eggs"], ["1 cup", "Milk"]]),
    "2": meal("2", "Bacon hash", "Breakfast", [["4 slices", "Bacon"], ["2", "Potatoes"]]),
    "3": meal("3", "Lemon chicken", "Chicken", [["6", "Chicken Thighs"], ["2", "Lemons"], ["", "Salt"]]),
    "4": meal("4", "Mushroom risotto", "Vegetarian", [["1 cup", "Arborio Rice"], ["8 oz", "Mushrooms"], ["", "Water"]]),
    "5": meal("5", "Prawn linguine", "Pasta", [["200g", "Linguine Pasta"], ["150g", "King Prawns"]]),
    "6": meal("6", "Apple crumble", "Dessert", [["4", "Apples"], ["100g", "Butter"]]),
}
CATS = {"Breakfast": ["1", "2"], "Chicken": ["3"], "Vegetarian": ["4"], "Pasta": ["5"], "Dessert": ["6"]}
SEEN = []


def fake_get_json(url, data=None, timeout=15):
    SEEN.append(url)
    u = urlparse(url)
    q = parse_qs(u.query)
    if "api.spoonacular.com" in u.netloc:
        if q.get("apiKey") != ["good-key"]:
            raise HTTPError(url, 401, "Unauthorized", {}, None)
        return {"totalResults": 3, "results": [{"id": 99, "title": "Tomato soup", "image": "https://img.spoonacular.com/recipes/99-556x370.jpg",
                "readyInMinutes": 25, "cuisines": ["American"], "sourceName": "Example Kitchen", "sourceUrl": "https://example.com/soup",
                "extendedIngredients": [{"name": "tomatoes", "amount": 1.5, "unit": "lb"}, {"name": "onion", "amount": 1, "unit": ""}],
                "analyzedInstructions": [{"steps": [{"step": "Simmer."}, {"step": "Blend."}]}]}]}
    if u.path.endswith("filter.php"):
        return {"meals": [{"idMeal": i} for i in CATS.get(q["c"][0], [])] or None}
    if u.path.endswith("lookup.php"):
        return {"meals": [MEALS[q["i"][0]]]}
    if u.path.endswith("categories.php"):
        return {"categories": [{}] * 14}
    raise AssertionError("unexpected request " + url)


class MealIdeasTest(unittest.TestCase):
    def setUp(self):
        ct._get_json = fake_get_json
        ct.MEAL_CACHE.clear()
        ct.MEAL_LOOKUPS.clear()
        ct.SALES["data"] = None
        ct.sources_write({k: [] for k in ct.SOURCE_KINDS})
        ct.NOTES.write_text(json.dumps({"items": [], "note": "", "updated": 0}))
        SEEN.clear()

    def test_breakfast_and_dessert(self):
        b = ct.meal_ideas("breakfast")
        self.assertEqual({i["title"] for i in b["ideas"]}, {"Pancakes", "Bacon hash"})
        self.assertTrue(all("/api/json/v1/1/" in u for u in SEEN), "no recipe source set up uses the free key")
        d = ct.meal_ideas("dessert")
        self.assertEqual([i["title"] for i in d["ideas"]], ["Apple crumble"])
        self.assertEqual(d["ideas"][0]["credit"], "TheMealDB")

    def test_diets(self):
        self.assertEqual([i["title"] for i in ct.meal_ideas("breakfast", "No pork")["ideas"]], ["Pancakes"])
        dinner = {i["title"] for i in ct.meal_ideas("dinner", "Vegetarian")["ideas"]}
        self.assertEqual(dinner, {"Mushroom risotto"})
        self.assertNotIn("Prawn linguine", {i["title"] for i in ct.meal_ideas("dinner", "No seafood")["ideas"]})
        self.assertEqual(ct.meal_ideas("dessert", "Vegan")["ideas"], [])

    def test_reason_from_list_and_sales(self):
        ct.NOTES.write_text(json.dumps({"items": [{"id": "a", "text": "Mushrooms", "done": False}], "note": "", "updated": 0}))
        ct.SALES["data"] = {"deals": [{"want": "Chicken thighs", "name": "Chicken thighs family pack", "store": "Corner Market", "why": "onlist"}]}
        d = ct.meal_ideas("dinner")
        why = {i["title"]: i["why"] for i in d["ideas"]}
        self.assertEqual(why["Lemon chicken"], "Uses chicken thighs, on sale at Corner Market")
        self.assertEqual(why["Mushroom risotto"], "Uses mushrooms from your list")
        self.assertEqual(why["Prawn linguine"], "")
        self.assertNotEqual(d["ideas"][-1]["why"], "Uses chicken thighs, on sale at Corner Market", "ideas with a reason come first")
        self.assertTrue(d["list"]["canAdd"])
        self.assertFalse(ct._uses("Water", "water"), "staples never count")

    def test_supporter_key_and_spoonacular(self):
        ct.sources_apply({"kind": "recipes", "op": "add", "item": {"name": "Mine", "service": "TheMealDB", "key": "abc123"}})
        ct.meal_ideas("dessert")
        self.assertTrue(any("/api/json/v1/abc123/" in u for u in SEEN))
        self.assertNotIn("abc123", json.dumps(ct.sources_public()), "the key never goes back to the browser")
        ct.sources_write({k: [] for k in ct.SOURCE_KINDS})
        ct.sources_apply({"kind": "recipes", "op": "add", "item": {"name": "Spoon", "service": "Spoonacular", "key": "good-key"}})
        d = ct.meal_ideas("lunch")
        i = d["ideas"][0]
        self.assertEqual((i["title"], i["credit"], i["link"], i["cat"]), ("Tomato soup", "Example Kitchen", "https://example.com/soup", "Ready in 25 min"))
        self.assertEqual(i["ingredients"][0], ["1½ lb", "tomatoes"])
        self.assertEqual(d["service"], "Spoonacular")

    def test_bad_key_is_not_shown(self):
        ct.sources_apply({"kind": "recipes", "op": "add", "item": {"name": "Spoon", "service": "Spoonacular", "key": "wrong-key"}})
        d = ct.meal_ideas("dinner")
        self.assertEqual(d["ideas"], [])
        self.assertIn("didn't accept the API key", d["error"])
        self.assertNotIn("wrong-key", json.dumps(d))
        self.assertNotIn("wrong-key", json.dumps(ct.status_view()))
        t = ct.recipes_test({"service": "Spoonacular", "key": "wrong-key"})
        self.assertFalse(t["ok"])
        self.assertTrue(ct.recipes_test({"service": "Spoonacular", "key": "good-key"})["ok"])
        self.assertTrue(ct.recipes_test({"service": "TheMealDB"})["ok"])


if __name__ == "__main__":
    unittest.main()
