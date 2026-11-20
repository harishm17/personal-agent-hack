"""Serves data/order/ on port 8005 so Airbyte (inside Docker) can fetch the export at
http://host.docker.internal:8005/order.csv. Run: uv run python -m signoff.airbyte.serve"""
import functools
import http.server
import pathlib

DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "order"
PORT = 8005

if __name__ == "__main__":
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIR))
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler).serve_forever()
