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
        memory = memory_api.everything() if hasattr(memory_api, "everything") else None
    except Exception:  # noqa: BLE001  (an absent or unfinished stream means no rows, and `read` says so)
        memory = None
    return body, held, memory


def _rows(memory) -> list:
    """Memory rows from whatever shape GET /api/memory has: a list, or lists nested under owners."""
    if isinstance(memory, list):
        return [r for r in memory if isinstance(r, dict) and "kind" in r and "owner" in r]
    if isinstance(memory, dict):
        return [r for v in memory.values() for r in _rows(v)]
    return []


def read() -> dict:
    base = config.env("SIGNOFF_GRAPH_FROM")
    state, receipts, memory = _remote(base) if base else _local()
    sheet = state.get("sheet") or {}
    doc = sheet.get("order_doc")
    path = ROOT / doc if doc else None
    order_text = path.read_text() if path and path.is_file() else None
    return {"state": state, "receipts": receipts, "order_text": order_text, "memory": _rows(memory),
            "memory_available": memory is not None, "read_from": base or "the engine, in process"}
