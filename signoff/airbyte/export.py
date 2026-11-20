"""Writes the files Airbyte syncs, into data/order/ (the "export" a source system would publish).

  pool.jsonl           one row per product of the active sheet's cached pool (data/pool/*.json for sheet1, data/<sheet>/pool/)
  store_answers.jsonl  one row per store answer of the active sheet
  order.csv            the issuer's order, one row per limit, from the active sheet's file (invented)

Run: uv run python -m signoff.airbyte.export
"""
import csv
import glob
import json
import pathlib

from signoff.store import sheetctx

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "order"
NOTE = "invented order: invented issuer and shopper, written from the sheet file"
ORDER_FIELDS = ["line_id", "need", "limit_id", "name", "op", "value", "unit", "bound_source", "bound_fact",
                "issuer", "issued_at", "order_note"]


def _dir(root: pathlib.Path, kind: str, sheet_id: str | None) -> pathlib.Path:
    """The active sheet's pool or store_answers folder under `root` (the one path rule: sheetctx)."""
    sid = sheet_id or sheetctx.active_id()
    return root / "data" / kind if sid == "sheet1" else root / "data" / sid / kind


def pool_rows(root: pathlib.Path = ROOT, sheet_id: str | None = None) -> list[dict]:
    rows = []
    for f in sorted(glob.glob(str(_dir(root, "pool", sheet_id) / "*.json"))):
        for p in json.load(open(f)):
            rows.append({"store": p["store"], "product_id": p["product_id"], "variant_id": p.get("variant_id"),
                         "title": p["title"], "price_cents": p["price_cents"], "url": p["url"], "text": p["text"],
                         "fetched_at": p["fetched_at"], "product_key": p.get("product_key"),
                         "line_ids": ",".join(p.get("line_ids") or [])})
    return rows


def answer_rows(root: pathlib.Path = ROOT, sheet_id: str | None = None) -> list[dict]:
    rows = []
    for f in sorted(glob.glob(str(_dir(root, "store_answers", sheet_id) / "*.json"))):
        for a in json.load(open(f)):
            d, r = a.get("delivery") or {}, a.get("returns") or {}
            rows.append({"store": a["store"], "asked_at": a.get("asked_at"), "question": a.get("question"),
                         "answer": a.get("answer"), "delivery_stated": d.get("stated"), "delivery_quote": d.get("quote"),
                         "days_low": d.get("days_low"), "days_high": d.get("days_high"),
                         "returnable": r.get("returnable"), "return_fee": r.get("fee"), "return_quote": r.get("quote")})
    return rows


def order_rows(sheet: dict) -> list[dict]:
    out = []
    for line in sheet["lines"]:
        for lim in line["limits"]:
            b = lim["bound"]
            out.append({"line_id": line["id"], "need": line["need"], "limit_id": lim["id"], "name": lim["name"],
                        "op": lim["op"], "value": b.get("value", "") if b["source"] == "issuer" else "",
                        "unit": lim["unit"], "bound_source": b["source"], "bound_fact": b.get("fact", ""),
                        "issuer": sheet["issuer"]["name"] + (", " + sheet["issuer"]["role_label"] if sheet["issuer"].get("role_label") else ""),
                        "issued_at": lim.get("set_at", ""), "order_note": NOTE})
    return out


def write_all(root: pathlib.Path = ROOT, out: pathlib.Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, rows in (("pool", pool_rows(root)), ("store_answers", answer_rows(root))):
        with (out / f"{name}.jsonl").open("w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        counts[name] = len(rows)
    orows = order_rows(json.loads((root / "sheets" / f"{sheetctx.active_id()}.json").read_text()))
    with (out / "order.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ORDER_FIELDS)
        w.writeheader()
        w.writerows(orows)
    counts["order"] = len(orows)
    return counts


if __name__ == "__main__":
    print(write_all())
