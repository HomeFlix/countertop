#!/bin/zsh
# Builds "Kitchen Dashboard.app" into ~/Applications and opens it.
# Needs the Xcode command line tools (xcode-select --install) for swiftc.
set -e
cd "${0:A:h}"
APP="$HOME/Applications/Kitchen Dashboard.app"
pkill -x KitchenDash 2>/dev/null || true
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
swiftc -O main.swift -o "$APP/Contents/MacOS/KitchenDash" -framework AppKit
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Countertop</string>
  <key>CFBundleIdentifier</key><string>local.kitchen-dashboard.menubar</string>
  <key>CFBundleExecutable</key><string>KitchenDash</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSUIElement</key><true/>
  <key>NSAppleEventsUsageDescription</key><string>The dashboard server reads your Grocery list from Reminders.</string>
</dict></plist>
PLIST
codesign --force --sign - "$APP" >/dev/null 2>&1 || true
open "$APP"
echo "Built and opened: $APP"
