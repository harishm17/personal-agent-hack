#!/bin/bash
# Assemble the demo video from a folder of screen recordings and a cuts file.
#
#   demo/recording/make.sh <clips-folder> <cuts-file> [out.mp4]
#
# The cuts file has one cut per line, fields separated by "|". Lines starting with # are skipped.
#
#   clip.mov | in | out | caption | zoom | speed
#   card     | seconds | first line / second line / third line
#
#   in, out   seconds or m:ss, measured in the clip (read them off QuickTime's scrubber)
#   caption   one short sentence; may be empty
#   zoom      optional "cx,cy,k": centre of the crop as fractions of the frame, and how much to enlarge
#             (0.5,0.5,1 is the whole frame; 0.85,0.5,1.8 is the right-hand side, 1.8 times larger)
#   speed     optional, 2 plays the cut twice as fast
#
# Output: 1920 x 1080, 30 frames a second, H.264, the picture above a caption band, a silent sound track
# (or VOICE=voice.m4a to lay one recording under the whole video). MAXMB=95 is the size limit: when the
# file is larger it is encoded once more at the bitrate that fits.
#
# Needs ffmpeg and Google Chrome. This ffmpeg has no text filter, so Chrome draws each caption as a
# picture in the product's own type and ffmpeg lays the recording on top of it.
set -euo pipefail

CLIPS="${1:?clips folder}"; CUTS="${2:?cuts file}"; OUT="${3:-demo/out/sign-off-demo.mp4}"
MAXMB="${MAXMB:-95}"; VOICE="${VOICE:-}"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
command -v ffmpeg >/dev/null || { echo "ffmpeg is not installed"; exit 1; }
[ -x "$CHROME" ] || { echo "Chrome not found at $CHROME (set CHROME=)"; exit 1; }
[ -f "$CUTS" ] || { echo "no cuts file: $CUTS"; exit 1; }

W=1920; H=1080; VW=1728; VH=972; VX=96; VY=12          # frame; picture size and place
WORK="$(mktemp -d "${TMPDIR:-/tmp}/signoff-video.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$(dirname "$OUT")"

trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"; printf '%s' "$s"; }
secs() { awk -v t="$1" 'BEGIN { n = split(t, a, ":"); s = 0; for (i = 1; i <= n; i++) s = s * 60 + a[i]; printf "%.3f", s }'; }
esc()  { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
shot() { "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
           --window-size=$W,$H --screenshot="$2" "file://$1" </dev/null >/dev/null 2>&1; [ -s "$2" ] || { echo "Chrome drew nothing for $1"; exit 1; }; }

STYLE="html,body{margin:0;width:${W}px;height:${H}px;background:#f7f8fa;color:#111827;overflow:hidden;
font-family:Inter,-apple-system,'SF Pro Text','Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased}
.pic{position:absolute;left:$((VX-1))px;top:$((VY-1))px;width:${VW}px;height:${VH}px;border:1px solid #e5e7eb;background:#fff}
.cap{position:absolute;left:160px;right:160px;top:$((VY+VH))px;bottom:0;display:flex;align-items:center;justify-content:center;
text-align:center;font-size:34px;line-height:40px;font-weight:500;letter-spacing:-0.01em}
.card{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:22px;text-align:center;padding:0 240px}
.card div{font-size:38px;line-height:50px;color:#4b5563}.card div:first-child{font-size:60px;line-height:70px;font-weight:600;color:#111827;letter-spacing:-0.02em;margin-bottom:14px}"

ENC=(-c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -r 30 -video_track_timescale 30000 -an)
n=0; : > "$WORK/list.txt"
while IFS= read -r line || [ -n "$line" ]; do
  case "$(trim "$line")" in ""|\#*) continue ;; esac
  IFS='|' read -r f1 f2 f3 f4 f5 f6 <<< "$line"
  src="$(trim "${f1:-}")"; n=$((n + 1)); seg="$WORK/seg$(printf '%03d' "$n").mp4"
  if [ "$src" = "card" ]; then
    dur="$(secs "$(trim "${f2:-4}")")"
    body="$(esc "$(trim "${f3:-}")" | awk '{ k = split($0, a, " / "); for (i = 1; i <= k; i++) printf "<div>%s</div>", a[i] }')"
    printf '<!doctype html><meta charset="utf-8"><style>%s</style><div class="card">%s</div>' "$STYLE" "$body" > "$WORK/c$n.html"
    shot "$WORK/c$n.html" "$WORK/c$n.png"
    ffmpeg -nostdin -v error -y -loop 1 -framerate 30 -t "$dur" -i "$WORK/c$n.png" "${ENC[@]}" "$seg"
    echo "cut $n  card  ${dur}s"
  else
    clip="$CLIPS/$src"; [ -f "$clip" ] || { echo "cut $n: no such clip: $clip"; exit 1; }
    in="$(secs "$(trim "${f2:-0}")")"; out="$(secs "$(trim "${f3:-0}")")"
    cap="$(trim "${f4:-}")"; zoom="$(trim "${f5:-}")"; speed="$(trim "${f6:-}")"; speed="${speed:-1}"
    awk -v a="$in" -v b="$out" 'BEGIN { exit !(b > a) }' || { echo "cut $n ($src): out must be after in"; exit 1; }
    printf '<!doctype html><meta charset="utf-8"><style>%s</style><div class="pic"></div><div class="cap">%s</div>' "$STYLE" "$(esc "$cap")" > "$WORK/c$n.html"
    shot "$WORK/c$n.html" "$WORK/c$n.png"
    crop=""
    if [ -n "$zoom" ]; then
      dims="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$clip" </dev/null)"
      crop="$(awk -v d="$dims" -v z="$zoom" 'BEGIN { split(d, s, ","); split(z, q, ","); k = (q[3] < 1 ? 1 : q[3]);
        w = int(s[1] / k / 2) * 2; h = int(s[2] / k / 2) * 2; x = s[1] * q[1] - w / 2; y = s[2] * q[2] - h / 2;
        if (x < 0) x = 0; if (y < 0) y = 0; if (x > s[1] - w) x = s[1] - w; if (y > s[2] - h) y = s[2] - h;
        printf "crop=%d:%d:%d:%d,", w, h, int(x), int(y) }')"
    fi
    ffmpeg -nostdin -v error -y -loop 1 -framerate 30 -i "$WORK/c$n.png" -ss "$in" -to "$out" -i "$clip" -filter_complex \
      "[1:v]${crop}setpts=(PTS-STARTPTS)/${speed},fps=30,scale=${VW}:${VH}:force_original_aspect_ratio=decrease:flags=lanczos,pad=${VW}:${VH}:(ow-iw)/2:(oh-ih)/2:color=white[v];[0:v][v]overlay=${VX}:${VY}:shortest=1[o]" \
      -map "[o]" "${ENC[@]}" "$seg"
    echo "cut $n  $src  $in to $out  x$speed  ${cap:0:60}"
  fi
  echo "file '$seg'" >> "$WORK/list.txt"
done < "$CUTS"
[ "$n" -gt 0 ] || { echo "the cuts file has no cuts"; exit 1; }

ffmpeg -nostdin -v error -y -f concat -safe 0 -i "$WORK/list.txt" -c copy "$WORK/joined.mp4"
dur="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK/joined.mp4")"
if [ -n "$VOICE" ]; then
  [ -f "$VOICE" ] || { echo "no such voice file: $VOICE"; exit 1; }
  ffmpeg -nostdin -v error -y -i "$WORK/joined.mp4" -i "$VOICE" -map 0:v -map 1:a -af apad -t "$dur" -c:v copy -c:a aac -b:a 128k -movflags +faststart "$OUT"
else
  ffmpeg -nostdin -v error -y -i "$WORK/joined.mp4" -f lavfi -i anullsrc=r=48000:cl=stereo -map 0:v -map 1:a -t "$dur" -c:v copy -c:a aac -b:a 64k -movflags +faststart "$OUT"
fi

size() { echo $(( $(stat -f%z "$1" 2>/dev/null || stat -c%s "$1") / 1048576 )); }
if [ "$(size "$OUT")" -ge "$MAXMB" ]; then
  kbps="$(awk -v mb="$MAXMB" -v d="$dur" 'BEGIN { printf "%d", mb * 8192 * 0.9 / d - 128 }')"
  echo "over ${MAXMB} MB: encoding again at ${kbps} kb/s"
  ffmpeg -nostdin -v error -y -i "$OUT" -c:v libx264 -preset medium -b:v "${kbps}k" -maxrate "${kbps}k" -bufsize "$((kbps * 2))k" -pix_fmt yuv420p -c:a copy -movflags +faststart "$WORK/small.mp4"
  mv "$WORK/small.mp4" "$OUT"
fi
awk -v d="$dur" -v o="$OUT" -v mb="$(size "$OUT")" 'BEGIN { printf "%s  %d:%02d  about %d MB%s\n", o, int(d / 60), int(d) % 60, mb, (d > 180 ? "  (over 3:00: cut something)" : "") }'
