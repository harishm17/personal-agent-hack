"""Build the pool of a sheet from its raw search replies: data/pool/<store>.json (sheet1) or data/<sheet>/pool/<store>.json.

One rule for every sheet: a product from a line's query stays in the pool for that line when the store's own labels or title
say what it is (signoff.store.relevance), and every in-stock option is carried. Nothing in here knows a brand, a product type or
a sheet. A product that is dropped is counted, with the reason, in `<pool folder's parent>/pool_summary.json`.
"""
import datetime
import html
import json
import pathlib
import re
import sys

from signoff.store import relevance, replay, sheetctx, ucp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def image_url(prod: dict):
    """The store's own first image from its reply (`media[0].url`), or None. Nothing is fetched or resized."""
    media = prod.get("media") or []
    return (media[0].get("url") if media and isinstance(media[0], dict) else None) or None


def options_of(prod: dict) -> list[dict]:
    """Every in-stock option of the product, as the store's own reply lists them: {variant_id, title, price_cents, available}."""
    out = []
    for v in prod.get("variants", []):
        if (v.get("availability") or {}).get("available"):
            out.append({"variant_id": v["id"], "title": ucp.plain(v.get("title") or "") or None,
                        "price_cents": v["price"]["amount"], "available": True})
    return out


def clean_title(t: str) -> str:
    t = html.unescape(re.sub(r"&(trade|reg);", "", t or ""))
    return re.sub(r"[™®]", "", t).strip()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.\" ]+", " ", clean_title(s).lower())).strip()


def product_key(prod: dict | str) -> str:
    """The store's own vendor (or brand) and model fields, lower-cased, or its title when the store gives none. The same product
    at another store has the same key only if both stores say so; nothing is guessed from a list of brands."""
    if isinstance(prod, str):
        return _norm(prod)
    maker = prod.get("vendor") or prod.get("brand") or ""
    model = prod.get("model") or prod.get("title") or ""
    key = _norm(model)
    return _norm(f"{maker} {model}") if maker and _norm(str(maker)) not in key else key


def build(sheet_id: str | None = None) -> dict:
    """Rebuild the pool of the sheet from the raw replies on disk. Returns {store: rows}; writes the pool files and the summary."""
    sheet_id = sheetctx.data_id(sheet_id)  # a sheet with `data_from` has no pool of its own: build the one it uses
    sheet = json.loads((ROOT / "sheets" / f"{sheet_id}.json").read_text())
    pool_dir = sheetctx.pool_dir(sheet_id)
    raw_dir = pool_dir / "raw"
    pool_dir.mkdir(parents=True, exist_ok=True)
    out, summary = {}, {"sheet": sheet_id, "rule": "a product stays for a line when its title or one of the store's own labels "
                        "(collections, tags, categories) has a phrase ending with the head word of the line's need or of one of "
                        "its queries, and the rest of that phrase is named in the title or labels", "stores": {}}
    for store in sheet["stores"]:
        found: dict = {}
        for line in sheet["lines"]:
            for q in line["queries"]:
                p = replay.raw_path(store, q, raw_dir)
                if not p.exists():
                    continue
                fetched = datetime.datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec="seconds")
                for prod in json.loads(p.read_text()).get("products", []):
                    e = found.setdefault(prod["id"], {"prod": prod, "lines": set(), "fetched_at": fetched})
                    e["lines"].add(line["id"])
        rows, per_line = [], {l["id"]: {"candidates": 0, "kept": 0, "dropped": []} for l in sheet["lines"]}
        for pid, e in found.items():
            prod, kept_for = e["prod"], []
            for line in sheet["lines"]:
                if line["id"] not in e["lines"]:
                    continue
                per_line[line["id"]]["candidates"] += 1
                ok, why = False, ""
                for need in [line["need"], *line["queries"]]:  # the need, or any way the sheet itself names the item
                    ok, why = relevance.belongs(prod, need)
                    if ok:
                        break
                if ok:
                    kept_for.append(line["id"])
                else:
                    per_line[line["id"]]["dropped"].append({"product_id": pid, "title": clean_title(prod["title"]), "why": why})
            options = options_of(prod)
            if kept_for and not options:
                for lid in kept_for:
                    per_line[lid]["dropped"].append({"product_id": pid, "title": clean_title(prod["title"]), "why": "no option in stock"})
                continue
            if not kept_for:
                continue
            for lid in kept_for:
                per_line[lid]["kept"] += 1
            v = min((v for v in prod["variants"] if (v.get("availability") or {}).get("available")), key=lambda v: v["price"]["amount"])
            title = clean_title(prod["title"])
            text = title + ".\n" + ucp.plain((prod.get("description") or {}).get("html", ""))
            vt = v.get("title")
            if vt not in (None, "", "Default Title", "Each"):
                text += "\nSelected option: " + ucp.plain(vt) + "."
            rows.append({"store": store, "product_id": pid, "variant_id": v["id"], "title": title,
                         "price_cents": v["price"]["amount"], "url": prod.get("url", ""), "text": text,
                         "fetched_at": e["fetched_at"], "image_url": image_url(prod), "options": options,
                         "product_key": product_key(prod), "line_ids": sorted(kept_for),
                         "variants": len(options), "variant_title": vt})
        rows.sort(key=lambda r: (r["line_ids"], r["price_cents"]))
        (pool_dir / f"{store}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
        out[store] = rows
        summary["stores"][store] = {lid: {"candidates": d["candidates"], "kept": d["kept"], "dropped": len(d["dropped"]),
                                          "dropped_why": d["dropped"]} for lid, d in per_line.items()}
    (pool_dir.parent / "pool_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    return out


if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else None
    s = build(sid)
    for store, rows in s.items():
        per: dict = {}
        for r in rows:
            for l in r["line_ids"]:
                per[l] = per.get(l, 0) + 1
        print(store, len(rows), dict(sorted(per.items())), sum(len(r["options"]) for r in rows), "options")
