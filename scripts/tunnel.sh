#!/bin/sh
# Start the day's public tunnel to the main app (port 8800) if it is not running, and record its address.
# A quick tunnel gets a NEW address every start: the phone must re-enrol (keys are per address) and stores
# fetch the profile at the new address. Never restart it unless it has died.
cd "$(dirname "$0")/.." || exit 1
KEYS="$HOME/.config/tokensand.env"
if pgrep -f 'cloudflared tunnel --url http://127.0.0.1:8800' >/dev/null; then
  echo "tunnel already running: $(grep '^PUBLIC_URL=' "$KEYS" | cut -d= -f2)"; exit 0
fi
mkdir -p .hk/state
nohup cloudflared tunnel --url http://127.0.0.1:8800 > .hk/state/tunnel.log 2>&1 &
URL=""
for i in $(seq 1 40); do URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' .hk/state/tunnel.log | head -1); [ -n "$URL" ] && break; sleep 1; done
[ -z "$URL" ] && { echo "no tunnel address after 40 s; see .hk/state/tunnel.log"; exit 1; }
if grep -q '^PUBLIC_URL=' "$KEYS"; then sed -i '' "s#^PUBLIC_URL=.*#PUBLIC_URL=$URL#" "$KEYS"; else echo "PUBLIC_URL=$URL" >> "$KEYS"; fi
cp "$KEYS" .env
echo "new tunnel: $URL"
echo "now run: sh scripts/run_main.sh   (the app reads the new address), then reload the phone at $URL/phone/"
