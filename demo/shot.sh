#!/bin/sh
# Screenshot of the big screen at 1920 x 1080 with headless Chrome.
# Usage: demo/shot.sh [url] [out.png]     default: http://localhost:8003/ -> demo/shots/screen.png
URL="${1:-http://localhost:8003/}"
OUT="${2:-demo/shots/screen.png}"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1920,1080 --virtual-time-budget=4000 --screenshot="$OUT" "$URL" 2>/dev/null
echo "$OUT"
