"""Ask a store's own agent a question; keep the reply verbatim and find the delivery and returns sentences in it."""
import datetime
import json
import pathlib
import re

from signoff.store import ucp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ANSWERS = ROOT / "data" / "store_answers"
def question_for(need: str) -> str:
    """The delivery and returns question for a line's `need`, the same wording for every sheet."""
    plural = need.endswith("s") and not need.endswith("ss")
    order = need if plural else ("an " if need[:1].lower() in "aeiou" else "a ") + need
    opened = "opened " + need if plural else "an opened " + need
    return ("If I order %s today to a California address, how many days will delivery take? "
            "And can %s be returned, and is there any fee?" % (order, opened))


QUESTION = question_for("shower chair")  # sheet 1's first line; kept for callers that still import it

_DAYS = re.compile(r"(\d+)\s*(?:[–—-]|to)\s*(\d+)\s*(?:business\s+|working\s+)?days", re.I)
_ONE_DAY = re.compile(r"(?:within|in|about)\s+(\d+)\s*(?:business\s+|working\s+)?days", re.I)


def _sentences(text: str) -> list[str]:
    """Sentences: a full stop ends one only when a capital letter follows ("U.S. order" does not end it, "U.S. Opened" does); a semicolon ends a clause."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])|;\s*", text) if s.strip()]


def _clause(text: str, sent: str) -> str:
    """The sentence without its final punctuation: always a substring of the reply."""
    return sent.rstrip(".;! ")


_NOT_SAID = re.compile(r"\b(?:does|do|did|is|are)(?: not|n.t)\s+(?:specif|state|say|mention|clear|provid|list|address|cover)|"
                       r"\bnot (?:specified|stated|clear|mentioned|provided)|unclear|no information|cannot tell|can.t tell", re.I)
_DENIED = re.compile(r"cannot be returned|can.t be returned|not (?:be )?returnable|non-returnable|not eligible|excluded from returns|"
                     r"no returns|final sale|not accepted|(?:will not|won.t|do not|don.t|does not|doesn.t) accept|unable to be returned", re.I)
_ABOUT_OPENED = re.compile(r"opened|unboxed|\bused\b", re.I)
_HEDGED = re.compile(r"\bmay\b|\bmight\b|\bcould\b|generally|typically|usually|depends|only if|\bif\b|\bmust\b|unused|unopened|"
                     r"original packaging|resalable|provided|unless|conditions?\b|would not meet|not meet", re.I)
_AFFIRMED = re.compile(r"can be returned|is returnable|are returnable|accepts? returns?|returns? (?:are |is )?accepted|"
                       r"eligible for (?:a )?(?:return|refund)|will accept", re.I)


def returnable_from(sentence: str) -> str:
    """'yes' only when the sentence itself affirms the return of an opened item, with no condition an opened item could fail;
    'no' when it denies; anything else, including a store saying it does not say, is 'unclear'. No phrase list of answers:
    four checks in a fixed order (does not say, denial, hedge or condition, affirmation)."""
    if _NOT_SAID.search(sentence):
        return "unclear"
    if _DENIED.search(sentence):
        return "no"
    if _HEDGED.search(sentence):
        return "unclear"
    # a plain "returns are accepted" says nothing about an opened item: yes needs the sentence to be about the opened item
    return "yes" if _AFFIRMED.search(sentence) and _ABOUT_OPENED.search(sentence) else "unclear"


def parse_reply(store: str, question: str, answer: str, asked_at: str) -> dict:
    delivery = {"stated": False, "quote": None, "days_low": None, "days_high": None}
    for sent in _sentences(answer):
        m = _DAYS.search(sent)
        if m and re.search(r"ship|deliver|arriv", sent, re.I) and not re.search(r"return|refund|exchange", sent, re.I):
            delivery = {"stated": True, "quote": sent[: m.end()].strip().rstrip(".;"),
                        "days_low": int(m.group(1)), "days_high": int(m.group(2))}
            break
    if not delivery["stated"]:
        for sent in _sentences(answer):
            m = _ONE_DAY.search(sent)
            if m and re.search(r"ship|deliver|arriv", sent, re.I) and not re.search(r"return|refund|exchange", sent, re.I):
                n = int(m.group(1))
                delivery = {"stated": True, "quote": sent[: m.end()].strip(), "days_low": n, "days_high": n}
                break
    assert delivery["quote"] is None or delivery["quote"] in answer

    m = re.search(r"\b(opened [a-z][a-z -]*?)(?: be returned|\?|,)", question, re.I)
    returns = {"returnable": "unclear", "fee": None, "quote": None, "applies_to": m.group(1) if m else "opened item"}
    sents = _sentences(answer)
    ret = [s for s in sents if re.search(r"return|refund", s, re.I)]
    opened = next((s for s in sents if re.search(r"opened|unboxed|\bused\b", s, re.I)), None)
    pick = opened or (ret[0] if ret else None)
    if pick:
        returns["quote"] = _clause(answer, pick)
        returns["returnable"] = returnable_from(pick)
    fee = next((s for s in sents if re.search(r"restocking|return shipping|shipping cost", s, re.I)
                and not re.search(r"does not apply", s, re.I)), None)
    if fee:
        returns["fee"] = _clause(answer, fee)
    elif any(re.search(r"restocking fee is", s, re.I) for s in sents):
        returns["fee"] = None
    return {"store": store, "asked_at": asked_at, "question": question, "answer": answer,
            "delivery": delivery, "returns": returns}


def _need_for(store: str, sheet_id: str | None = None) -> str:
    """The `need` of the first line the store has products for in the active sheet (the sheet's own words)."""
    from signoff.store import sheetctx
    sheet_id = sheet_id or sheetctx.active_id()
    sheet = json.loads((ROOT / "sheets" / f"{sheet_id}.json").read_text())
    f = sheetctx.pool_dir(sheet_id) / f"{store}.json"
    lines = sorted({lid for r in (json.loads(f.read_text()) if f.exists() else []) for lid in r["line_ids"]})
    needs = {l["id"]: l["need"] for l in sheet["lines"]}
    if lines:
        return needs[lines[0]]
    try:  # nothing kept for the store: the line it returned the most candidates for (pool_summary.json)
        summ = json.loads((sheetctx.pool_dir(sheet_id).parent / "pool_summary.json").read_text())["stores"][store]
        best = max(summ, key=lambda lid: summ[lid]["candidates"])
        if summ[best]["candidates"]:
            return needs[best]
    except Exception:  # noqa: BLE001
        pass
    return sheet["lines"][0]["need"]


def ask(store: str, query: str | None = None) -> dict:
    """One real ask_business call; the reply is kept verbatim in `answer`. Without a query: the delivery and returns question
    for the first line the store has products for in the active sheet."""
    from signoff.store import sheetctx
    query = query or question_for(_need_for(store))
    r = ucp.ask_business(store, query)
    answer = ((r.get("answer") or {}).get("plain")) or json.dumps(r.get("answer"))
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    rec = parse_reply(store, query, answer, now)
    if r.get("mode") == "replay":
        rec["mode"] = "replay"
        for d in [sheetctx.answers_dir(), *sheetctx.all_answer_dirs()]:
            saved = d / f"{store}.json"
            if saved.exists():  # the saved record keeps its own question and time
                old = json.loads(saved.read_text())
                old = old[0] if isinstance(old, list) else old
                rec.update(question=old.get("question", query), asked_at=old.get("asked_at", now))
                break
    return rec


def refresh(stores: list[str] | None = None, sheet_id: str | None = None) -> list[dict]:
    """One delivery and returns question to each store's agent about the first line it has products for; saved verbatim in the
    active sheet's store_answers folder."""
    from signoff.store import sheetctx
    sheet_id = sheet_id or sheetctx.active_id()
    sheet = json.loads((ROOT / "sheets" / f"{sheet_id}.json").read_text())
    pool_dir, ans_dir = sheetctx.pool_dir(sheet_id), sheetctx.answers_dir(sheet_id)
    ans_dir.mkdir(parents=True, exist_ok=True)
    needs = {l["id"]: l["need"] for l in sheet["lines"]}
    out = []
    for s in stores or sheet["stores"]:
        rec = ask(s, question_for(_need_for(s, sheet_id)))
        (ans_dir / f"{s}.json").write_text(json.dumps([rec], indent=1, ensure_ascii=False))
        out.append(rec)
    return out


if __name__ == "__main__":
    for rec in refresh():
        print(json.dumps({k: rec[k] for k in ("store", "delivery", "returns")}, ensure_ascii=False))
