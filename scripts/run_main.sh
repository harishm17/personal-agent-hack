#!/bin/sh
# Restart the main app on port 8800 (the one behind the tunnel). Run from the repo root after each merge.
# No --reload: an open event stream keeps a reloading server waiting for ever.
cd "$(dirname "$0")/.." || exit 1
pkill -f 'uvicorn signoff.app:app --port 8800' 2>/dev/null
sleep 1
pkill -9 -f 'uvicorn signoff.app:app --port 8800' 2>/dev/null
mkdir -p .hk/state
SIGNOFF_SHEET="${SIGNOFF_SHEET:-sheet4}" nohup uv run -q uvicorn signoff.app:app --port 8800 --timeout-graceful-shutdown 2 > .hk/state/server.log 2>&1 &
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  code=$(curl -s -m 2 -o /dev/null -w '%{http_code}' localhost:8800/api/health)
  [ "$code" = 200 ] && break
  sleep 1
done
echo "main app: $code"
curl -s -m 3 localhost:8800/api/health
echo
