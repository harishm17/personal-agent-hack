"""Build data/pool/<store>.json from the raw search replies in data/pool/raw/ (replay and live share this)."""
import datetime
import glob
import html
import json
import pathlib
import re
import sys

from signoff.store import ucp
from signoff.store.fetch import RAW, raw_path

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
POOL = ROOT / "data" / "pool"

# Per line: title must match `inc` and must not match `exc`. Titles only: no figure is read here.
RULES = {
    "L1": (r"shower (chair|seat|bench|stool)|bath(ing)? (seat|bench|chair|stool)|bath & shower|transfer bench",
           r"transport|wall mounted|reclining|\bmat\b|leg tips|\bdisc\b|\bboard\b|belt|blanket|sling|slide sheet"
           r"|stand assist|liner|\bpads?\b|^[^|]*commode(?!.*bench)"),
    "L2": (r"toilet seat|seat riser|seat elevator|toilet riser",
           r"cushion|commode|shower|safety (frame|rail)|\brail\b"),
    "L3": (r"commode", r"liners?\b|\bpads\b|bucket|transport|wheelchair|bench|sitz|opening"),
    "L4": (r"walker", r"walker bag|knee|3[- ]wheel|4[- ]wheel|transport|rollator|upright"),
    "L5": (r"grab bars?|bath handle",
           r"suction|reacher|floor to ceiling|accessory|toilet rail|\bpole\b|bed assist|bumper"),
    "L6": (r"bed ?(side )?rails?|bedside rail|bed (assist )?(bar|handle|cane)|stable rail|mobility rail",
           r"bumper|\bpads\b|fall mat|ladder|electric|riser|toilet|bath|tub|stand assist|transport|leg lift"),
}
BRANDS = ["carex", "drive", "medline", "guardian", "stander", "probasics", "nova", "elements", "dmi", "pride", "vive"]
STORE_BRAND = {"carex.com": "carex", "vivehealth.com": "vive"}


def image_url(prod: dict):
    """The store's own first image from its reply (`media[0].url`), or None. Nothing is fetched or resized."""
    media = prod.get("media") or []
    return (media[0].get("url") if media and isinstance(media[0], dict) else None) or None


def clean_title(t: str) -> str:
    t = html.unescape(re.sub(r"&(trade|reg);", "", t or ""))
    return re.sub(r"[™®]", "", t).strip()


def product_key(store: str, title: str) -> str:
    """Maker and model, lower-cased: 'Wonder EZ Adjust Bed Rail by Stander' -> 'stander wonder ez adjust bed rail'."""
    t = clean_title(title).lower()
    maker = None
    m = re.search(r"\s+by\s+([a-z0-9+ ]+?)(?:\s+with\b.*)?$", t)
    if m and m.group(1).strip().split()[0] in BRANDS:
        maker = m.group(1).strip().split()[0]
        t = t[:m.start()] + (t[m.end(1):] if False else "")
        t = re.sub(r"\s+by\s+" + re.escape(m.group(1)), "", clean_title(title).lower())
    for b in BRANDS:
        if maker is None and re.match(rf"{b}\b", t):
            maker = b
            t = t[len(b):]
    maker = maker or STORE_BRAND.get(store, "")
    t = re.sub(r"[^a-z0-9.\" ]+", " ", t)
    return re.sub(r"\s+", " ", f"{maker} {t}").strip()


def line_ids_for(sheet: dict, title: str, queries_hit: set) -> list:
    out = []
    for line in sheet["lines"]:
        if not set(line["queries"]) & queries_hit:
            continue
        inc, exc = RULES.get(line["id"], (r".", r"$^"))
        t = clean_title(title).lower()
        if re.search(inc, t) and not re.search(exc, t):
            out.append(line["id"])
    return out


def build(sheet_path: str = "sheets/sheet1.json") -> dict:
    sheet = json.loads((ROOT / sheet_path).read_text())
    summary = {}
    for store in sheet["stores"]:
        found: dict = {}
        for line in sheet["lines"]:
            for q in line["queries"]:
                p = raw_path(store, q)
                if not p.exists():
                    continue
                fetched = datetime.datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec="seconds")
                for prod in json.loads(p.read_text()).get("products", []):
                    e = found.setdefault(prod["id"], {"prod": prod, "queries": set(), "fetched_at": fetched})
                    e["queries"].add(q)
        rows = []
        for pid, e in found.items():
            prod = e["prod"]
            lids = line_ids_for(sheet, prod["title"], e["queries"])
            variants = [v for v in prod.get("variants", []) if (v.get("availability") or {}).get("available")]
            if not lids or not variants:
                continue
            v = min(variants, key=lambda v: v["price"]["amount"])
            title = clean_title(prod["title"])
            text = title + ".\n" + ucp.plain((prod.get("description") or {}).get("html", ""))
            if v.get("title") not in (None, "", "Default Title", "Each"):
                text += "\nSelected option: " + ucp.plain(v["title"]) + "."
            rows.append({
                "store": store, "product_id": pid, "variant_id": v["id"], "title": title,
                "price_cents": v["price"]["amount"], "url": prod.get("url", ""), "text": text,
                "fetched_at": e["fetched_at"], "image_url": image_url(prod), "product_key": product_key(store, prod["title"]),
                "line_ids": lids,
            })
        rows.sort(key=lambda r: (r["line_ids"], r["price_cents"]))
        (POOL / f"{store}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
        summary[store] = rows
    return summary


if __name__ == "__main__":
    s = build(*sys.argv[1:])
    keys: dict = {}
    for store, rows in s.items():
        per = {}
        for r in rows:
            for l in r["line_ids"]:
                per[l] = per.get(l, 0) + 1
            keys.setdefault(r["product_key"], set()).add(store)
        print(store, len(rows), dict(sorted(per.items())))
    print("keys at 2+ stores:", {k: sorted(v) for k, v in keys.items() if len(v) > 1})
