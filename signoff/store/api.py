"""STORE routes: the passing-box SQL, refreshing the pool, the agent profile (served as a static file by app.py)."""
import importlib
import json
import pathlib
import threading
import sys
import time

from fastapi import APIRouter, HTTPException

from signoff import config
from signoff.db import passing, records
from signoff.obs import gate

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
router = APIRouter()
_refresh = {"running": False, "started_at": None, "finished_at": None, "result": None, "error": None}


def _engine_state() -> dict | None:
    try:
        return importlib.import_module("signoff.engine.state").get_state()
    except Exception:  # noqa: BLE001
        return None


@router.get("/api/sql/passing-box")
def passing_box(line_id: str):
    sheet_lines = {l["id"] for l in json.loads((ROOT / "sheets" / "sheet1.json").read_text())["lines"]}
    if line_id not in sheet_lines:
        raise HTTPException(404, "unknown line_id")
    state = _engine_state()
    try:
        if state:  # make the tables match what the engine shows now, so the two sets cannot differ
            records.write_sync(state)
        return passing.passing_box(line_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, "SingleStore unavailable: " + type(e).__name__)


def _do_refresh(live: bool) -> None:
    from signoff.store import ask, build_pool, fetch
    try:
        out = {"mode": "live" if live else "replay"}
        if live:
            out["fetched"] = {f"{s}|{q}": r for (s, q), r in fetch.fetch_raw(force=True).items()}
        rows = build_pool.build()
        out["products"] = {s: len(r) for s, r in rows.items()}
        if live:
            sheet = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
            out["answers"] = [a["store"] for a in ask.refresh(sheet["stores"])]
        try:
            importlib.import_module("signoff.engine.state").reload_data()
        except Exception as e:  # noqa: BLE001
            out["engine_reload"] = "skipped: " + type(e).__name__
        _refresh.update(result=out, error=None)
    except Exception as e:  # noqa: BLE001
        _refresh.update(error=type(e).__name__ + ": " + str(e)[:200])
    finally:
        _refresh.update(running=False, finished_at=time.time())


@router.post("/api/admin/refresh-pool")
def refresh_pool():
    """Refetch the stores (live) or rebuild the pool from the cached raw replies (replay mode)."""
    if _refresh["running"]:
        return {"started": False, **_refresh}
    live = config.mode() != "replay"
    _refresh.update(running=True, started_at=time.time(), finished_at=None, result=None, error=None)
    threading.Thread(target=_do_refresh, args=(live,), daemon=True).start()
    return {"started": True, "mode": "live" if live else "replay"}


@router.get("/api/admin/refresh-pool")
def refresh_status():
    return _refresh


@router.get("/api/gate/status")
def gate_status():
    """The Statsig gate `sie_reader`: value, deciding reader, last change, and both arms' outcome numbers."""
    gate.start()
    return gate.status()


@router.post("/api/gate/override")
def gate_override(body: dict):
    """Rehearsal without the console: {"value": true|false|null}. Status shows source "local override" while set."""
    v = body.get("value")
    if v not in (True, False, None):
        raise HTTPException(422, "value must be true, false or null")
    gate.set_override(v)
    return gate.status()


if "pytest" not in sys.modules:
    gate.start()
