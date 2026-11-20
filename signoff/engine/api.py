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
    strike_line: str = "L3"
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
        key = box.strike(body.strike_line, body.product_key)
    except state.EngineError as error:
        return _refuse(error)
    session = uuid.uuid4().hex[:16]
    with _drill_lock:
        _drills[session] = {"box": box, "plain": plain.Sandbox(box), "history": [], "said": []}
        while len(_drills) > 300:  # oldest first
            _drills.pop(next(iter(_drills)))
    return {"session": session, "struck": {"line_id": body.strike_line, "product_key": key},
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
