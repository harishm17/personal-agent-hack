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
from signoff import obs
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
    from signoff.store import sheetctx
    sheet_lines = {l["id"] for l in sheetctx.sheet()["lines"]}
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
    from signoff.store import ask, build_pool, fetch, sheetctx
    try:
        sid = sheetctx.active_id()
        out = {"mode": "live" if live else "replay", "sheet": sid}
        if live:
            out["fetched"] = {f"{s}|{q}": r for (s, q), r in fetch.fetch_raw(sid, force=True).items()}
        rows = build_pool.build(sid)
        out["products"] = {s: len(r) for s, r in rows.items()}
        if live:
            out["answers"] = [a["store"] for a in ask.refresh(sheet_id=sid)]
        try:
            if live:  # reads only the products whose text changed, then reloads the engine
                out["figures"] = importlib.import_module("signoff.extract.run").refresh()
            else:
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


@router.get("/api/obs/status")
def obs_status():
    """Amplitude event counters of this process: queued, sent, delivered (HTTP 200 from Amplitude), dropped, last error."""
    return {**obs.stats, "session_id": obs._state.get("session_id"), "experiments": obs._state.get("experiments"),
            "key_present": bool(obs.config.env("AMPLITUDE_AI_API_KEY")), "off": obs.config.env("SIGNOFF_OBS") == "off"}


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


@router.get("/api/egress")
def egress_ledger(limit: int = 500, sheet: str | None = None):
    """The outbound ledger of the active sheet (or `?sheet=all`): one row per message that left the process, counted from the
    saved log, so a restart does not reset it. Hashes and sizes only, never payloads."""
    from signoff.obs.egress import rows, summary
    rs = rows(sheet)
    return {"sheet": sheet or "active", "rows": rs[-max(1, min(limit, 5000)):], "summary": summary(rs)}


def _warm() -> None:
    try:
        from signoff.store import ucp
        ucp.warm(json.loads((ROOT / "sheets" / "sheet1.json").read_text())["stores"])
    except Exception:  # noqa: BLE001
        pass


if "pytest" not in sys.modules and config.mode() != "replay":
    threading.Thread(target=_warm, name="store-warm", daemon=True).start()


@router.get("/api/obs/events")
def obs_events(n: int = 200, session_id: str | None = None, sheet_id: str | None = None):
    """The local log of tool-call events (name, at, duration_ms, success), oldest first; the audit trail reads this."""
    return {"events": obs.recent(max(1, min(n, 5000)), session_id, sheet_id)}
