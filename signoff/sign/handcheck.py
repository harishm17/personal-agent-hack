"""The hand-check sheet: 30 products across the stores, each shown as the store's own text, with three numbers
the builder reads off it (weight capacity, seat or added height, overall width; each a number or "not stated").
Saved to evals/handcheck.jsonl. It grades the figure reader, so the builder fills it in without seeing any
model output.

    uv run python -m signoff.sign.handcheck        # serves http://localhost:8004/handcheck/
or, on the main app, /handcheck/ (the SIGN router includes these routes).
"""
from __future__ import annotations

import json
import pathlib
import random
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ANSWERS = ROOT / "evals" / "handcheck.jsonl"
SAMPLE = ROOT / "evals" / "handcheck_sample.json"
PAGE = pathlib.Path(__file__).with_name("handcheck.html")
TOTAL = 30
FIELDS = ("weight_capacity", "height", "overall_width")
HEIGHT_KINDS = ("added_height", "seat_height", "none")
_lock = threading.Lock()
router = APIRouter()


def load_pool() -> tuple[list[dict], str]:
    files = sorted((ROOT / "data" / "pool").glob("*.json"))
    if files:
        pool = [p for f in files for p in json.loads(f.read_text())]
        if pool:
            return pool, "data/pool"
    return json.loads((ROOT / "fixtures" / "pool.json").read_text()), "fixtures/pool.json (placeholder products)"


def pick_sample(pool: list[dict], total: int = TOTAL, seed: int = 20261120) -> list[dict]:
    """Even share per store, spread over lines, each product once (same maker and model counts once)."""
    rng = random.Random(seed)
    by_store: dict[str, list[dict]] = {}
    for p in pool:
        if p.get("text"):
            by_store.setdefault(p["store"], []).append(p)
    stores = sorted(by_store)
    if not stores:
        return []
    quota = {s: total // len(stores) + (1 if i < total % len(stores) else 0) for i, s in enumerate(stores)}
    chosen, seen_keys = [], set()
    for s in stores:
        buckets: dict[str, list[dict]] = {}
        for p in by_store[s]:
            buckets.setdefault((p.get("line_ids") or ["?"])[0], []).append(p)
        for b in buckets.values():
            rng.shuffle(b)
        order = sorted(buckets)
        took = 0
        while took < quota[s] and any(buckets.values()):
            for line in order:
                while buckets[line] and buckets[line][0].get("product_key") in seen_keys:
                    buckets[line].pop(0)
                if buckets[line] and took < quota[s]:
                    p = buckets[line].pop(0)
                    seen_keys.add(p.get("product_key"))
                    chosen.append(p)
                    took += 1
    short = total - len(chosen)  # a store with few products: top up from the others
    if short > 0:
        rest = [p for p in pool if p.get("text") and p not in chosen and p.get("product_key") not in seen_keys]
        rng.shuffle(rest)
        chosen += rest[:short]
    return chosen[:total]


def _item(p: dict) -> dict:
    return {"id": "%s|%s" % (p["store"], p["product_id"]), "store": p["store"], "product_id": p["product_id"],
            "product_key": p.get("product_key"), "title": p.get("title"), "price_cents": p.get("price_cents"),
            "url": p.get("url"), "line_ids": p.get("line_ids"), "text": p.get("text", "")}


def sample(resample: bool = False) -> tuple[list[dict], str]:
    pool, source = load_pool()
    index = {"%s|%s" % (p["store"], p["product_id"]): p for p in pool}
    if not resample and SAMPLE.exists():
        try:
            ids = json.loads(SAMPLE.read_text())["ids"]
            if all(i in index for i in ids) and ids:
                return [_item(index[i]) for i in ids], source
        except (ValueError, KeyError):
            pass
    picked = pick_sample(pool)
    if source != "data/pool":  # placeholder products are never pinned as the sample
        return [_item(p) for p in picked], source
    SAMPLE.parent.mkdir(exist_ok=True)
    SAMPLE.write_text(json.dumps({"made_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": source,
                                  "ids": ["%s|%s" % (p["store"], p["product_id"]) for p in picked]}, indent=1))
    return [_item(p) for p in picked], source


def read_answers() -> dict[str, dict]:
    out = {}
    if ANSWERS.exists():
        for line in ANSWERS.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                out["%s|%s" % (row["store"], row["product_id"])] = row
    return out


def _number(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("a number or null")
    return float(value)


def save_answer(body: dict) -> dict:
    """One row per product. `null` means "not stated on the page"; a missing field is not saved (unfinished)."""
    row = {"store": body["store"], "product_id": body["product_id"], "product_key": body.get("product_key"),
           "title": body.get("title")}
    for f in FIELDS:
        if f not in body:
            raise ValueError("%s missing" % f)
        row[f] = _number(body[f])
    kind = body.get("height_kind", "none")
    if kind not in HEIGHT_KINDS:
        raise ValueError("height_kind")
    if row["height"] is not None and kind == "none":
        raise ValueError("say whether the height is added or seat height")
    row["height_kind"] = kind if row["height"] is not None else "none"
    row["checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock:
        answers = read_answers()
        answers["%s|%s" % (row["store"], row["product_id"])] = row
        ANSWERS.parent.mkdir(exist_ok=True)
        tmp = ANSWERS.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r) + "\n" for r in answers.values()))
        tmp.replace(ANSWERS)
    return row


@router.get("/handcheck")
def handcheck_redirect():
    return RedirectResponse("/handcheck/")


@router.get("/handcheck/")
def handcheck_page():
    return FileResponse(PAGE)


@router.get("/api/handcheck/items")
def items(resample: bool = False):
    products, source = sample(resample)
    return {"source": source, "total": len(products), "items": products, "answers": read_answers()}


@router.post("/api/handcheck/save")
async def save(request: Request):
    try:
        row = save_answer(await request.json())
    except (ValueError, KeyError, TypeError) as error:
        return JSONResponse({"ok": False, "error": str(error)}, status_code=400)
    return {"ok": True, "row": row, "done": len(read_answers())}


if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    print("hand-check sheet: http://localhost:8004/handcheck/")
    uvicorn.run(app, host="127.0.0.1", port=8004, log_level="warning")
