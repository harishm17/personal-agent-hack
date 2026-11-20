"""Ask, don't tell: questions to a store's own agent about one product, built by a code template from the product title
and the figure name only. A question never carries a limit, a shopper measurement, a person or a reason.

Replies are cached verbatim in data/store_answers/asked/<store>.json, a list of
{store, product_id, figure, question, reply, asked_at, ...}. The same question is never asked twice, and in replay mode
(SIGNOFF_MODE=replay) nothing is asked: the cache answers. This module does not parse figures; ENGINE reads the replies.
"""
import datetime
import html
import json
import pathlib
import re
import threading
import time

from signoff import config
from signoff.store import sheetctx, ucp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CACHE = None  # None: the active sheet's folder (sheetctx.asked_dir); tests may set a folder
SPACING_SECONDS = 0.8
_lock = threading.Lock()

FIGURE_WORDS = {"weight_capacity": "weight capacity", "added_height": "added height", "seat_height": "seat height",
                "overall_width": "overall width", "length": "length", "mattress_thickness_max": "maximum mattress thickness",
                "rough_in": "rough-in", "flush_volume": "flush volume", "flow_rate": "water flow rate"}
UNIT_WORDS = {"lb": "pounds", "in": "inches", "gpf": "gallons per flush", "gpm": "gallons per minute"}


def _cache_dir() -> pathlib.Path:
    return CACHE if CACHE is not None else sheetctx.asked_dir()
RETURNS_FIGURE = "returns_and_delivery"


def clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"&(trade|reg);", "", title or ""))).strip()


def figure_question(title: str, figure: str, unit: str) -> str:
    return f"What does {clean_title(title)} state for its {FIGURE_WORDS.get(figure, figure.replace('_', ' '))}, in {UNIT_WORDS.get(unit, unit)}?"


def returns_question(title: str) -> str:
    return f"Can an opened {clean_title(title)} be returned, and how many business days does standard delivery take?"


def sheet_values(sheet: dict) -> set[float]:
    """Every number the sheet keeps private: issuers' limit values and the shopper's measurements."""
    vals = {float(f["value"]) for f in sheet.get("shopper_facts", [])}
    for line in sheet["lines"]:
        for lim in line["limits"]:
            if lim["bound"].get("source") == "issuer":
                vals.add(float(lim["bound"]["value"]))
    return vals


def leaks(question: str, sheet: dict, title: str | None = None) -> list[float]:
    """The sheet values that appear as a number in `question` (empty list = clean). The product's own title is the store's
    words, not ours, so it is left out of the check (a page named "10-Inch Rough-In" tells the store nothing new)."""
    if title:
        question = question.replace(clean_title(title), "")
    found = []
    for tok in re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])", question):
        if float(tok) in sheet_values(sheet):
            found.append(float(tok))
    return found


def plan(state: dict, sheet: dict, per_line_not_stated: int = 3) -> list[dict]:
    """Targets per line: the pick and the runner-up (returns and delivery), and up to three not_stated candidates whose one
    missing figure is the only thing keeping them out (one question per missing figure). Titles that contain a number equal
    to a sheet value are skipped, so no question can repeat a limit or a measurement."""
    out = []
    for line in state["lines"]:
        local = next((l for l in sheet["lines"] if l["id"] == line["line_id"]), {}).get("fulfilment") == "pick_up_locally"
        cands = line["candidates"]
        need_delivery = "delivery" in (sheet.get("pick_rule") or {}).get("id", "delivery")  # sheet 2's rule is plain "cheapest"
        eligible = sorted((c for c in cands if c["status"] == "inside"
                           and (local or not need_delivery or c["arrival"]["status"] == "stated")),
                          key=lambda c: (c["product"]["price_cents"], c["id"]))
        targets = []
        for role, c in zip(("pick", "runner_up"), eligible[:2]):
            targets.append((role, c, [(RETURNS_FIGURE, None)]))
        sole = []
        for c in cands:
            if c["status"] != "not_stated":
                continue
            bad = [k for k in c["checks"] if k["state"] != "pass"]
            if len(bad) == 1 and bad[0]["state"] == "not_stated":
                lim = next(l for l in sheet["lines"] if l["id"] == line["line_id"])["limits"]
                unit = next((l["unit"] for l in lim if l["id"] == bad[0]["limit_id"]), "")
                sole.append(("not_stated", c, [(bad[0]["missing_figure"], unit)]))
        sole.sort(key=lambda t: (t[1]["product"]["price_cents"], t[1]["id"]))
        targets += sole[:per_line_not_stated]
        for role, c, items in targets:
            for figure, unit in items:
                p = c["product"]
                q = returns_question(p["title"]) if figure == RETURNS_FIGURE else figure_question(p["title"], figure, unit or "")
                if leaks(q, sheet, p["title"]):
                    out.append({"skipped": "the question template contains a sheet value", "store": p["store"], "product_id": p["product_id"],
                                "line_id": line["line_id"], "role": role, "title": p["title"]})
                    continue
                out.append({"line_id": line["line_id"], "role": role, "store": p["store"], "product_id": p["product_id"],
                            "variant_id": p.get("variant_id"), "title": clean_title(p["title"]), "figure": figure,
                            "question": q})
    return out


def _file(store: str) -> pathlib.Path:
    return _cache_dir() / f"{store}.json"


def load(store: str | None = None) -> list[dict]:
    files = [_file(store)] if store else sorted(_cache_dir().glob("*.json"))
    out: list = []
    for f in files:
        if f.exists():
            out.extend(json.loads(f.read_text()))
    return out


def cached(store: str, product_id: str, question: str) -> dict | None:
    return next((r for r in load(store) if r["product_id"] == product_id and r["question"] == question), None)


def _save(rec: dict) -> None:
    with _lock:
        _cache_dir().mkdir(parents=True, exist_ok=True)
        rows = load(rec["store"])
        rows.append(rec)
        _file(rec["store"]).write_text(json.dumps(rows, indent=1, ensure_ascii=False))


def ask_one(target: dict) -> dict | None:
    """Return the cached record, or ask once (live mode only) and cache the reply verbatim. None if it could not be asked."""
    hit = cached(target["store"], target["product_id"], target["question"])
    if hit or config.mode() == "replay":
        return hit
    r = ucp.ask_business(target["store"], target["question"], mask=[clean_title(target["title"])])
    reply = (r.get("answer") or {}).get("plain")
    if not reply:
        return None
    rec = {"store": target["store"], "product_id": target["product_id"], "figure": target["figure"],
           "question": target["question"], "reply": reply,
           "asked_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "variant_id": target.get("variant_id"), "title": target["title"], "line_id": target["line_id"],
           "role": target["role"]}
    _save(rec)
    return rec


def run(lines: list[str] | None = None, dry: bool = False) -> dict:
    """Plan from the engine's current state and ask what is not cached yet, one call at a time, spaced out."""
    from signoff.engine import state as engine
    sheet = sheetctx.sheet()
    st = engine.get_state()
    targets = [t for t in plan(st, sheet) if not lines or t["line_id"] in lines]
    asked = skipped = failed = cached_n = 0
    for t in targets:
        if "skipped" in t:
            skipped += 1
            continue
        if cached(t["store"], t["product_id"], t["question"]):
            cached_n += 1
            continue
        if dry:
            continue
        try:
            if ask_one(t):
                asked += 1
            else:
                failed += 1
        except Exception:  # noqa: BLE001
            failed += 1
        time.sleep(SPACING_SECONDS)
    return {"planned": len(targets), "asked": asked, "cached": cached_n, "skipped": skipped, "failed": failed}


if __name__ == "__main__":
    import sys
    only = [a for a in sys.argv[1:] if a.startswith("L")] or None
    print(run(only, dry="--dry" in sys.argv))
