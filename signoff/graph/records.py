"""Reading the product's records for the graph. Read only: nothing here writes engine state.

In the app this runs in the same process as the engine, so the records are read through the engine's own
functions. `SIGNOFF_GRAPH_FROM` (a base URL, used on the stream's development port) reads the same records with
GET requests from a running app instead.
"""
import json
import pathlib

from signoff import config

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _remote(base):
    import httpx
    with httpx.Client(base_url=base.rstrip("/"), timeout=30) as c:
        state = c.get("/api/state").raise_for_status().json()
        receipts = c.get("/api/receipts").raise_for_status().json().get("receipts") or []
        memory = c.get("/api/memory")
        return state, receipts, (memory.json() if memory.status_code == 200 else None)


def _local():
    from signoff.engine import receipts, state
    body = json.loads(state.state_json())
    held = receipts.chain()["receipts"]
    try:
        from signoff.memory import api as memory_api  # the MEMORY stream's rows, when that stream is merged
        memory = memory_api.memory()
    except Exception:  # noqa: BLE001  (an absent or failing memory means no rows, and `read` says so)
        memory = None
    return body, held, memory


def _rows(memory) -> list:
    """Every row of GET /api/memory (`owners[].rows[]`, the shape MEMORY gave in NOTES/GRAPH.md)."""
    if not isinstance(memory, dict):
        return []
    return [r for o in memory.get("owners") or [] for r in o.get("rows") or [] if isinstance(r, dict)]


def read() -> dict:
    base = config.env("SIGNOFF_GRAPH_FROM")
    state, receipts, memory = _remote(base) if base else _local()
    sheet = state.get("sheet") or {}
    doc = sheet.get("order_doc")
    path = ROOT / doc if doc else None
    order_text = path.read_text() if path and path.is_file() else None
    return {"state": state, "receipts": receipts, "order_text": order_text, "memory": _rows(memory),
            "memory_available": memory is not None, "read_from": base or "the engine, in process"}


def reviews(line_id: str):
    """What GET /api/reviews?line_id= holds, or None when that route is absent or fails (the web stage is then left out)."""
    base = config.env("SIGNOFF_GRAPH_FROM")
    try:
        if base:
            import httpx
            r = httpx.get(base.rstrip("/") + "/api/reviews", params={"line_id": line_id}, timeout=30)
            return r.json() if r.status_code == 200 else None
        from signoff.reviews import api as reviews_api
        body = reviews_api.read(line_id)
        return body if isinstance(body, dict) else json.loads(body.body)
    except Exception:  # noqa: BLE001
        return None


def _route(path: str, params: dict, local):
    """One of the product's own GET routes: over HTTP on the development port, in process in the app. None when
    the route is absent or fails; the stage that needs it is then left out."""
    base = config.env("SIGNOFF_GRAPH_FROM")
    try:
        if base:
            import httpx
            got = httpx.get(base.rstrip("/") + path, params=params, timeout=30)
            return got.json() if got.status_code == 200 else None
        body = local()
        return body if isinstance(body, (dict, list)) else json.loads(body.body)
    except Exception:  # noqa: BLE001
        return None


def recall(line_id: str):
    """GET /api/memory/recall?line_id=: what the agent already knew that bears on this item."""
    def local():
        from signoff.memory import api as memory_api
        return memory_api.recall(line_id)
    return _route("/api/memory/recall", {"line_id": line_id}, local)


def talk():
    """GET /api/talk/threads: every message to a store's agent, what the guard withheld, and the replies."""
    def local():
        from signoff.talk import api as talk_api
        return talk_api.threads()
    return _route("/api/talk/threads", {}, local)
