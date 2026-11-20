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
    sh = sheetctx.sheet(sid)
    turns = [turn for t in talk.threads(sid) for turn in t["turns"]]
    count = {"messages": len(turns), "not_sent": sum(1 for x in turns if not x["sent"]),
             "over_cautious": sum(1 for x in turns if not x["sent"] and (x.get("review") or {}).get("verdict") == "over-cautious")}
    return {"count": count, "shopper": (sh.get("shopper") or {}).get("name"), "sheet": sid, "title": sh.get("title"), "rule": guard.rule(sh), "marks": guard.MARK, "threads": talk.threads(sid),
            "messages": talk.messages(sh)}


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
