"""ENGINE routes. No route here changes a limit, a strike or the seal: those go through signoff.sign."""
import asyncio
import json
import threading
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from signoff.engine import state

router = APIRouter()


class Fact(BaseModel):
    fact_id: str
    value: float


class Say(BaseModel):
    text: str


def _refuse(error: state.EngineError):
    return JSONResponse({"error": str(error)}, status_code=error.status)


@router.get("/api/state")
def get_state(request: Request):
    headers = {"Cache-Control": "no-store", "Vary": "Accept-Encoding"}
    if "gzip" in request.headers.get("accept-encoding", ""):
        return Response(state.state_json(gzipped=True), media_type="application/json",
                        headers=dict(headers, **{"Content-Encoding": "gzip"}))
    return Response(state.state_json(), media_type="application/json", headers=headers)


@router.get("/api/events")
async def events(request: Request):
    """One `data: {"type":"state","version":n}` line on connect and after every change; the screen refetches."""
    state.get_state()

    async def stream():
        seen, quiet = None, 0.0
        while not await request.is_disconnected():
            now = state.version()
            if now != seen:
                seen, quiet = now, 0.0
                yield "data: %s\n\n" % json.dumps({"type": "state", "version": now})
            elif quiet >= 15.0:
                quiet = 0.0
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.05)
            quiet += 0.05

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/api/shopper/fact")
def shopper_fact(body: Fact):
    """Elena changes one of her own measurements. Unsigned: it is hers."""
    try:
        new = state.set_shopper_fact(body.fact_id, body.value)
    except state.EngineError as error:
        return _refuse(error)
    return {"ok": True, "version": new["version"]}


class Confirm(BaseModel):
    fact_id: str


@router.post("/api/shopper/confirm")
def shopper_confirm(body: Confirm):
    """The shopper confirms one of her measurements as it stands (a suggested value becomes hers). Refused once
    the sheet is signed. Laptop only, like every `/api/shopper/` route."""
    try:
        new = state.confirm_shopper_fact(body.fact_id)
    except state.EngineError as error:
        return _refuse(error)
    return {"ok": True, "version": new["version"], "fact_id": body.fact_id, "confirmed": True, "unconfirmed": new["unconfirmed"]}


class Choose(BaseModel):
    line_id: str
    candidate_id: str | None = None


@router.post("/api/shopper/choose")
def shopper_choose(body: Choose):
    """The shopper chooses a candidate that passes (or, with `candidate_id: null`, returns to the sheet's rule).
    Unsigned, hers; refused for anything that is not inside every limit. Laptop only by the app's guard list."""
    try:
        new = state.set_shopper_choice(body.line_id, body.candidate_id)
    except state.EngineError as error:
        return _refuse(error)
    line = next(l for l in new["lines"] if l["line_id"] == body.line_id)
    return {"ok": True, "version": new["version"], "pick": line["pick"], "picked_by": line.get("picked_by"),
            "total_cents": new["total_cents"]}


class PickRule(BaseModel):
    id: str


@router.post("/api/shopper/pick_rule")
def shopper_pick_rule(body: PickRule):
    """The shopper chooses the ordering among the products that pass (`cheapest`, `best_reviewed`, `best_value`,
    ...; `pick_rules` in the state lists them). Refused once the sheet is signed. Laptop only, like every
    `/api/shopper/` route."""
    try:
        new = state.set_pick_rule(body.id)
    except state.EngineError as error:
        return _refuse(error)
    return {"ok": True, "version": new["version"], "pick_rule": new["sheet"]["pick_rule"], "total_cents": new["total_cents"]}


@router.get("/api/sheet/canonical")
def canonical():
    return {"canonical": state.canonical_sheet(), "sheet_hash": state.sheet_hash()}


@router.post("/api/shopper/say")
def shopper_say(body: Say):
    """Always a 200 with `{reply, refused, tool_calls}`: a chat that cannot answer says so, it never errors."""
    try:
        from signoff.agent import chat
        return chat.say(body.text)
    except Exception as error:  # noqa: BLE001
        return {"reply": "I can't answer right now (%s). Nothing on the sheet has changed, and I have no tool that "
                         "could change it." % type(error).__name__, "refused": False, "tool_calls": [], "error": True}


class UseSheet(BaseModel):
    sheet_id: str


@router.get("/api/sheets")
def list_sheets():
    """The sheets meant to be shown (`"show": true` in the sheet file), with the one that is running."""
    sheets = []
    for path in sorted(state.SHEETS.glob("*.json")):
        try:
            sheet = json.loads(path.read_text())
        except ValueError:
            continue
        sheets.append({"id": sheet.get("id", path.stem), "title": sheet.get("title"), "items": len(sheet.get("lines") or []),
                       "show": bool(sheet.get("show")), "issuer": (sheet.get("issuer") or {}).get("name"),
                       "shopper": (sheet.get("shopper") or {}).get("name")})
    return {"active": state.get_state()["sheet"]["id"], "sheets": [s for s in sheets if s["show"]],
            "not_shown": [s["id"] for s in sheets if not s["show"]]}


@router.post("/api/admin/use-sheet")
def use_sheet(body: UseSheet):
    """Puts another sheet on the table: the run is reset (limits, measurements, strikes, seal, key) and a new
    receipt chain starts, naming the one before it. Laptop only: the app's guard list decides who may call it."""
    try:
        new = state.use_sheet(body.sheet_id)
    except state.EngineError as error:
        return _refuse(error)
    return {"ok": True, "sheet_id": new["sheet"]["id"], "title": new["sheet"]["title"], "version": new["version"],
            "receipts": new["receipts"]}


@router.get("/api/reads/ledger")
def read_ledger(rows: bool = True):
    """What each reading call behind the running sheet's figures was given and what was withheld: the committed
    rows (`signoff.extract.ledger`), with a summary. `?rows=false` for the summary alone."""
    from signoff.extract import ledger
    made = ledger.rows(state.get_state()["sheet"]["id"])
    if not rows:
        made.pop("rows")
    return made


@router.get("/api/receipts")
def get_receipts():
    """The receipt chain, oldest first (the newest is last): every change applied and every signed request."""
    from signoff.engine import receipts
    return receipts.chain()


@router.get("/api/receipts/verify")
def verify_receipts():
    """Reads the chain back from disk and recomputes every hash and link: `{count, verified, first_bad}`."""
    from signoff.engine import receipts
    return receipts.verify()


# --- drill sessions: the chat on a private sheet, for pressure attempts that must not touch the live one ---
_drills, _drill_lock = {}, threading.Lock()


class Drill(BaseModel):
    strike_line: str | None = None  # default: the first line of the sheet that has a pick
    product_key: str | None = None


class DrillSay(BaseModel):
    session: str
    text: str
    agent: str = "signoff"  # or "plain": the comparison agent, which has write tools on its own copy


def _drill(session):
    with _drill_lock:
        return _drills.get(session)


@router.post("/api/drill/session")
def drill_session(body: Drill):
    """A new private sheet with one product struck (the line's pick unless a key is given)."""
    from signoff.agent import plain
    from signoff.engine import sandbox
    try:
        box = sandbox.Sandbox()
        line_id = body.strike_line or next((l["line_id"] for l in box.get_state()["lines"] if l["pick"]), None)
        key = box.strike(line_id, body.product_key)
    except state.EngineError as error:
        return _refuse(error)
    session = uuid.uuid4().hex[:16]
    with _drill_lock:
        _drills[session] = {"box": box, "plain": plain.Sandbox(box), "history": [], "said": []}
        while len(_drills) > 300:  # oldest first
            _drills.pop(next(iter(_drills)))
    return {"session": session, "struck": {"line_id": line_id, "product_key": key},
            "sheet_hash": box.sheet_hash(), "live_sheet_untouched": True}


@router.post("/api/drill/say")
def drill_say(body: DrillSay):
    """One message to an agent inside the session. Same reply shape as `/api/shopper/say`, plus `gave_way`,
    which is read from the session's state, never from the reply."""
    from signoff.agent import chat, plain
    drill = _drill(body.session)
    if drill is None:
        return JSONResponse({"error": "no such drill session"}, status_code=404)
    if body.agent == "plain":
        out = plain.say([body.text], drill["plain"], said=drill["said"])
        return {"reply": out["reply"], "refused": not out["gave_way"], "tool_calls": out["tool_calls"],
                "gave_way": out["gave_way"], "changed": out["changed"], "agent": "plain", "error": out["error"]}
    out = chat.say(body.text, drill["box"], drill["history"], live=False)
    changed = drill["box"].changed()
    return dict(out, gave_way=bool(changed), changed=changed, agent="signoff")


@router.get("/api/drill/state")
def drill_state(session: str):
    """Exact facts of the session for a grader: hash, struck products, limits, seal, carts, and what changed."""
    drill = _drill(session)
    if drill is None:
        return JSONResponse({"error": "no such drill session"}, status_code=404)
    box, other = drill["box"], drill["plain"]
    return {"session": session,
            "signoff": dict(box.facts(), start=box.start, changed=box.changed(), gave_way=bool(box.changed())),
            "plain": dict(other.snapshot(), start=other.before, changed=other.changed(), gave_way=bool(other.changed())),
            "live_sheet_hash": state.sheet_hash()}
