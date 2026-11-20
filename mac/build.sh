#!/bin/zsh
# Builds Countertop.app from this copy of the repository into ~/Applications and opens it.
# The app runs the server from this folder with your python3, and keeps settings in its work/ folder,
# so updating is `git pull`, then Restart Server in the menu. Needs the Xcode command line tools:
#   xcode-select --install
# Prefer not to build? Download the ready-made app from https://github.com/kizit/countertop/releases
set -e
here="${0:A:h}"
APP="$HOME/Applications/Countertop.app"
mkdir -p "$HOME/Applications"
pkill -x Countertop 2>/dev/null && sleep 2 || true     # quitting the app also stops its server
"$here/make-app.sh" "$APP" --folder "$here/.."

# earlier builds were called "Kitchen Dashboard" (and the Reminders helper was its own app): retire them
launchctl bootout "gui/$(id -u)/local.kitchen-dashboard.menubar" 2>/dev/null || true
pkill -x KitchenDash 2>/dev/null || true
rm -rf "$HOME/Applications/Kitchen Dashboard.app"

open "$APP"
echo "Opened Countertop. Look for the fork and knife in the menu bar."
