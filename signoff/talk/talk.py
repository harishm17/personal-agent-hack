"""One conversation with a store's own agent: a model writes our message, the guard decides what leaves, the store's
real agent answers (`ask_business`, single turn), a model marks the answering words, and one follow-up may be sent.

Every thread is saved under data/talk/threads/<sheet>/<id>.json: the purpose, and for each turn the draft, what the
guard removed and by which rule, the text sent, the reply. The same purpose is never run twice and the same message
is never sent twice to a store: the saved exchange answers. In replay mode nothing is asked; the cache answers.
A reply is text to quote. It is never executed, and nothing here writes engine state.
"""
import datetime
import hashlib
import json
import pathlib
import re
import threading
import time

from signoff import config, obs
from signoff.store import sheetctx, ucp
from signoff.talk import guard, writer

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DIR = ROOT / "data" / "talk" / "threads"
SPACING_SECONDS = 3.0
_lock = threading.Lock()
_last_call = [0.0]


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def thread_id(sheet_id: str, store: str, product_id: str | None, purpose: str) -> str:
    return hashlib.sha256("|".join([sheet_id, store, product_id or "", _norm(purpose)]).encode()).hexdigest()[:12]


def _path(sheet_id: str, tid: str) -> pathlib.Path:
    return DIR / sheet_id / (tid + ".json")


def threads(sheet_id: str | None = None) -> list:
    """Saved threads of one sheet (None: every sheet), oldest first."""
    files = sorted(DIR.glob((sheet_id or "*") + "/*.json"))
    return sorted((json.loads(f.read_text()) for f in files), key=lambda t: t["asked_at"])


def _save(thread: dict) -> None:
    with _lock:
        p = _path(thread["sheet"], thread["id"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(thread, indent=1, ensure_ascii=False))


def exchange(store: str, sent: str) -> dict | None:
    """A saved turn in which this exact message went to this store and was answered."""
    for t in threads():
        if t["store"] == store:
            for turn in t["turns"]:
                if turn.get("sent") and _norm(turn["sent"]) == _norm(sent) and turn.get("reply"):
                    return turn
    return None


def product(store: str, product_id: str | None, sheet_id: str) -> dict | None:
    """The product's saved record (the store's own title), from the sheet's pool."""
    if not product_id:
        return None
    f = sheetctx.pool_dir(sheet_id) / (store + ".json")
    rows = json.loads(f.read_text()) if f.exists() else []
    hit = next((r for r in rows if r["product_id"] == product_id), None)
    if hit is None:
        raise LookupError("no such product in the saved pool of %s: %s" % (store, product_id))
    return {"product_id": product_id, "title": re.sub(r"\s+", " ", hit["title"]).strip(), "url": hit.get("url")}


def store_send(store: str, text: str, mask: list) -> dict:
    """The real call, through the project's client (agent profile, outbound ledger, its own sealed-value stop)."""
    with _lock:
        wait = SPACING_SECONDS - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
    r = ucp.ask_business(store, text, mask=mask)
    return {"reply": ucp.plain((r.get("answer") or {}).get("plain") or ""), "reply_at": _now()}


def _decide(text: str, sheet: dict, prod: dict | None, finder, rewrite) -> dict:
    """The guard on one outbound message. Clean: it leaves as written. Otherwise the sealed spans are cut, the message
    is rewritten once without them and checked again; if it still carries a sealed span it does not leave."""
    turn = {"draft": text, "removed": guard.check(text, sheet, prod, finder), "cut": None, "rewritten": None,
            "still": [], "sent": None}
    if not turn["removed"]:
        turn.update(decision="sent", sent=text)
        return turn
    turn["cut"] = guard.cut(text, turn["removed"])
    if not re.search(r"\w", turn["cut"].replace(guard.GAP, "")):
        turn.update(decision="refused", why="nothing is left after the sealed parts are removed")
        return turn
    turn["rewritten"] = rewrite(turn["cut"])
    turn["still"] = guard.check(turn["rewritten"], sheet, prod, finder)
    if turn["still"]:
        turn.update(decision="refused", why="the rewritten message still carries a sealed part")
    else:
        turn.update(decision="rewritten", sent=turn["rewritten"])
    return turn


def _ledger(store: str, turn: dict, prod: dict | None) -> None:
    """One ledger row per guard decision. A refused message is recorded with its draft, marked blocked; the row of a
    message that left is written by the store client when it sends."""
    kinds = sorted({s["kind"] for s in turn["removed"]})
    if turn["decision"] == "refused":
        row = obs.egress(store, "talk guard: refused, not sent (%s)" % ", ".join(kinds), turn["draft"], ("product",),
                         kind="store", block_on_hit=True, mask=[prod["title"]] if prod else None)
        turn["ledger"] = {"n": row.get("n"), "blocked": True}
    elif kinds:
        row = obs.egress(store, "talk guard: withheld %d (%s), rewritten" % (len(turn["removed"]), ", ".join(kinds)),
                         turn["sent"], ("product",), kind="store", mask=[prod["title"]] if prod else None)
        turn["ledger"] = {"n": row.get("n"), "withheld": kinds}


def _turn(n: int, text: str, questions: list, thread: dict, sheet: dict, prod: dict | None, deps: dict) -> dict:
    turn = {"n": n, "questions": questions, **_decide(text, sheet, prod, deps["finder"], deps["rewrite"])}
    _ledger(thread["store"], turn, prod)
    if turn["sent"]:
        saved = exchange(thread["store"], turn["sent"])
        got = {"reply": saved["reply"], "reply_at": saved["reply_at"], "asked_before": True} if saved else \
            deps["send"](thread["store"], turn["sent"], [prod["title"]] if prod else [])
        turn.update(got)
        turn["answers"] = deps["read"](questions, turn["reply"])
    thread["turns"].append(turn)
    return turn


def ask(store: str, purpose: str, product_id: str | None = None, sheet: dict | None = None, origin: str = "agent",
        finder=guard.sie_finder, send=store_send, draft=writer.draft, rewrite=writer.rewrite, read=writer.read,
        follow_up=writer.follow_up) -> dict:
    """Run one purpose with one store's agent and return the saved thread. `origin`: "agent" (the agent's own
    question about a pick) or "shopper" (the shopper's own words)."""
    sheet = sheet or sheetctx.sheet()
    if store not in sheet.get("stores", []):
        raise LookupError("not a store of this sheet: " + store)
    tid = thread_id(sheet["id"], store, product_id, purpose)
    if _path(sheet["id"], tid).exists():
        return {**json.loads(_path(sheet["id"], tid).read_text()), "from_cache": True}
    if config.mode() == "replay":
        return {"id": tid, "sheet": sheet["id"], "store": store, "product_id": product_id, "purpose": purpose,
                "origin": origin, "turns": [], "status": "not_saved", "mode": "replay",
                "why": "replay mode asks nothing and this was never asked"}
    prod = product(store, product_id, sheet["id"])
    deps = {"finder": finder, "send": send, "rewrite": rewrite, "read": read}
    may = guard.allowed(sheet)  # the writer is told only what this recipient may receive
    known = {"product": prod["title"] if prod and "product" in may else None,
             "needed by": guard.need_by_text(sheet) if "need_by" in may else None,
             "delivery region": sheet.get("delivery_region") if "delivery_region" in may else None}
    thread = {"id": tid, "sheet": sheet["id"], "store": store, "product_id": product_id, "title": prod and prod["title"],
              "origin": origin, "purpose": purpose, "asked_at": _now(), "mode": config.mode(),
              "rule": guard.rule(sheet), "writer": writer.NAME, "span_model": "sie:" + guard.SPAN_MODEL,
              "turns": [], "status": None}
    try:
        first = draft(purpose, known)
        turn = _turn(1, first["message"], first["questions"], thread, sheet, prod, deps)
        if turn["sent"]:
            answered = {a["question"] for a in turn["answers"]}
            still_open = [q for q in first["questions"] if q not in answered]
            if still_open:  # one follow-up; each call is single turn, so it carries the short thread
                text = 'Earlier I asked: "%s" %s' % (turn["sent"], follow_up(turn["sent"], turn["reply"], still_open))
                turn = _turn(2, text, still_open, thread, sheet, prod, deps)
                answered |= {a["question"] for a in turn.get("answers", [])}
            thread["open"] = [q for q in first["questions"] if q not in answered]
        sent = [t for t in thread["turns"] if t["sent"]]
        thread["status"] = "refused" if not sent else "answered" if not thread.get("open") else "open"
    except Exception as e:  # noqa: BLE001  a failed call is shown on the thread, never hidden
        thread.update(status="error", error=(type(e).__name__ + ": " + str(e))[:300])
    _save(thread)
    return thread


def purpose_for(need: str, sheet: dict) -> str:
    """The agent's own purpose for a picked product: returns of an opened item, and arrival by the need-by date."""
    return "Find out whether this %s can be returned once opened, and whether it will arrive by the date it is needed." % need


def plan(state: dict, sheet: dict) -> list:
    """One target per line: the picked product and its store."""
    out = []
    for line in state.get("lines", []):
        need = next((l["need"] for l in sheet["lines"] if l["id"] == line.get("line_id")), None)
        for c in line.get("candidates", []):
            if c.get("picked") and need:
                out.append({"store": c["product"]["store"], "product_id": c["product"]["product_id"],
                            "purpose": purpose_for(need, sheet)})
    return out
