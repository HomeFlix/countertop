"""Print one version's section of CHANGELOG.md, for the GitHub release notes.

    python3 .github/release-notes.py v0.2.0
Exits with an error if the version has no section or tools/countertop.py has a different VERSION.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tag = sys.argv[1] if len(sys.argv) > 1 else ""
m = re.match(r"v(\d+\.\d+\.\d+)$", tag)
if not m:
    sys.exit("usage: release-notes.py vX.Y.Z")
code = re.search(r'^VERSION = "([^"]+)"', (ROOT / "tools" / "countertop.py").read_text(), re.M)
if not code or code.group(1) != m.group(1):
    sys.exit("tools/countertop.py says VERSION = %s, but the tag is %s. Bump VERSION first." % (code and code.group(1), tag))
text = (ROOT / "CHANGELOG.md").read_text()
sec = re.search(r"^## %s\b[^\n]*\n(.*?)(?=^## |\Z)" % re.escape(tag), text, re.M | re.S)
if not sec or not sec.group(1).strip():
    sys.exit("CHANGELOG.md has no section for %s" % tag)
print(sec.group(1).strip())
