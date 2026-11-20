"""Routes of the TALK stream. GET /api/talk/threads is open; the POST routes are laptop only (app.py guards /api/talk/)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from signoff.store import sheetctx
from signoff.talk import guard, talk

router = APIRouter()


class Ask(BaseModel):
    store: str
    text: str
    product_id: str | None = None


@router.get("/api/talk/threads")
def threads(sheet: str | None = None):
    """The saved conversations of the active sheet (or `sheet`), oldest first, with the sharing rule in force."""
    sid = sheet or sheetctx.active_id()
    return {"sheet": sid, "rule": guard.rule(sheetctx.sheet(sid)), "threads": talk.threads(sid)}


@router.post("/api/talk/ask")
def ask(body: Ask):
    """The shopper's own words become the purpose of one conversation with one store's agent."""
    if not body.text.strip():
        raise HTTPException(422, "text is empty")
    try:
        return talk.ask(body.store, body.text.strip(), body.product_id, origin="shopper")
    except LookupError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/api/talk/run")
def run():
    """The agent's own questions: one conversation per picked product of the active sheet. Saved ones are not asked again."""
    from signoff.engine import state as engine
    sheet = sheetctx.sheet()
    out = [talk.ask(t["store"], t["purpose"], t["product_id"], sheet) for t in talk.plan(engine.get_state(), sheet)]
    return {"sheet": sheet["id"], "threads": [{"id": t["id"], "store": t["store"], "status": t["status"]} for t in out]}
