#!/bin/zsh
# Builds "Countertop List Sync.app" into ~/Applications, asks for its three settings the first time,
# and starts it at login. Needs the Xcode command line tools (xcode-select --install) for swiftc.
#   ./build.sh            build, set up and start
#   ./build.sh --setup    change the server, key or list name
#   ./build.sh --remove   stop it and remove it from login
set -e
cd "${0:A:h}"
APP="$HOME/Applications/Countertop List Sync.app"
ID="local.countertop.listsync"
AGENT="$HOME/Library/LaunchAgents/$ID.plist"
LOGF="$HOME/Library/Logs/countertop-listsync.log"

if [[ "$1" == "--remove" ]]; then
  launchctl bootout "gui/$(id -u)/$ID" 2>/dev/null || true
  rm -f "$AGENT"; rm -rf "$APP"; echo "Removed."; exit 0
fi

ask() {  # ask <defaults key> <question> <fallback>
  local cur; cur=$(defaults read "$ID" "$1" 2>/dev/null || echo "$3")
  local v; read "v?$2 [$cur]: "; defaults write "$ID" "$1" "${v:-$cur}"
}
if [[ "$1" == "--setup" ]] || ! defaults read "$ID" key >/dev/null 2>&1; then
  echo "In Controls > Setup > Lists, set your list to \"Sent from another app\", save, and copy its Sync key."
  ask server "Dashboard server address" "http://127.0.0.1:8090"
  ask key    "Sync key" ""
  ask list   "Reminders list name" "Grocery"
fi

mkdir -p "$APP/Contents/MacOS" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
swiftc -O main.swift -o "$APP/Contents/MacOS/CountertopListSync" -framework AppKit -framework EventKit
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Countertop List Sync</string>
  <key>CFBundleIdentifier</key><string>$ID</string>
  <key>CFBundleExecutable</key><string>CountertopListSync</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSUIElement</key><true/>
  <key>NSRemindersUsageDescription</key><string>Sends your grocery list to the kitchen dashboard.</string>
  <key>NSRemindersFullAccessUsageDescription</key><string>Sends your grocery list to the kitchen dashboard.</string>
</dict></plist>
PLIST
codesign --force --sign - "$APP" >/dev/null 2>&1 || true

cat > "$AGENT" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$ID</string>
  <key>ProgramArguments</key><array><string>$APP/Contents/MacOS/CountertopListSync</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>60</integer>
  <key>StandardOutPath</key><string>$LOGF</string>
  <key>StandardErrorPath</key><string>$LOGF</string>
</dict></plist>
PLIST
launchctl bootout "gui/$(id -u)/$ID" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$AGENT"
echo "Started. macOS will ask once whether it may use Reminders: click Allow."
echo "Log: $LOGF   (tail -f it to watch each send)"
