"""ENGINE routes. No route here changes a limit, a strike or the seal: those go through signoff.sign."""
import asyncio
import json

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
