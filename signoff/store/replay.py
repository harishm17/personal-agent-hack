"""Replay mode (SIGNOFF_MODE=replay): every store call is answered from files in data/, with no network."""
import datetime
import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "pool" / "raw"
ANSWERS = ROOT / "data" / "store_answers"


def raw_path(store: str, query: str, raw_dir: pathlib.Path = RAW) -> pathlib.Path:
    return raw_dir / store / (re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_") + ".json")


def _pool_rows() -> list:
    from signoff.store import sheetctx
    out: list = []
    for d in sheetctx.all_pool_dirs():
        for f in sorted(d.glob("*.json")):
            out.extend(json.loads(f.read_text()))
    return out


def search_catalog(store: str, query: str) -> dict:
    p = raw_path(store, query)
    if not p.exists():
        for d in [*(ROOT / "data").glob("*/pool/raw"), *(ROOT / "data").glob("*/*/pool/raw")]:  # sheet 2 raw replies
            if raw_path(store, query, d).exists():
                p = raw_path(store, query, d)
                break
    if not p.exists():
        return {"products": [], "messages": [{"type": "info", "text": "replay: no saved reply for this query"}],
                "mode": "replay"}
    return {**json.loads(p.read_text()), "mode": "replay"}


def ask_business(store: str, query: str) -> dict:
    from signoff.store import sheetctx
    for d in sheetctx.all_answer_dirs():  # a question asked before (signoff.store.asked) is answered with its saved reply
        cached = d / "asked" / f"{store}.json"
        if cached.exists():
            hit = next((r for r in json.loads(cached.read_text()) if r["question"] == query), None)
            if hit:
                return {"answer": {"plain": hit["reply"]}, "mode": "replay", "saved_question": hit["question"]}
    found = [d / f"{store}.json" for d in sheetctx.all_answer_dirs() if (d / f"{store}.json").exists()]
    if not found:
        raise RuntimeError(f"replay: no saved answer for {store}")
    rec = json.loads(found[0].read_text())
    rec = rec[0] if isinstance(rec, list) else rec
    return {"answer": {"plain": rec["answer"]}, "mode": "replay", "saved_question": rec.get("question")}


def create_cart(store: str, items: list[tuple[str, int]]) -> dict:
    """No cart is created at the store: the continue_url is the first product's page, the id is derived and labelled."""
    rows = {r["variant_id"]: r for r in _pool_rows() if r["store"] == store}
    missing = [v for v, _ in items if v not in rows]
    if missing:
        raise RuntimeError("replay: variant not in the saved pool")
    cid = "replay-" + hashlib.sha256(f"{store}|{sorted(items)}".encode()).hexdigest()[:16]
    total = sum(rows[v]["price_cents"] * q for v, q in items)
    return {"id": cid, "currency": "USD", "mode": "replay",
            "totals": [{"type": "subtotal", "amount": total}, {"type": "total", "amount": total}],
            "continue_url": rows[items[0][0]]["url"],
            "created_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
