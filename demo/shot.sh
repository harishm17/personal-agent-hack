#!/bin/sh
# Screenshot of the big screen at 1920 x 1080 with headless Chrome.
# Usage: demo/shot.sh [path-and-query] [out.png]     default: / -> demo/shots/screen.png
# live=0 is added so the page opens no event stream (an open stream keeps headless Chrome waiting).
# MOTION=1 BUDGET=900 demo/shot.sh ... takes the picture 900 ms into the opening animation; default is no motion.
BASE="${SCREEN_URL:-http://localhost:8003}"
PATHQ="${1:-/}"
OUT="${2:-demo/shots/screen.png}"
case "$PATHQ" in
  *\#*) URL="$BASE${PATHQ%%#*}"; HASH="#${PATHQ#*#}" ;;
  *) URL="$BASE$PATHQ"; HASH="" ;;
esac
EXTRA="live=0"; [ "${MOTION:-0}" = "1" ] || EXTRA="$EXTRA&motion=0"
case "$URL" in *\?*) URL="$URL&$EXTRA" ;; *) URL="$URL?$EXTRA" ;; esac
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1920,1080 --virtual-time-budget="${BUDGET:-3000}" --timeout=10000 --screenshot="$OUT" "$URL$HASH" 2>/dev/null
echo "$OUT"
