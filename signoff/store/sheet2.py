"""Sheet 2 pool (the plumber's fixture list: toilets, sink faucets, shower heads, vanities), fetched once:
data/sheet2/pool/<store>.json (same shape as data/pool, plus `variants` and `variant_title`), raw replies in
data/sheet2/pool/raw/, each store agent's delivery and returns answer in data/sheet2/store_answers/.
Never calls a cart or checkout tool.

Run: uv run python -m signoff.store.sheet2 [fetch|build|ask]   (no argument: all three)
"""
import concurrent.futures as cf
import datetime
import json
import pathlib
import re
import sys
import time

from signoff.store import ask, build_pool, replay, ucp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "data" / "sheet2" / "pool"
RAW = OUT / "raw"
ANSWERS = ROOT / "data" / "sheet2" / "store_answers"
STORES = ["swissmadison.com", "horow.com", "deervalleybath.com", "kingstonbrass.com"]
LINES = {  # line id -> (queries, title must match, title must not match)
    "T1": (["toilet", "one piece toilet", "10 inch rough in toilet"], r"toilet|commode|water closet",
           r"\bseats?\b|bidet|tank only|bowl only|\blid\b|flange|bolt|paper|brush|holder|\bwax\b|supply|bracket|cover|"
           r"flush valve|fill valve|repair|lever|handle|\bkit\b|cleaner|\bpart\b|tank lid|gasket|rod|trap|safety|riser|stool"),
    "T2": (["bathroom faucet", "bathroom sink faucet"], r"faucet",
           r"kitchen|shower|\btub\b|bathtub|bidet|laundry|pot filler|drain only|cartridge|diverter|aerator|escutcheon|"
           r"replacement|spout only|trim kit|rough|faucet holes?\b|\d+ ?mm faucet|overflow|vessel|pedestal|undermount|"
           r"drop-in|console|\bsinks?\b(?!.*faucet$)"),
    "T3": (["shower head"], r"shower ?head|rain(fall)? shower|hand ?held|hand shower",
           r"arm only|extension|flange|\bhose\b|bracket|holder|diverter|connector|elbow|drain|trim kit|rough|cartridge|"
           r"filter|cleaner|replacement|kit only|enclosure|\bbase\b|\bpan\b|\bdoor\b|chair|\btub\b|toilet"),
    "T4": (["bathroom vanity", "30 inch vanity"], r"vanity",
           r"faucet|mirror|stool|bench|light|sconce|hardware|knob|handle|\bpull\b|tray|organizer|bulb|\bbar\b|"
           r"top only|sink only|basin only|countertop only|\bvanity top\b|stool|chair|replacement|\bdrawer\b"),
}
SPACING = 0.8


def fetch(force: bool = False) -> dict:
    def one_store(store):
        res = {}
        for line, (queries, _, _) in LINES.items():
            for q in queries:
                p = replay.raw_path(store, q, RAW)
                if p.exists() and not force:
                    res[(store, q)] = "cached"
                    continue
                try:
                    r = ucp.call(store, "search_catalog", {"catalog": {"query": q, "context": {"address_country": "US"}}})
                except Exception as e:  # noqa: BLE001
                    res[(store, q)] = "ERR " + repr(e)[:100]
                    continue
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(r, indent=1))
                res[(store, q)] = "ok %d" % len(r.get("products", []))
                time.sleep(SPACING)
        return res

    out: dict = {}
    with cf.ThreadPoolExecutor(len(STORES)) as ex:  # one thread per store: each store is called about once a second
        for r in ex.map(one_store, STORES):
            out.update(r)
    return out


def build() -> dict:
    out = {}
    OUT.mkdir(parents=True, exist_ok=True)
    for store in STORES:
        found: dict = {}
        for line, (queries, inc, exc) in LINES.items():
            for q in queries:
                p = replay.raw_path(store, q, RAW)
                if not p.exists():
                    continue
                t = p.stat().st_mtime
                for prod in json.loads(p.read_text()).get("products", []):
                    e = found.setdefault(prod["id"], {"prod": prod, "lines": set(), "t": t})
                    title = build_pool.clean_title(prod["title"]).lower()
                    if re.search(inc, title) and not re.search(exc, title):
                        e["lines"].add(line)
        rows = []
        for pid, e in found.items():
            prod = e["prod"]
            avail = [v for v in prod.get("variants", []) if (v.get("availability") or {}).get("available")]
            if not e["lines"] or not avail:
                continue
            v = min(avail, key=lambda v: v["price"]["amount"])
            title = build_pool.clean_title(prod["title"])
            text = title + ".\n" + ucp.plain((prod.get("description") or {}).get("html", ""))
            vt = v.get("title")
            if vt not in (None, "", "Default Title", "Each"):
                text += "\nSelected option: " + ucp.plain(vt) + "."
            rows.append({"store": store, "product_id": pid, "variant_id": v["id"], "title": title,
                         "price_cents": v["price"]["amount"], "url": prod.get("url", ""), "text": text,
                         "fetched_at": datetime.datetime.fromtimestamp(e["t"]).astimezone().isoformat(timespec="seconds"),
                         "image_url": build_pool.image_url(prod), "product_key": build_pool.product_key(store, prod["title"]), "line_ids": sorted(e["lines"]),
                         "variants": len(avail), "variant_title": vt})
        rows.sort(key=lambda r: (r["line_ids"], r["price_cents"]))
        (OUT / f"{store}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
        out[store] = rows
    return out


QUESTION = ("If I order a toilet today to a California address, how many days will delivery take? "
            "And can an opened toilet be returned, and is there any fee?")


def ask_stores() -> list:
    ANSWERS.mkdir(parents=True, exist_ok=True)
    out = []
    for s in STORES:
        f = ANSWERS / f"{s}.json"
        if f.exists():
            out.extend(json.loads(f.read_text()))
            continue
        rec = ask.ask(s, QUESTION)
        f.write_text(json.dumps([rec], indent=1, ensure_ascii=False))
        out.append(rec)
        time.sleep(SPACING)
    return out


if __name__ == "__main__":
    what = sys.argv[1:] or ["fetch", "build", "ask"]
    if "fetch" in what:
        res = fetch()
        print({f"{s}|{q}": r for (s, q), r in res.items() if not r.startswith(("ok", "cached"))} or "fetch ok", len(res), "searches")
    if "build" in what:
        for s, rows in build().items():
            per = {}
            for r in rows:
                for l in r["line_ids"]:
                    per[l] = per.get(l, 0) + 1
            print(s, len(rows), dict(sorted(per.items())))
    if "ask" in what:
        for a in ask_stores():
            print(a["store"], a["delivery"]["stated"], a["delivery"]["quote"], "|", a["returns"]["returnable"], a["returns"]["quote"])
