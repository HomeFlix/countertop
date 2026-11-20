#!/bin/zsh
# Assembles Countertop.app. Used by build.sh (build from a clone) and package.sh (the download on each release).
#   make-app.sh OUT.app --folder REPO           the app runs tools/countertop.py from REPO with your python3
#   make-app.sh OUT.app --bundle REPO PYTHON    the server and the Python in PYTHON go inside the app
# ARCH=arm64 or x86_64 picks the processor (default: this Mac's). Needs swiftc (Xcode command line tools).
set -euo pipefail
here="${0:A:h}"
APP="$1"; MODE="$2"; ROOT="${3:A}"; PY="${4:-}"
ARCH="${ARCH:-$(uname -m)}"
VERSION=$(sed -n 's/^VERSION = "\([^"]*\)".*/\1/p' "$ROOT/tools/countertop.py")

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -target "$ARCH-apple-macos13" "$here/Countertop.swift" -o "$APP/Contents/MacOS/Countertop" \
  -framework AppKit -framework EventKit -framework ServiceManagement

# app icon from the Unraid icon
iconset="$(mktemp -d)/Countertop.iconset"; mkdir -p "$iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$ROOT/docker/unraid/icon.png" --out "$iconset/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$ROOT/docker/unraid/icon.png" --out "$iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$iconset" -o "$APP/Contents/Resources/Countertop.icns"

extra=""
if [[ "$MODE" == "--folder" ]]; then
  esc=${ROOT//&/&amp;}; esc=${esc//</&lt;}; esc=${esc//>/&gt;}
  extra="<key>CountertopFolder</key><string>$esc</string>"
elif [[ "$MODE" == "--bundle" ]]; then
  mkdir -p "$APP/Contents/Resources/server"
  rsync -a --exclude '*.backup*' --exclude '__pycache__' --exclude '.DS_Store' "$ROOT/tools" "$APP/Contents/Resources/server/"
  cp "$ROOT/LICENSE" "$APP/Contents/Resources/LICENSE.txt"
  ditto "$PY" "$APP/Contents/Resources/python"
else
  echo "usage: make-app.sh OUT.app --folder REPO | --bundle REPO PYTHON" >&2; exit 2
fi

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Countertop</string>
  <key>CFBundleDisplayName</key><string>Countertop</string>
  <key>CFBundleIdentifier</key><string>io.github.kizit.countertop</string>
  <key>CFBundleExecutable</key><string>Countertop</string>
  <key>CFBundleIconFile</key><string>Countertop</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHumanReadableCopyright</key><string>MIT License. See github.com/kizit/countertop</string>
  <key>NSAppleEventsUsageDescription</key><string>Countertop reads a Reminders list for the dashboard when you choose Apple Reminders in Setup.</string>
  <key>NSRemindersUsageDescription</key><string>Reminders Sync sends the list you pick to your Countertop dashboard.</string>
  <key>NSRemindersFullAccessUsageDescription</key><string>Reminders Sync sends the list you pick to your Countertop dashboard.</string>
  $extra
</dict></plist>
PLIST

codesign --force --deep --sign - "$APP" >/dev/null
echo "Made $APP (v$VERSION, $ARCH)"
