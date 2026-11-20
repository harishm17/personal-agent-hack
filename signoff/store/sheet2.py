"""Sheet 2 (shared kitchen): fetch a cookware pool once from five stores into data/sheet2/pool/, same pool shape."""
import concurrent.futures as cf
import datetime
import json
import pathlib
import re
import sys

from signoff.store import build_pool, replay, ucp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "data" / "sheet2" / "pool"
RAW = OUT / "raw"
STORES = ["madeincookware.com", "carawayhome.com", "greatjonesgoods.com", "fromourplace.com", "materialkitchen.com"]
# line id (the ids carry the need; the integrator's sheets/sheet2.json decides the final ids) -> queries
LINES = {
    "frying_pan": ["frying pan", "skillet", "nonstick pan"],
    "saucepan": ["saucepan"],
    "stock_pot": ["stock pot", "dutch oven"],
    "roasting_pan": ["roasting pan", "baking sheet"],
    "cookware_set": ["cookware set"],
}
EXCLUDE = r"\blids?\b|spatula|utensil|towel|apron|brush|cleaner|gift ?card|knife|knives|board|mitt|trivet|spoon|ladle|" \
          r"whisk|tongs|rack|handle|steamer|insert|sponge|mat\b|organizer|storage|bundle box|sample|shaker|bowl|mug|cup\b"


def fetch(force: bool = False) -> dict:
    jobs = [(s, q) for s in STORES for qs in LINES.values() for q in qs]

    def one(job):
        store, q = job
        p = replay.raw_path(store, q, RAW)
        if p.exists() and not force:
            return job, "cached"
        try:
            r = ucp.call(store, "search_catalog", {"catalog": {"query": q, "context": {"address_country": "US"}}})
        except Exception as e:  # noqa: BLE001
            return job, "ERR " + repr(e)[:100]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, indent=1))
        return job, "ok %d" % len(r.get("products", []))

    with cf.ThreadPoolExecutor(5) as ex:
        return dict(ex.map(one, jobs))


def _key(store: str, title: str) -> str:
    brand = STORE_BRAND[store]
    t = re.sub(r"[^a-z0-9.\" ]+", " ", title.lower().replace(brand, ""))
    return f"{brand} {re.sub(chr(92) + 's+', ' ', t).strip()}"


def build() -> dict:
    out = {}
    for store in STORES:
        found: dict = {}
        for line, qs in LINES.items():
            for q in qs:
                p = replay.raw_path(store, q, RAW)
                if not p.exists():
                    continue
                for prod in json.loads(p.read_text()).get("products", []):
                    e = found.setdefault(prod["id"], {"prod": prod, "lines": set(), "t": p.stat().st_mtime})
                    e["lines"].add(line)
        rows = []
        for pid, e in found.items():
            prod = e["prod"]
            title = build_pool.clean_title(prod["title"])
            if re.search(EXCLUDE, title.lower()):
                continue
            variants = [v for v in prod.get("variants", []) if (v.get("availability") or {}).get("available")]
            if not variants:
                continue
            v = min(variants, key=lambda v: v["price"]["amount"])
            text = title + ".\n" + ucp.plain((prod.get("description") or {}).get("html", ""))
            if v.get("title") not in (None, "", "Default Title", "Each"):
                text += "\nSelected option: " + ucp.plain(v["title"]) + "."
            rows.append({"store": store, "product_id": pid, "variant_id": v["id"], "title": title,
                         "price_cents": v["price"]["amount"], "url": prod.get("url", ""), "text": text,
                         "fetched_at": datetime.datetime.fromtimestamp(e["t"]).astimezone().isoformat(timespec="seconds"),
                         "product_key": _key(store, title),
                         "line_ids": sorted(e["lines"])})
        rows.sort(key=lambda r: (r["line_ids"], r["price_cents"]))
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{store}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
        out[store] = rows
    return out


STORE_BRAND = {"madeincookware.com": "made in", "carawayhome.com": "caraway", "greatjonesgoods.com": "great jones",
               "fromourplace.com": "our place", "materialkitchen.com": "material"}

if __name__ == "__main__":
    print({f"{s}|{q}": r for (s, q), r in fetch().items() if not r.startswith(("ok", "cached"))} or "fetch ok")
    for s, rows in build().items():
        print(s, len(rows))
