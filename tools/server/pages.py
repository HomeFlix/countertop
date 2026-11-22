"""The dashboard and Controls pages, put together from their parts when they're served (no build step).

tools/dash/index.html and tools/control/index.html hold each page's HTML. A line `<!--#include <path>-->` in them
is replaced by that file's text, path relative to tools/: the page's own parts (tools/dash/, tools/control/) and
code both pages use (tools/shared/). The browser gets one page, just as if it were a single file.
"""
import re
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent      # tools/
INCLUDE = re.compile(r"^<!--#include ([\w./-]+)-->\n", re.M)


def page(name):
    """The page tools/<name>/index.html with its includes filled in, as bytes."""
    def fill(text, depth):
        def one(m):
            f = (TOOLS / m.group(1)).resolve()
            if depth > 2 or TOOLS not in f.parents or not f.is_file():
                raise ValueError("can't include %s" % m.group(1))
            return fill(f.read_text(encoding="utf-8"), depth + 1)
        return INCLUDE.sub(one, text)
    return fill((TOOLS / name / "index.html").read_text(encoding="utf-8"), 0).encode("utf-8")


def page_files(*names):
    """Every file the pages in these folders are made from (and shared/), for noticing a change."""
    return sorted(f for d in names + ("shared",) for f in (TOOLS / d).rglob("*") if f.is_file())
