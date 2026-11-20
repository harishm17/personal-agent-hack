"""Writes the files Airbyte syncs for one sheet, into data/order/<sheet_id>/ (the "export" a source system would publish).

  pool.jsonl           one row per product of the sheet's stores (the cached pool)
  store_answers.jsonl  one row per store answer
  order.csv            the issuer's limits, one row per limit, from the sheet (invented)
  order_doc.jsonl      the order document (the text the issuer wrote), when the sheet names one

Where a sheet's files live is STORE's rule, `signoff.store.sheetctx` (see `_dir`). Run: uv run python -m signoff.airbyte.export [sheet_id]
"""
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "order"
NOTE = "invented order: invented issuer and household, written from the sheet"
ORDER_FIELDS = ["sheet_id", "line_id", "need", "limit_id", "name", "op", "value", "unit", "bound_source", "bound_fact",
                "issuer", "issued_at", "order_note"]


def active_sheet() -> str:
    """The sheet the app is running; never raises."""
    from signoff.store import sheetctx
    return sheetctx.active_id()


def load_sheet(sheet_id: str, root: pathlib.Path = ROOT) -> dict:
    return json.loads((root / "sheets" / f"{sheet_id}.json").read_text())


def _dir(kind: str, sheet_id: str) -> pathlib.Path:
    """STORE's one path rule (signoff.store.sheetctx): sheet1 keeps data/pool and data/store_answers, any other
    sheet keeps data/<sheet id>/pool and data/<sheet id>/store_answers. `kind` is "pool" or "store_answers"."""
    from signoff.store import sheetctx
    return sheetctx.pool_dir(sheet_id) if kind == "pool" else sheetctx.answers_dir(sheet_id)


def pool_rows(sheet: dict) -> list[dict]:
    d = _dir("pool", sheet["id"])
    rows = []
    for store in sheet["stores"]:
        f = d / f"{store}.json" if d else None
        if not f or not f.exists():
            continue
        for p in json.load(open(f)):
            rows.append({"sheet_id": sheet["id"], "store": p["store"], "product_id": p["product_id"],
                         "variant_id": p.get("variant_id"), "title": p["title"], "price_cents": p["price_cents"],
                         "url": p["url"], "text": p["text"], "fetched_at": p["fetched_at"],
                         "product_key": p.get("product_key"), "line_ids": ",".join(p.get("line_ids") or [])})
    return rows


def answer_rows(sheet: dict) -> list[dict]:
    d = _dir("store_answers", sheet["id"])
    rows = []
    for store in sheet["stores"]:
        f = d / f"{store}.json" if d else None
        if not f or not f.exists():
            continue
        for a in json.load(open(f)):
            dl, r = a.get("delivery") or {}, a.get("returns") or {}
            rows.append({"sheet_id": sheet["id"], "store": a["store"], "asked_at": a.get("asked_at"),
                         "question": a.get("question"), "answer": a.get("answer"), "delivery_stated": dl.get("stated"),
                         "delivery_quote": dl.get("quote"), "days_low": dl.get("days_low"),
                         "days_high": dl.get("days_high"), "returnable": r.get("returnable"),
                         "return_fee": r.get("fee"), "return_quote": r.get("quote")})
    return rows


def order_rows(sheet: dict) -> list[dict]:
    out = []
    for line in sheet["lines"]:
        for lim in line["limits"]:
            b = lim["bound"]
            out.append({"sheet_id": sheet["id"], "line_id": line["id"], "need": line["need"], "limit_id": lim["id"],
                        "name": lim["name"], "op": lim["op"],
                        "value": b.get("value", "") if b["source"] == "issuer" else "", "unit": lim["unit"],
                        "bound_source": b["source"], "bound_fact": b.get("fact", ""),
                        "issuer": sheet["issuer"]["name"] + ", " + sheet["issuer"]["role_label"],
                        "issued_at": lim["set_at"], "order_note": NOTE})
    return out


def order_doc_rows(sheet: dict, root: pathlib.Path = ROOT) -> list[dict]:
    name = sheet.get("order_doc")
    f = root / name if name else None
    if not f or not f.exists():
        return []
    return [{"sheet_id": sheet["id"], "name": name, "text": f.read_text()}]


def write_all(sheet_id: str = "sheet1", root: pathlib.Path = ROOT, out: pathlib.Path = OUT) -> dict:
    """Writes the sheet's files; returns row counts by `count_key`."""
    sheet = load_sheet(sheet_id, root)
    d = out / sheet_id
    d.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, rows in (("pool", pool_rows(sheet)), ("store_answers", answer_rows(sheet)),
                       ("order_doc", order_doc_rows(sheet, root))):
        with (d / f"{name}.jsonl").open("w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        counts[name] = len(rows)
    orows = order_rows(sheet)
    with (d / "order.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ORDER_FIELDS)
        w.writeheader()
        w.writerows(orows)
    counts["order"] = len(orows)
    return counts


if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else "sheet1"
    print(sid, write_all(sid))
