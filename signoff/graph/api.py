"""Optional router. Read-only on the product: it reads records and never writes engine state.

GET  /api/graph?line_id=      one item's nodes and edges, with `backend` (which store answered)
GET  /api/graph               the whole graph in counts, and the items
GET  /api/graph/ask?line_id=  Cognee's saved answer to "what decides this item, and from whom?"
POST /api/graph/ask?line_id=  asks Cognee again and saves the answer (laptop only: LOCAL_ONLY in app.py)
GET  /api/graph/cognee        what Cognee holds: datasets, identities, ingest timings, every write attempt

The picture's nodes and edges come from the product's own records (`backend: "records"`). Cognee holds the same
knowledge, one dataset per owner, and answers the question (`backend: "cognee"`). Neither stands in for the
other: if Cognee cannot answer, the reply says so and carries no answer.
"""
import json
import pathlib

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from signoff.graph import build, cognee, records

router = APIRouter()
ANSWERS = cognee.DATA / "answers"
NO_STORE = {"Cache-Control": "no-store"}


def _graph():
    r = records.read()
    return r, build.build(r["state"], r["receipts"], r["order_text"], r["memory"])


def _held(sheet_id) -> dict:
    """What Cognee holds for this sheet, from the saved facts (no call to Cognee)."""
    facts = cognee.facts()
    ingests = [i for i in facts.get("ingests") or [] if i.get("sheet_id") == sheet_id]
    last = ingests[-1] if ingests else None
    return {"holds": bool(last and all("COMPLETED" in v for v in (last.get("status") or {}).values())),
            "datasets": {o: d["name"] for o, d in (facts.get("datasets") or {}).items()},
            "last_ingest": last and {k: last.get(k) for k in ("at", "scope", "seconds_total", "sentences", "cognee_graph")}}


@router.get("/api/graph")
def graph(line_id: str | None = None, near: int = 2):
    try:
        r, g = _graph()
    except Exception as error:  # noqa: BLE001
        return JSONResponse({"backend": "records", "error": "the run's records could not be read: " + type(error).__name__},
                            status_code=503, headers=NO_STORE)
    sheet = r["state"].get("sheet") or {}
    base = {"backend": "records", "backend_note": "built from the run's own records: " + r["read_from"],
            "sheet": {k: sheet.get(k) for k in ("id", "title", "invented")},
            "people": {role: (sheet.get(role) or {}).get("name") for role in ("issuer", "shopper")},
            "lines": [{"line_id": l["id"], "need": l["need"]} for l in sheet.get("lines") or []],
            "whole": build.counts(g), "memory_rows": len(r["memory"]), "memory_available": r["memory_available"],
            "cognee": _held(sheet.get("id"))}
    if line_id is None:
        return JSONResponse(base, headers=NO_STORE)
    v = build.view(g, line_id, near=max(0, min(near, 6)))
    if v is None:
        return JSONResponse(dict(base, error="no item %r on this sheet" % line_id), status_code=404, headers=NO_STORE)
    return JSONResponse(dict(base, **v), headers=NO_STORE)


def _answer_file(sheet_id, line_id) -> pathlib.Path:
    safe = "".join(ch for ch in "%s_%s" % (sheet_id, line_id) if ch.isalnum() or ch in "_-")
    return ANSWERS / (safe + ".json")


def _text(reply) -> str:
    """Cognee's search reply as plain text: it is a list of strings or of objects holding the text."""
    if isinstance(reply, str):
        return reply
    if isinstance(reply, list):
        return "\n".join(t for t in (_text(x) for x in reply) if t)
    if isinstance(reply, dict):
        for key in ("search_result", "text", "answer", "result"):
            if reply.get(key):
                return _text(reply[key])
    return ""


def question(need: str) -> str:
    return "What do we know that decides the %s, and from whom? Name who said each thing." % need


@router.get("/api/graph/ask")
def asked(line_id: str):
    r = records.read()
    sheet = r["state"].get("sheet") or {}
    f = _answer_file(sheet.get("id"), line_id)
    if not f.is_file():
        return JSONResponse({"backend": "cognee", "answered": False, "line_id": line_id,
                             "note": "Cognee has not been asked about this item"}, headers=NO_STORE)
    return JSONResponse(json.loads(f.read_text()), headers=NO_STORE)


@router.post("/api/graph/ask")
def ask(line_id: str):
    r = records.read()
    sheet = r["state"].get("sheet") or {}
    line = next((l for l in sheet.get("lines") or [] if l["id"] == line_id), None)
    if line is None:
        return JSONResponse({"backend": "cognee", "answered": False, "error": "no item %r on this sheet" % line_id}, status_code=404)
    q = question(line["need"])
    owners = list((cognee.facts().get("datasets") or {}))
    try:
        got = cognee.ask(q, owners)
        text = _text(got["reply"])
        if not text:
            raise cognee.CogneeError("Cognee returned no text")
    except Exception as error:  # noqa: BLE001
        cognee.log({"action": "ask", "identity": "system", "line_id": line_id, "status": 502, "reply": str(error)[:300]})
        return JSONResponse({"backend": "cognee", "answered": False, "line_id": line_id, "question": q,
                             "error": str(error)[:300]}, status_code=502, headers=NO_STORE)
    body = {"backend": "cognee", "answered": True, "line_id": line_id, "sheet_id": sheet.get("id"), "question": q,
            "answer": text, "seconds": got["seconds"], "search_type": got["search_type"], "datasets": got["datasets"],
            "at": cognee._now()}
    ANSWERS.mkdir(parents=True, exist_ok=True)
    _answer_file(sheet.get("id"), line_id).write_text(json.dumps(body, indent=1) + "\n")
    cognee.log({"action": "ask", "identity": "system", "line_id": line_id, "status": 200, "seconds": got["seconds"],
                "reply": text[:300]})
    return JSONResponse(body, headers=NO_STORE)


@router.get("/api/graph/cognee")
def held():
    facts = cognee.facts()
    log = cognee.read_log()
    return JSONResponse({"backend": "cognee", "configured": cognee.configured(),
                         "datasets": facts.get("datasets") or {}, "identities": facts.get("agents") or {},
                         "grants": facts.get("grants") or [], "ingests": facts.get("ingests") or [],
                         "refused": [e for e in log if e.get("action") == "write" and not e.get("accepted")],
                         "log": log[-50:]}, headers=NO_STORE)
