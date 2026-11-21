"""Meal ideas from TheMealDB or Spoonacular."""
import random
import re
import threading
import time
from datetime import datetime
from fractions import Fraction
from urllib.parse import quote, urlencode
from server.sources import MEALDB_SRC, SPOON_SRC


# ---------- Meal ideas: breakfast, lunch, dinner and dessert ideas from a recipe service ----------
# Setup > Recipes picks the service. With nothing set up, TheMealDB's shared free key is used.
# TheMealDB: the free key browses by category and looks recipes up by id, which is all this needs.
#   A supporter key (a one-time purchase on themealdb.com) replaces the shared one. Credit TheMealDB.
# Spoonacular: each person's own key (the free plan has 50 points a day). Its terms allow keeping
#   recipe details for at most an hour, so ideas live in memory only and are fetched again after that.
#   Credit the recipe's own site and spoonacular.
MEALDB, SPOON = MEALDB_SRC, SPOON_SRC
MEAL_KINDS = ("breakfast", "lunch", "dinner", "dessert")
MEALDB_CATS = {"breakfast": ["Breakfast"], "lunch": ["Starter", "Side", "Pasta", "Miscellaneous"],
               "dinner": ["Beef", "Chicken", "Lamb", "Pork", "Seafood", "Pasta", "Vegetarian", "Vegan", "Goat"],
               "dessert": ["Dessert"]}
DIETS = ("Anything", "Vegetarian", "Vegan", "No pork", "No seafood", "No pork or seafood")
_MEAT = r"beef|steak|chicken|turkey|duck|lamb|mutton|goat|veal|venison|pork|bacon|ham|sausage|chorizo|salami|pancetta|prosciutto|pepperoni|mince|meatball|gelatin|lard|suet|anchov|stock cube|oxtail|kidney|liver"
_PORK = r"pork|bacon|\bham\b|sausage|chorizo|salami|pancetta|prosciutto|pepperoni|lard|gammon"
_FISH = r"fish|salmon|tuna|cod\b|haddock|mackerel|sardine|anchov|trout|prawn|shrimp|crab|lobster|clam|mussel|oyster|scallop|squid|calamari|octopus|kedgeree|saltfish"
_ANIMAL = _MEAT + r"|egg|milk|butter|cream|cheese|yogurt|yoghurt|honey|ghee|parmesan|mozzarella|cheddar|feta|ricotta|mascarpone|" + _FISH
DIET_BLOCK = {"Vegetarian": _MEAT + "|" + _FISH, "Vegan": _ANIMAL, "No pork": _PORK, "No seafood": _FISH, "No pork or seafood": _PORK + "|" + _FISH}
SPOON_DIET = {"Vegetarian": {"diet": "vegetarian"}, "Vegan": {"diet": "vegan"}, "No pork": {"excludeIngredients": "pork,bacon,ham,sausage"},
              "No seafood": {"intolerances": "seafood,shellfish"}, "No pork or seafood": {"excludeIngredients": "pork,bacon,ham,sausage", "intolerances": "seafood,shellfish"}}
SPOON_TYPE = {"breakfast": [{"type": "breakfast"}], "lunch": [{"type": "salad"}, {"type": "soup"}, {"query": "sandwich"}],
              "dinner": [{"type": "main course"}], "dessert": [{"type": "dessert"}]}
MEAL_CACHE = {}           # (source id, meal, diet) -> {at, day, ideas, error}
MEAL_LOOKUPS = {}         # TheMealDB id -> parsed recipe (TheMealDB lets us keep these)
MEAL_LOCK = threading.Lock()
MEAL_STATUS = {}          # source id -> {name, service, at, ok, error}
# pantry staples nobody needs a reason for, or a list item for
STAPLES = {"water", "salt", "pepper", "black pepper", "salt and pepper", "sea salt", "oil", "olive oil", "vegetable oil", "sugar", "ice", "boiling water", "cold water"}


def recipe_source(sid=""):
    """The recipe service a tile asked for: a Setup source by id, else the first one, else TheMealDB's free key."""
    L = [x for x in sources_load().get("recipes") or [] if x.get("service") in (MEALDB, SPOON, None, "")]
    src = next((x for x in L if x.get("id") == sid), None) or (L[0] if L else None)
    if not src:
        return {"id": "", "name": MEALDB, "service": MEALDB, "key": ""}
    return dict(src, service=src.get("service") or MEALDB)


def _diet_ok(diet, ings):
    pat = DIET_BLOCK.get(diet)
    return not pat or not any(re.search(pat, (n or "").lower()) for _, n in ings)


def _mealdb_parse(m):
    ings = []
    for n in range(1, 21):
        ing, mea = (m.get("strIngredient%d" % n) or "").strip(), (m.get("strMeasure%d" % n) or "").strip()
        if ing:
            ings.append([mea, ing])
    steps = [x.strip() for x in re.split(r"\r?\n+", m.get("strInstructions") or "") if x.strip()]
    steps = [re.sub(r"(?i)^(step\s*)?\d+[.):]\s*", "", x) for x in steps if not re.fullmatch(r"(?i)(step\s*)?\d+[.):]?", x)]
    thumb = m.get("strMealThumb") or ""
    return {"id": str(m.get("idMeal") or ""), "title": (m.get("strMeal") or "").strip(), "thumb": thumb + "/medium" if thumb else "", "big": thumb,
            "cat": m.get("strCategory") or "", "area": m.get("strArea") or "", "ingredients": ings, "steps": [x for x in steps if x],
            "link": m.get("strSource") or "", "credit": "TheMealDB"}


def _mealdb_ideas(src, meal, diet, want=4):
    key = (src.get("key") or "").strip() or "1"
    base = "https://www.themealdb.com/api/json/v1/%s/" % quote(key, safe="")
    cats = MEALDB_CATS[meal]
    if diet == "Vegetarian" and meal == "dinner":
        cats = ["Vegetarian", "Vegan", "Pasta"]
    elif diet == "Vegan" and meal in ("lunch", "dinner"):
        cats = ["Vegan", "Vegetarian", "Pasta"] + (["Side", "Starter"] if meal == "lunch" else [])
    pool = []
    for c in cats:
        for m in _get_json(base + "filter.php?c=" + quote(c), timeout=10).get("meals") or []:
            pool.append(str(m.get("idMeal")))
    pool = sorted(set(pool))
    if not pool:
        return []
    rnd = random.Random(datetime.now().strftime("%Y-%m-%d") + meal + diet)   # the same ideas all day, new ones tomorrow
    rnd.shuffle(pool)
    out = []
    for mid in pool[:want * 4]:
        r = MEAL_LOOKUPS.get(mid)
        if r is None:
            got = (_get_json(base + "lookup.php?i=" + quote(mid), timeout=10).get("meals") or [None])[0]
            if not got:
                continue
            r = MEAL_LOOKUPS[mid] = _mealdb_parse(got)
        if r["title"] and _diet_ok(diet, r["ingredients"]):
            out.append(dict(r))
        if len(out) >= want:
            break
    return out


def _spoon_ideas(src, meal, diet, want=4):
    q = {"apiKey": (src.get("key") or "").strip(), "number": want, "sort": "random", "addRecipeInformation": "true",
         "fillIngredients": "true", "instructionsRequired": "true"}
    opts = SPOON_TYPE[meal]
    q.update(opts[datetime.now().toordinal() % len(opts)])
    q.update(SPOON_DIET.get(diet, {}))
    j = _get_json("https://api.spoonacular.com/recipes/complexSearch?" + urlencode(q), timeout=15)
    out = []
    for r in j.get("results") or []:
        ings = [[(" ".join(x for x in [_amt(i.get("amount")), i.get("unit") or ""] if x)).strip(), i.get("name") or i.get("originalName") or ""]
                for i in r.get("extendedIngredients") or []]
        steps = [s.get("step", "").strip() for b in r.get("analyzedInstructions") or [] for s in b.get("steps") or []]
        mins = r.get("readyInMinutes")
        out.append({"id": str(r.get("id")), "title": (r.get("title") or "").strip(), "thumb": r.get("image") or "", "big": r.get("image") or "",
                    "cat": ("Ready in %d min" % mins) if mins else "", "area": (r.get("cuisines") or [""])[0],
                    "ingredients": [x for x in ings if x[1]], "steps": [s for s in steps if s],
                    "link": r.get("sourceUrl") or "", "credit": (r.get("sourceName") or "").strip() or "spoonacular", "via": "spoonacular.com"})
    return out


def _amt(a):
    if not a:
        return ""
    f = Fraction(a).limit_denominator(8)
    whole, part = divmod(f.numerator, f.denominator)
    frac = {"1/2": "½", "1/3": "⅓", "2/3": "⅔", "1/4": "¼", "3/4": "¾", "1/8": "⅛"}.get("%d/%d" % (part, f.denominator), "") if part else ""
    if part and not frac:
        return ("%g" % round(float(a), 2))
    return (str(whole) if whole else "") + frac or "0"


def _recipe_error(e, src):
    key = (src.get("key") or "").strip()
    code = getattr(e, "code", None)
    if src["service"] == SPOON and code == 402:
        return "Spoonacular's daily limit is used up. It resets at midnight UTC."
    if code in (401, 403):
        return "%s didn't accept the API key. Check it in Setup, Recipes." % src["service"]
    msg = str(getattr(e, "reason", None) or e)
    return ("Couldn't reach %s: %s" % (src["service"], msg.replace(key, "<key>") if key else msg))[:200]


def _norm_words(t):
    return [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in re.findall(r"[a-z]+", (t or "").lower())]


def _uses(ing, thing):
    """Whether a recipe ingredient and a list item or deal are the same food: all the words of the shorter one appear in the longer one."""
    a, b = _norm_words(ing), _norm_words(thing)
    if not a or not b or " ".join(a) in STAPLES:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return all(w in long_ for w in short) and len(" ".join(short)) >= 3


def meal_reason(idea, list_items, deals):
    names = [n for _, n in idea.get("ingredients") or []]
    for d in deals:
        want = d.get("want") or d.get("name") or ""
        hit = next((n for n in names if _uses(n, want)), None)
        if hit:
            return "Uses %s, on sale%s" % (hit.lower(), " at " + d["store"] if d.get("store") else "")
    for t in list_items:
        hit = next((n for n in names if _uses(n, t)), None)
        if hit:
            return "Uses %s from your list" % hit.lower()
    return ""


def meal_ideas(meal="dinner", diet="Anything", sid=""):
    meal = meal if meal in MEAL_KINDS else "dinner"
    diet = diet if diet in DIETS else "Anything"
    src = recipe_source(sid)
    day = datetime.now().strftime("%Y-%m-%d")
    ck = (src.get("id") or "", src["service"], meal, diet)
    # TheMealDB: the same ideas all day. Spoonacular: at most an hour, as its terms ask.
    ttl = 3600 if src["service"] == SPOON else 6 * 3600
    with MEAL_LOCK:
        c = MEAL_CACHE.get(ck)
        fresh = c and time.time() - c["at"] < (ttl if c["ideas"] else 600) and (src["service"] == SPOON or c["day"] == day)
        if not fresh:
            err, ideas = None, []
            try:
                ideas = (_spoon_ideas if src["service"] == SPOON else _mealdb_ideas)(src, meal, diet)
                if not ideas:
                    err = "No %s ideas matched. Try another diet setting." % meal
            except Exception as e:
                err = _recipe_error(e, src)
            if not ideas and c and c["ideas"] and src["service"] != SPOON:
                ideas = c["ideas"]                     # keep yesterday's ideas rather than an empty tile
            c = MEAL_CACHE[ck] = {"at": time.time(), "day": day, "ideas": ideas, "error": err}
            MEAL_STATUS[src.get("id") or ""] = {"name": src.get("name") or src["service"], "service": src["service"], "at": time.time(),
                                                 "ok": not err or bool(ideas), "error": err}
    try:
        nv = notes_view()
        list_items = [i["text"] for i in nv.get("items", []) if not i.get("done")]
        can_add = not nv.get("readonly")
        list_name = nv.get("list") or "Grocery"
    except Exception:
        list_items, can_add, list_name = [], False, ""
    deals = [d for d in ((SALES.get("data") or {}).get("deals") or [])]
    ideas = [dict(i, why=meal_reason(i, list_items, deals)) for i in c["ideas"]]
    ideas.sort(key=lambda i: not i["why"])               # a reason to cook it goes first
    return {"meal": meal, "diet": diet, "ideas": ideas, "error": c["error"] if not ideas else None, "service": src["service"],
            "list": {"name": list_name, "canAdd": can_add, "items": list_items}}


def recipes_test(item):
    """Setup's Test button for a recipe source: one small request with the key as typed (or the saved one)."""
    saved = next((x for x in sources_load().get("recipes") or [] if x.get("id") == item.get("id")), {}) if item.get("id") else {}
    src = {"service": item.get("service") or saved.get("service") or MEALDB, "key": (item.get("key") or saved.get("key") or "").strip()}
    if src["service"] == SPOON and not src["key"]:
        return {"ok": False, "error": "Paste your Spoonacular API key first."}
    try:
        if src["service"] == SPOON:
            j = _get_json("https://api.spoonacular.com/recipes/complexSearch?" + urlencode({"apiKey": src["key"], "number": 1, "query": "soup"}), timeout=15)
            return {"ok": True, "detail": "Spoonacular · %s recipes for soup" % "{:,}".format(j.get("totalResults") or 0)}
        j = _get_json("https://www.themealdb.com/api/json/v1/%s/categories.php" % quote(src["key"] or "1", safe=""), timeout=10)
        return {"ok": True, "detail": "TheMealDB · %d categories" % len(j.get("categories") or []) + ("" if src["key"] else " · free key")}
    except Exception as e:
        return {"ok": False, "error": _recipe_error(e, src)}


# names used only inside functions: imported last, so these modules can use each other
from server.core import _get_json  # noqa: E402
from server.feeds.sales import SALES  # noqa: E402
from server.lists import notes_view  # noqa: E402
from server.sources import sources_load  # noqa: E402
