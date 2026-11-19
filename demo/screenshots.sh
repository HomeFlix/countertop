#!/bin/sh
# Regenerates the README screenshots with made-up data. Never reads your own work/ folder.
# Needs: python3, node, Playwright (npm i -D playwright && npx playwright install chromium),
#        ImageMagick (montage/convert) for the tile gallery and phone crop, Pillow to shrink the PNGs,
#        ffmpeg for the animated overview.gif.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
cp -R "$ROOT/tools" "$TMP/tools"
cp -R "$ROOT/demo/work" "$TMP/work"
python3 "$TMP/tools/countertop.py" --port 8091 > "$TMP/server.log" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null; rm -rf "$TMP"' EXIT
sleep 2
A="$ROOT/docs/screenshots"
BASE=http://127.0.0.1:8091 OUT="$A" node "$ROOT/demo/capture.js"
if command -v ffmpeg >/dev/null; then BASE=http://127.0.0.1:8091 OUT="$A" node "$ROOT/demo/record-gif.js"; else echo "(ffmpeg not installed: overview.gif not updated)"; fi
convert "$A/phone-list-full.png" -crop 1170x1500+0+0 -resize 520x "$A/phone-list.png" && rm "$A/phone-list-full.png"
( cd "$A/tiles" && montage agenda.png forecast.png countdown.png nextevent.png stocks.png sunmoon.png team.png worldclock.png \
    planes.png space.png joke.png onthisday.png -tile 4x3 -geometry 600x380+10+10 -background '#0d1a2b' ../tile-gallery.png )
rm -rf "$A/tiles"
python3 "$ROOT/demo/shrink.py" "$A" || echo "(Pillow not installed: screenshots left full size)"
echo "Screenshots written to $A"
