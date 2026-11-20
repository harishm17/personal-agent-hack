#!/bin/sh
# Contact sheet of frames: demo/contact.sh <framedir> <out.png> <from-ms> <to-ms>   (2 columns, 720 px wide each)
DIR="$(cd "$1" && pwd)"; OUT="$2"; FROM="${3:-0}"; TO="${4:-99999}"
HTML="$DIR/contact.html"
{
  echo '<body style="margin:0;background:#222;display:grid;grid-template-columns:repeat(2,720px);gap:0;font:14px monospace;color:#fff">'
  for f in "$DIR"/f*.png; do
    n=$(basename "$f" .png | sed 's/^f0*//'); n=${n:-0}
    if [ "$n" -ge "$FROM" ] && [ "$n" -le "$TO" ]; then echo "<div style='position:relative'><img src='file://$f' width=720><span style='position:absolute;left:4px;top:2px;background:#000'>$n ms</span></div>"; fi
  done
  echo '</body>'
} > "$HTML"
COUNT=$(grep -c '<img' "$HTML"); ROWS=$(( (COUNT + 1) / 2 ))
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files \
  --window-size=1440,$(( ROWS * 405 )) --screenshot="$OUT" "file://$HTML" 2>/dev/null
echo "$OUT ($COUNT frames)"
