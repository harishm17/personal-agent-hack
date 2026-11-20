"""Ask a store's own agent a question; keep the reply verbatim and find the delivery and returns sentences in it."""
import datetime
import json
import pathlib
import re

from signoff.store import ucp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ANSWERS = ROOT / "data" / "store_answers"
QUESTION = ("If I order a shower chair today to a California address, how many days will delivery take? "
            "And can an opened bath seat be returned, and is there any fee?")

_DAYS = re.compile(r"(\d+)\s*(?:[–—-]|to)\s*(\d+)\s*(?:business\s+|working\s+)?days", re.I)
_ONE_DAY = re.compile(r"(?:within|in|about)\s+(\d+)\s*(?:business\s+|working\s+)?days", re.I)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|;\s*", text) if s.strip()]


def _clause(text: str, sent: str) -> str:
    """The sentence without its final punctuation: always a substring of the reply."""
    return sent.rstrip(".;! ")


def parse_reply(store: str, question: str, answer: str, asked_at: str) -> dict:
    delivery = {"stated": False, "quote": None, "days_low": None, "days_high": None}
    for sent in _sentences(answer):
        m = _DAYS.search(sent)
        if m and re.search(r"ship|deliver|arriv", sent, re.I):
            delivery = {"stated": True, "quote": sent[: m.end()].strip().rstrip(".;"),
                        "days_low": int(m.group(1)), "days_high": int(m.group(2))}
            break
    if not delivery["stated"]:
        for sent in _sentences(answer):
            m = _ONE_DAY.search(sent)
            if m and re.search(r"ship|deliver|arriv", sent, re.I):
                n = int(m.group(1))
                delivery = {"stated": True, "quote": sent[: m.end()].strip(), "days_low": n, "days_high": n}
                break
    assert delivery["quote"] is None or delivery["quote"] in answer

    returns = {"returnable": "unclear", "fee": None, "quote": None, "applies_to": "opened bath seats"}
    sents = _sentences(answer)
    ret = [s for s in sents if re.search(r"return|refund", s, re.I)]
    pick = next((s for s in ret if re.search(r"opened|bath seat", s, re.I)), ret[0] if ret else None)
    if pick:
        returns["quote"] = _clause(answer, pick)
        if re.search(r"may not qualify|isn.t specified|not specified|unclear|depends", pick, re.I):
            returns["returnable"] = "unclear"
        elif re.search(r"cannot be returned|can't be returned|not returnable|non-returnable|excluded from returns|no returns", pick, re.I):
            returns["returnable"] = "no"
        elif re.search(r"can be returned|may be returned|accepted|within \d+ days", pick, re.I):
            returns["returnable"] = "yes"
    fee = next((s for s in sents if re.search(r"restocking|return shipping|shipping cost", s, re.I)
                and not re.search(r"does not apply", s, re.I)), None)
    if fee:
        returns["fee"] = _clause(answer, fee)
    elif any(re.search(r"restocking fee is", s, re.I) for s in sents):
        returns["fee"] = None
    return {"store": store, "asked_at": asked_at, "question": question, "answer": answer,
            "delivery": delivery, "returns": returns}


def ask(store: str, query: str = QUESTION) -> dict:
    """One real ask_business call; the reply is kept verbatim in `answer`."""
    r = ucp.ask_business(store, query)
    answer = ((r.get("answer") or {}).get("plain")) or json.dumps(r.get("answer"))
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    return parse_reply(store, query, answer, now)


def refresh(stores: list[str]) -> list[dict]:
    ANSWERS.mkdir(parents=True, exist_ok=True)
    out = []
    for s in stores:
        rec = ask(s)
        (ANSWERS / f"{s}.json").write_text(json.dumps([rec], indent=1, ensure_ascii=False))
        out.append(rec)
    return out


if __name__ == "__main__":
    sheet = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
    for rec in refresh(sheet["stores"]):
        print(json.dumps({k: rec[k] for k in ("store", "delivery", "returns")}, ensure_ascii=False))
