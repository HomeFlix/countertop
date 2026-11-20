#!/bin/bash
# Builds the downloadable Countertop app for one processor: the server and its own Python inside, zipped.
#   ARCH=arm64 mac/package.sh       ->  dist/Countertop-<version>-mac-apple-silicon.zip
#   ARCH=x86_64 mac/package.sh      ->  dist/Countertop-<version>-mac-intel.zip
# Needs swiftc and the GitHub CLI (to find the Python build). Python comes from python-build-standalone.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$here")"
ARCH="${ARCH:-$(uname -m)}"
case "$ARCH" in arm64) TRIPLE=aarch64-apple-darwin; NAME=apple-silicon ;; x86_64) TRIPLE=x86_64-apple-darwin; NAME=intel ;; *) echo "ARCH?"; exit 2 ;; esac
VERSION=$(sed -n 's/^VERSION = "\([^"]*\)".*/\1/p' "$ROOT/tools/countertop.py")
work="$(mktemp -d)"

# a self-contained Python 3.12 for this processor
url=$(gh api repos/astral-sh/python-build-standalone/releases/latest --jq \
  "[.assets[].browser_download_url | select(test(\"cpython-3\\\\.12\\\\.[0-9]+\\\\+[0-9]+-$TRIPLE-install_only_stripped\\\\.tar\\\\.gz$\"))][0]")
[ -n "$url" ] && [ "$url" != "null" ] || { echo "No Python build found for $TRIPLE"; exit 1; }
echo "Python: $url"
curl -fsSL "$url" | tar -xz -C "$work"
PY="$work/python"
# trusted certificates for HTTPS (calendars, weather, update checks) and dateutil for repeating events
"$PY/bin/python3" -m pip install --quiet --disable-pip-version-check --no-compile --target "$work/site" certifi python-dateutil
SITE=$("$PY/bin/python3" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
cp -R "$work/site/." "$SITE/"
cp "$work/site/certifi/cacert.pem" "$PY/cacert.pem"
# drop what a server doesn't need
LIB=$(dirname "$SITE")
rm -rf "$LIB"/{test,idlelib,tkinter,turtledemo,ensurepip,lib2to3,pydoc_data} "$LIB"/site-packages/pip* "$PY"/include "$PY"/share "$PY"/lib/libtcl* "$PY"/lib/libtk* "$PY"/lib/tcl* "$PY"/lib/tk* "$PY"/lib/itcl* 2>/dev/null || true
find "$PY" -name '__pycache__' -type d -prune -exec rm -rf {} +

mkdir -p "$ROOT/dist"
APP="$work/out/Countertop.app"; mkdir -p "$work/out"
ARCH="$ARCH" "$here/make-app.sh" "$APP" --bundle "$ROOT" "$PY"
ZIP="$ROOT/dist/Countertop-$VERSION-mac-$NAME.zip"
rm -f "$ZIP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"
echo "$ZIP ($(du -h "$ZIP" | cut -f1))"
