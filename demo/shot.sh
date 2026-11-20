#!/bin/sh
# Screenshot of the big screen at 1920 x 1080 with headless Chrome.
# Usage: demo/shot.sh [path-and-query] [out.png]     default: / -> demo/shots/screen.png
# live=0 is added so the page opens no event stream (an open stream keeps headless Chrome waiting).
BASE="${SCREEN_URL:-http://localhost:8003}"
PATHQ="${1:-/}"
OUT="${2:-demo/shots/screen.png}"
case "$PATHQ" in
  *\#*) URL="$BASE${PATHQ%%#*}"; HASH="#${PATHQ#*#}" ;;
  *) URL="$BASE$PATHQ"; HASH="" ;;
esac
case "$URL" in *\?*) URL="$URL&live=0" ;; *) URL="$URL?live=0" ;; esac
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1920,1080 --virtual-time-budget=3000 --timeout=10000 --screenshot="$OUT" "$URL$HASH" 2>/dev/null
echo "$OUT"
