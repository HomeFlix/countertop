"""Get the repository ready for a release: pick the next version number, set it in
tools/countertop.py, and turn the changelog's "Unreleased" notes into that version's section.

    python3 .github/prepare-release.py fix        # 0.3.1 -> 0.3.2
    python3 .github/prepare-release.py feature    # 0.3.1 -> 0.4.0
    python3 .github/prepare-release.py 1.0.0      # an exact version

Prints the new tag (e.g. v0.3.2). Stops with an error, and changes nothing, if there are no
notes under "## Unreleased" or the version would not go up.
"""
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "tools" / "countertop.py"
CHANGELOG = ROOT / "CHANGELOG.md"

how = sys.argv[1] if len(sys.argv) > 1 else ""
code = SERVER.read_text()
cur = re.search(r'^VERSION = "(\d+)\.(\d+)\.(\d+)"', code, re.M)
if not cur:
    sys.exit("Couldn't find VERSION in tools/countertop.py")
major, minor, patch = map(int, cur.groups())
if how == "fix":
    new = (major, minor, patch + 1)
elif how == "feature":
    new = (major, minor + 1, 0)
elif re.fullmatch(r"v?\d+\.\d+\.\d+", how):
    new = tuple(map(int, how.lstrip("v").split(".")))
else:
    sys.exit("usage: prepare-release.py fix | feature | X.Y.Z")
if new <= (major, minor, patch):
    sys.exit("v%d.%d.%d isn't newer than the current version v%d.%d.%d" % (new + (major, minor, patch)))
ver = "%d.%d.%d" % new

text = CHANGELOG.read_text()
sec = re.search(r"^## Unreleased[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
if not sec or not sec.group(1).strip():
    sys.exit('CHANGELOG.md has nothing under "## Unreleased". Add a line for each change people will notice, then try again.')
today = datetime.date.today().isoformat()
text = text[:sec.start()] + "## Unreleased\n\n## v%s (%s)\n\n%s\n\n" % (ver, today, sec.group(1).strip()) + text[sec.end():]
CHANGELOG.write_text(text)
SERVER.write_text(code[:cur.start()] + 'VERSION = "%s"' % ver + code[cur.end():])
print("v" + ver)
