"""Writes the files Airbyte syncs, into data/order/ (the "export" a source system would publish).

  pool.jsonl           one row per product of the three stores' cached pool (data/pool/*.json)
  store_answers.jsonl  one row per store answer (data/store_answers/*.json)
  order.csv            the therapist's order, one row per limit, from sheets/sheet1.json (invented)

Run: uv run python -m signoff.airbyte.export
"""
import csv
import glob
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "order"
NOTE = "invented order: invented therapist and family, written from sheets/sheet1.json"
ORDER_FIELDS = ["line_id", "need", "limit_id", "name", "op", "value", "unit", "bound_source", "bound_fact",
                "issuer", "issued_at", "order_note"]


def pool_rows(root: pathlib.Path = ROOT) -> list[dict]:
    rows = []
    for f in sorted(glob.glob(str(root / "data" / "pool" / "*.json"))):
        for p in json.load(open(f)):
            rows.append({"store": p["store"], "product_id": p["product_id"], "variant_id": p.get("variant_id"),
                         "title": p["title"], "price_cents": p["price_cents"], "url": p["url"], "text": p["text"],
                         "fetched_at": p["fetched_at"], "product_key": p.get("product_key"),
                         "line_ids": ",".join(p.get("line_ids") or [])})
    return rows


def answer_rows(root: pathlib.Path = ROOT) -> list[dict]:
    rows = []
    for f in sorted(glob.glob(str(root / "data" / "store_answers" / "*.json"))):
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
                        "issuer": sheet["issuer"]["name"] + ", " + sheet["issuer"]["role_label"],
                        "issued_at": lim["set_at"], "order_note": NOTE})
    return out


def write_all(root: pathlib.Path = ROOT, out: pathlib.Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, rows in (("pool", pool_rows(root)), ("store_answers", answer_rows(root))):
        with (out / f"{name}.jsonl").open("w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        counts[name] = len(rows)
    orows = order_rows(json.loads((root / "sheets" / "sheet1.json").read_text()))
    with (out / "order.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ORDER_FIELDS)
        w.writeheader()
        w.writerows(orows)
    counts["order"] = len(orows)
    return counts


if __name__ == "__main__":
    print(write_all())
