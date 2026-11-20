"""Optional router: GET /api/airbyte/status, POST /api/airbyte/sync. The app never depends on it."""
import json
import threading
import time

from fastapi import APIRouter

from signoff.airbyte import sync
from signoff.db import conn

router = APIRouter()
_state = {"running": False, "started_at": None}
_lock = threading.Lock()


def _last_run() -> dict | None:
    try:
        c = conn.connect(timeout=5)
        try:
            cur = c.cursor()
            cur.execute("SELECT finished_at, ok, detail FROM airbyte_runs ORDER BY run_id DESC LIMIT 1")
            row = cur.fetchone()
        finally:
            c.close()
    except Exception:  # noqa: BLE001
        return None
    if not row:
        return None
    detail = row[2] if isinstance(row[2], dict) else json.loads(row[2])
    return {"finished_at": str(row[0]), "ok": bool(row[1]), **detail}


@router.get("/api/airbyte/status")
def status():
    last = _last_run()
    out = {"via": "airbyte", "running": _state["running"], "started_at": _state["started_at"], "last": None}
    if last:
        jobs = last.get("jobs", [])
        out["last"] = {
            "ok": last["ok"], "finished_at": last["finished_at"], "seconds": last.get("seconds"),
            "jobs": [{"stream": j["stream"], "job_id": j["job_id"], "connection_id": j["connection_id"],
                      "status": j["status"], "rows": j.get("rows_synced"), "duration": j.get("duration")} for j in jobs],
            "rows": last.get("loaded") or {},
            "expected": last.get("expected"), "error": last.get("error"),
            "path": "Airbyte File source -> Airbyte MySQL destination (local staging) -> copied into SingleStore",
        }
    return out


@router.post("/api/airbyte/sync")
def start_sync():
    with _lock:
        if _state["running"]:
            return {"started": False, "reason": "a sync is already running"}
        _state.update(running=True, started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"))

    def work():
        try:
            sync.run()
        finally:
            _state["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}
