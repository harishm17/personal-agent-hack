"""Serves data/order/ on port 8005 so the tunnel (and Airbyte through it) can fetch the export.
`start()` runs it in a thread for the length of one sync; `python -m signoff.airbyte.serve` runs it by hand."""
import functools
import http.server
import pathlib
import threading

DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "order"
PORT = 8005


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def start(port: int = PORT) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(_Quiet, directory=str(DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    start()
    threading.Event().wait()
