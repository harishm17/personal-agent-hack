"""The sheet's state, held in memory and recomputed by code on every change.

Signatures are fixed by CONTRACT.md "In-process calls". The dict returned by these functions is shared:
read it, do not change it. Limits and strikes change only through `apply_issuer`, which `signoff.sign`
calls after it has verified a signed request. Nothing here is reachable from a model.
"""
import datetime
import gzip
import hashlib
import json
import os
import pathlib
import re
import threading
import time

from signoff import config
from signoff.engine import health, obs, options, paths, planted, receipts, rules
from signoff.extract import spans

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DATA, FIXTURES, SHEETS = ROOT / "data", ROOT / "fixtures", ROOT / "sheets"
UNSIGNED = "Not signed. No cart exists at any store."


class EngineError(ValueError):
    """A request the engine refuses. `status` is the HTTP status a route should answer with."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


_lock = threading.RLock()
_s = {"loaded": False, "version": 0}


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _read(path):
    return json.loads(pathlib.Path(path).read_text())


def _read_dir(folder):
    rows = []
    for path in sorted(pathlib.Path(folder).glob("*.json")):
        rows.extend(_read(path))
    return rows


def _dirs(sheet_id=None):
    """(pool, store answers, figures) folders of a sheet, by the one rule in `signoff.engine.paths`."""
    where = paths.of(sheet_id or _s.get("sheet_id") or "sheet1", DATA)
    return where["pool"], where["answers"], where["figures"]


def _has_data_pool():
    return any(_dirs()[0].glob("*.json"))


def _load_pool():
    """Pool and store answers of the running sheet, from the folders the path rule names (a sheet with
    `data_from` reads the other sheet's). Every option on sale becomes its own row (rule 2).
    Without any pool on disk the placeholder products in fixtures/ are used and `mode` says "fixture"."""
    pool_dir, answers_dir, _ = _dirs()
    if _has_data_pool():
        return options.expand(_read_dir(pool_dir)), _read_dir(answers_dir) if answers_dir.is_dir() else []
    return _read(FIXTURES / "pool.json"), _read(FIXTURES / "store_answers.json")


def _load_figures(pool, from_data, variants=None):
    """Figures from data/figures (fixtures for the fixture pool). The span is checked again here, in code."""
    folder = _dirs()[2]
    run = folder / "_runs" / str(_s.get("reader")) if _s.get("reader") else None
    if from_data and run is not None and run.is_dir():
        figures = _read_dir(run)
    elif from_data:
        figures = _read_dir(folder) if folder.is_dir() else []
    else:
        figures = _read(FIXTURES / "figures.json")
    text = {(p["store"], p["product_id"]): p.get("text") for p in pool}
    variants = variants or {}
    number_rule_off = os.environ.get("SIGNOFF_NUMBER_RULE") == "off"  # read once: config.env re-reads the keys file on a miss
    for f in figures:
        page = text.get((f["store"], f["product_id"]))
        if number_rule_off:
            f["span_found_in_text"] = rules.span_found(f, page)
        else:
            spans.ready(f, page)
        option = variants.get((f["store"], f["product_id"], f.get("variant_id")))
        if f["span_found_in_text"] and option:
            spans.apply_option_rule(f, option)
        if f["span_found_in_text"] and page is not None:  # the store's whole sentence, for the screen to show around the quote
            sentence, a, b = rules.sentence_around(page, f["start"], f["end"])
            f.update(sentence=sentence, quote_in_sentence=[a, b])
    return figures


def _load_readers(from_data):
    """Which reader decided, and how far the others agree with it (signoff.extract.score writes the file)."""
    path = _dirs()[2] / "_runs" / "comparison.json"
    if not from_data or not path.exists():
        return None
    try:
        made = _read(path)
        return {"reference": made["reference"], "measure": made["measure"], "note": made["note"],
                "pages": made.get("pages"), "made_at": made["made_at"], "readers": made["readers"]}
    except (ValueError, KeyError):
        return None


def _order_file(sheet_id):
    """Where the limits read from a sheet's order are cached (see `signoff.engine.paths`)."""
    return paths.of(sheet_id, DATA)["order"]


def _load_order(sheet_id, from_data):
    """The limits as the agent read them from the written order (signoff.extract.order writes the file). Each
    quote is looked up again here in the order's own text. Shown beside the sheet; the engine runs on the sheet."""
    path = _order_file(sheet_id)
    if not from_data or not path.exists():
        return None
    try:
        made = _read(path)
        if made.get("sheet_id") != sheet_id:
            return None
        text = (ROOT / made["doc"]).read_text()
        for row in made["limits"] + made.get("fulfilment", []):
            row["span_found_in_text"] = rules.span_found(row, text)
        return made
    except (ValueError, KeyError, OSError) as error:
        health.note("order", "the limits read from the order could not be loaded (%s); limits show without their "
                    "sentence from the order" % type(error).__name__)
        return None


def _with_order(sheet):
    """(a copy of the sheet whose limits carry `from_order`, the `order` summary). The sheet the engine runs on
    is not touched. `matches` is worked out now, so a limit Dana has moved shows as changed from the order."""
    made = _s.get("order")
    if not made:
        return sheet, None
    read = {r["limit_id"]: r for r in made["limits"] if r.get("span_found_in_text")}
    lines, matching, total = [], 0, 0
    for line in sheet["lines"]:
        limits = []
        for limit in line["limits"]:
            total += 1
            r, b = read.get(limit["id"]), limit["bound"]
            if r is None:
                limits.append(limit)
                continue
            same = r["op"] == limit["op"] and r["unit"] == limit["unit"] and (
                (b["source"] == "issuer" and r["bound"]["source"] == "issuer" and abs(b["value"] - r["value"]) < 1e-9) or
                (b["source"] == "shopper" and r["bound"]["source"] == "shopper" and b["fact"] == r["bound"]["fact"]))
            matching += 1 if same else 0
            limits.append(dict(limit, from_order={
                "doc": made["doc"], "quote": r["quote"], "start": r["start"], "end": r["end"], "value": r["value"],
                "op": r["op"], "unit": r["unit"], "terms": r["terms"], "measurement": r.get("measurement"),
                "extractor": r["extractor"], "span_found_in_text": True, "matches": same}))
        lines.append(dict(line, limits=limits))
    how = {f["line_id"]: f for f in made.get("fulfilment", []) if f.get("span_found_in_text")}
    lines = [dict(l, fulfilment_from_order={k: how[l["id"]][k] for k in ("how", "quote", "start", "end")},
                  ) if l["id"] in how else l for l in lines]
    summary = {"doc": made["doc"], "title": made.get("title"), "issuer": made.get("issuer"),
               "limits_in_sheet": total, "limits_derived": len(read), "limits_matching": matching,
               "limits_matching_sheet_file": made.get("limits_equal_to_the_sheet"),
               "reading": "the agent's reading of the order matches the sheet on %d of %d limits" % (matching, total),
               "derived_at": made.get("derived_at"), "extractor": made.get("extractor"),
               "delivered_by": _s.get("order_delivery") or {"via": "file", "doc": made["doc"]}}
    return dict(sheet, lines=lines), summary


_raw_cache = {}


def _load_variants(pool, from_data):
    """What the store says about each candidate's option: `{(store, product_id, variant_id): {...}}`. The option's
    title, how many options are on sale and the other options' names come from the pool row; the currency from
    the store's own reply as STORE cached it (raw/), USD being what every store here answers in."""
    if not from_data:
        return {}
    currency, raw = {}, _dirs()[0] / "raw"
    if raw.is_dir():
        files = sorted(raw.glob("*/*.json"))
        stamp = (str(raw), tuple((f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in files))
        if _raw_cache.get("stamp") != stamp:  # the stores' raw replies are large: read once per change on disk
            found = {}
            for path in files:
                try:
                    for product in _read(path).get("products") or []:
                        for v in product.get("variants") or []:
                            if (v.get("price") or {}).get("currency"):
                                found[(path.parent.name, product.get("id"), v.get("id"))] = v["price"]["currency"]
                except (ValueError, AttributeError, OSError):
                    continue
            _raw_cache.update(stamp=stamp, currency=found)
        currency = _raw_cache["currency"]
    out, unknown = {}, 0
    for p in pool:
        key = (p["store"], p["product_id"], p.get("variant_id"))
        listed = [o for o in p.get("options") or [] if o.get("available", True)]
        others = sorted({str(o.get("title")) for o in listed if o.get("variant_id") != p.get("variant_id") and o.get("title")})
        if key not in currency and not p.get("currency"):
            unknown += 1
        out[key] = {"variant_title": p.get("variant_title"), "currency": p.get("currency") or currency.get(key),
                    "variant_price_cents": p.get("price_cents"), "variants": max(len(listed), 1),
                    "variants_listed": max(len(p.get("options") or []), 1),
                    "option_labels": [p["variant_title"]] if p.get("variant_title") and others else [],
                    "other_option_labels": others, "image_url": p.get("image_url")}
    if unknown:
        health.note("currency", "%d candidates have no currency in the store's reply; the signed pick names none for them" % unknown)
    else:
        health.clear("currency")
    return out


def _option_names(pool, figures, sheet):
    """An option's own name is a statement about it, and a statement about another size is not (the E26 rule).

    For a candidate that is one option of a product whose name states a figure ("18 Inch"): the name becomes a
    statement of that figure with its span in the candidate's text; page statements that give the same value,
    or whose passage names this option's value, are about this option; every other page statement of that
    figure describes another size and is not put to this candidate's test. If no page statement is about this
    option, the name stands alone and the check is unclear, with both shown: "option says 18 in; the page
    describes 12, 16 and 24 in". Returns the figures with the name statements added."""
    by_row = {}
    for f in figures:
        by_row.setdefault((f["store"], f["product_id"], f.get("variant_id")), []).append(f)
    added = []
    for row in pool:
        key = (row["store"], row["product_id"], row.get("variant_id"))
        for named in options.named_figures(row, sheet, spans.quote_numbers, rules.unit_name, spans.family_of):
            mine = [f for f in by_row.get(key, []) if f["figure"] == named["figure"] and f.get("span_found_in_text")
                    and f.get("number_in_quote") is not False]
            value, about_this, others = named["value"], [], []
            for f in mine:
                numbers = [f.get("value")] if f.get("kind") == "single" else [f.get("low"), f.get("high")]
                numbers = [n for n in numbers if isinstance(n, (int, float))]
                same = (len(numbers) == 1 and abs(numbers[0] - value) < 1e-6) or \
                    (len(numbers) == 2 and numbers[0] - 1e-6 <= value <= numbers[1] + 1e-6)
                names_it = any(abs(n["value"] - value) < 1e-6 for n in spans.quote_numbers(f.get("quote") or ""))
                (about_this if same or names_it else others).append(f)
            text = row.get("text") or ""
            other_sizes = {n["value"] for o in row.get("options") or [] if o.get("title") != named["quote"]
                           for n in spans.quote_numbers(str(o.get("title") or ""))}
            other_sizes |= {v for f in others for v in ([f.get("value")] if f.get("kind") == "single" else [f.get("low"), f.get("high")])
                            if isinstance(v, (int, float))}
            for f in about_this:
                # the page's line for this option: from the matched statement to where the text turns to another
                # size (the next number that names a different option), not the passage that lists every size
                begin, end = f["start"], f["end"]
                after = text[end:end + 140]
                turn = next((n["start"] for n in spans.quote_numbers(after)
                             if any(abs(n["value"] - v) < 1e-6 for v in other_sizes)), len(after))
                # ... or where the list starts its next entry: a number followed by the same words as this one
                shape = re.match(r"\s*\d[\d.,/]*\s*(?:\"|”|″)?\s*((?:[A-Za-z]+\s?){1,2})", text[begin:end])
                if shape and shape.group(1).strip():
                    again = re.search(r"\d[\d.,/]*\s*(?:\"|”|″)?\s*" + re.escape(shape.group(1).strip()), after)
                    if again:
                        turn = min(turn, again.start())
                stop = after.find("\n", 0, turn)
                line = (text[begin:end] + after[:stop if stop >= 0 else turn]).rstrip(" -–,;")
                f.update(sentence=line, quote_in_sentence=[0, end - begin])
                f["option_match"] = {"option": named["quote"], "line": line,
                                     "why": "the option you would buy is %s; the page's line for it: %s" % (named["quote"], line)}
            for f in others:
                shown = "%g" % f["value"] if f.get("kind") == "single" else "%g to %g" % (f["low"], f["high"])
                f["for_other_option"] = "describes another size (%s %s); this option is %s" % (shown, f.get("unit") or "", named["quote"])
            statement = {"store": row["store"], "product_id": row["product_id"], "variant_id": row.get("variant_id"),
                         "figure": named["figure"], "kind": "single", "value": value, "low": value, "high": value,
                         "unit": named["unit"], "quote": named["quote"], "start": named["start"], "end": named["end"],
                         "extractor": "code: the option's own name", "label": "Selected option",
                         "span_found_in_text": rules.span_found(named, row.get("text")), "option_name": True}
            if not about_this:
                described = sorted({n for f in others for n in ([f.get("value")] if f.get("kind") == "single" else [f.get("low"), f.get("high")])
                                    if isinstance(n, (int, float))})
                statement["for_other_option"] = "option says %g %s; the page %s" % (
                    value, named["unit"], ("describes " + ", ".join("%g" % n for n in described[:-1]) + (" and " if len(described) > 1 else "") +
                                           "%g %s" % (described[-1], named["unit"])) if described else "does not describe it")
            added.append((key, statement))
    for key, statement in added:  # the name's statement comes first: its words explain an unclear check
        figures.insert(0, statement)
    return figures


def _load_extras(pool, from_data):
    """Display-only material beside the figures: instruction-like passages found on pages (each a span of the
    page's text, checked again here) and the planted test page's own reading. None of it reaches the pick rule."""
    out = {"instructions": {}, "planted": None, "asked": {}, "delivery_replies": {}, "scan": None}
    folder = _dirs()[2]
    if not from_data:
        return out
    replies = paths.of(_s.get("sheet_id") or "sheet1", DATA)["replies"]
    if replies.is_dir():  # what each store's own agent replied about delivery and returns of a product, verbatim
        for row in _read_dir(replies):
            if not row.get("reply"):
                continue
            shown = {k: row.get(k) for k in ("question", "reply", "asked_at", "role") if row.get(k) is not None}
            out["asked"].setdefault((row["store"], row["product_id"]), []).append(shown)
            try:
                from signoff.store import ask as store_ask
                parsed = store_ask.parse_reply(row["store"], row.get("question"), row["reply"], row.get("asked_at"))
                out["delivery_replies"][(row["store"], row["product_id"])] = {
                    "delivery": parsed["delivery"], "returns": parsed["returns"], "asked_at": row.get("asked_at"),
                    "question": row.get("question")}
            except Exception as error:  # noqa: BLE001  (shown in the state under `degraded`, never silent)
                health.note("product replies", "replies about a product's delivery and returns could not be parsed "
                            "(%s); the store's general answer is shown instead" % type(error).__name__)
    text = {(p["store"], p["product_id"]): options.page_text(p) for p in pool}  # the page every option shares
    if (folder / "_instructions").is_dir():  # the scan of the real pages for text addressed to software
        scanned, examples = 0, []
        for row in _read_dir(folder / "_instructions"):
            page = text.get((row["store"], row["product_id"]))
            if page is None or row.get("text_sha") != hashlib.sha256(page.encode()).hexdigest()[:16]:
                continue  # a page that is no longer in the pool, or whose text has changed since it was scanned
            scanned += 1
            kept = [{"quote": i["quote"], "start": i["start"], "end": i["end"], "found_by": i.get("found_by")}
                    for i in row.get("instructions") or [] if rules.span_found(i, page)]
            if kept:
                out["instructions"][(row["store"], row["product_id"])] = kept
                examples += [{"quote": k["quote"], "store": row["store"], "product_id": row["product_id"],
                              "product": row.get("title"), "found_by": k["found_by"]} for k in kept]
        out["scan"] = {"pages_scanned": scanned, "pages_in_pool": len({(p["store"], p["product_id"]) for p in pool}),
                       "instructions_found": len(examples),
                       "examples": examples[:10],
                       "text": "%d pages scanned, %d instruction%s to an agent found" % (
                           scanned, len(examples), "" if len(examples) == 1 else "s")}
    # The invented test page is off unless asked for: SIGNOFF_PLANTED=1 (sheet 1 only). What the state shows by
    # default is the scan of the real pages above.
    if os.environ.get("SIGNOFF_PLANTED") == "1" and _s.get("sheet_id") == planted.SHEET_ID and \
            (folder / "_planted" / "figures.json").exists():
        found = _read(folder / "_planted" / "instructions.json") if (folder / "_planted" / "instructions.json").exists() else []
        out["planted"] = {"figures": _read(folder / "_planted" / "figures.json"),
                          "instructions": [i for row in found for i in row.get("instructions") or []]}
    return out


def _load(keep_changes=False):
    sheet_id = _s.get("sheet_id") or os.environ.get("SIGNOFF_SHEET") or "sheet1"
    _s["sheet_id"] = sheet_id
    pool, answers = _load_pool()
    from_data = _has_data_pool() and not any(str(p["store"]).endswith(".example") for p in pool)
    wanted = {line["id"] for line in _read(SHEETS / (sheet_id + ".json"))["lines"]}
    mine = [p for p in pool if wanted & set(p.get("line_ids") or [])]
    if pool and not mine:  # the folders hold another sheet's products: this sheet has no pool yet, and says so
        health.note("pool", "no products for %s have been fetched yet (the pool on disk belongs to another sheet); "
                    "every line is open" % sheet_id)
        pool, answers = [], []
    else:
        health.clear("pool")
        pool = mine if from_data else pool
    mode = "fixture" if not from_data else ("replay" if config.mode() == "replay" else "live")
    variants = _load_variants(pool, from_data)
    figures = _load_figures(pool, from_data, variants)
    if from_data and os.environ.get("SIGNOFF_OPTION_NAMES") != "off":
        figures = _option_names(pool, figures, _read(SHEETS / (sheet_id + ".json")))
    _s.update(pool=pool, answers=answers, figures=figures, mode=mode, loaded=True,
              readers=_load_readers(from_data), extras=_load_extras(pool, from_data),
              order=_load_order(sheet_id, from_data), variants=variants)
    if keep_changes and (_s.get("sheet") or {}).get("id") == sheet_id:
        return
    strikes_file = (DATA if from_data else FIXTURES) / "strikes.json"
    sheet = _read(SHEETS / (sheet_id + ".json"))
    rules.declare_units(sheet)
    try:
        rules.validate_sheet(sheet)
    except ValueError as error:
        raise EngineError("sheets/%s.json cannot be run: %s" % (sheet_id, error), 500) from error
    _s.update(sheet=sheet,
              strikes=_read(strikes_file) if strikes_file.exists() else [],
              seal=None, issuer_key={"enrolled": False, "key_id": None, "persona": None})


def _limit(limit_id):
    for line in _s["sheet"]["lines"]:
        for limit in line["limits"]:
            if limit["id"] == limit_id:
                return line, limit
    raise EngineError("no limit %r on this sheet" % (limit_id,), 404)


def _number(value, low, high, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EngineError("%s needs a number" % what)
    if (low is not None and value < low) or (high is not None and value > high):
        raise EngineError("%s must be between %g and %g" % (what, low, high))
    return value


def _canonical_obj(state):
    """What the issuer signs: sheet id, each line's limits, pick, its figures' quotes and prices, the total."""
    facts = {f["id"]: f["value"] for f in state["sheet"]["shopper_facts"]}
    by_id = {line["line_id"]: line for line in state["lines"]}
    lines = []
    for sheet_line in state["sheet"]["lines"]:
        line = by_id[sheet_line["id"]]
        limits = []
        for l in sheet_line["limits"]:
            b = l["bound"]
            limits.append({"id": l["id"], "op": l["op"], "unit": l["unit"], "set_by": b["source"],
                           "bound": b["value"] if b["source"] == "issuer" else facts[b["fact"]],
                           "terms": [t.get("figure") or "%s=%g" % (t["fact"], facts[t["fact"]]) for t in l["terms"]]})
        out = {"line_id": line["line_id"], "need": line["need"], "status": line["status"],
               "fulfilment": sheet_line.get("fulfilment"), "limits": limits,
               "struck": sorted(s["product_key"] for s in line["struck"]), "pick": None}
        pick = next((c for c in line["candidates"] if c["picked"]), None)
        if pick:
            p = pick["product"]
            out["pick"] = {"id": pick["id"], "store": p["store"], "product_id": p["product_id"],
                           "variant_id": p["variant_id"], "product_key": p["product_key"],
                           "price_cents": p["price_cents"], "quantity": p.get("quantity", 1),
                           "currency": p.get("currency"), "variant_title": p.get("variant_title"),
                           "checks": [{"limit_id": c["limit_id"], "expr": c["expr"]} for c in pick["checks"]],
                           "quotes": [t["quote"] for c in pick["checks"] for t in c["terms"] if t.get("quote")],
                           "delivery": {"status": pick["arrival"]["status"], "quote": pick["arrival"]["quote"],
                                        "scope": pick["arrival"].get("scope"),
                                        "days_low": pick["arrival"]["days_low"], "days_high": pick["arrival"]["days_high"],
                                        "need_by": pick["arrival"]["need_by"]}}
        lines.append(out)
    rule = state["sheet"]["pick_rule"]
    return {"sheet_id": state["sheet"]["id"], "pick_rule": {"id": rule["id"], "label": rule["label"]},
            "lines": lines, "total_cents": state["total_cents"]}


def _canonical(state):
    return json.dumps(_canonical_obj(state), sort_keys=True, separators=(",", ":"))


# What the signed hash is computed over, in words for the seal. Kept beside `_canonical_obj`: change both together.
COVERS = ["limits", "strikes", "picks", "variant and quantity", "prices and currency", "sums", "store quotes",
          "delivery quotes", "pick rule", "total"]


def _seal(state, current_hash):
    seal = _s.get("seal")
    if not seal:
        return dict(state["seal"], covers=list(COVERS))
    return dict(seal, current=seal["sheet_hash"] == current_hash, covers=list(COVERS))


def _attach(state):
    """Adds what is not a rule: who signed, the carts, the issuer's key and the text checks."""
    carts = {c.get("store"): c for c in (_s.get("seal") or {}).get("carts", []) if c.get("cart_url")}
    variants, replies = _s.get("variants") or {}, (_s.get("extras") or {}).get("delivery_replies") or {}
    wanted = {l["id"]: l.get("quantity", 1) for l in _s["sheet"]["lines"]}
    for line in state["lines"]:
        line["quantity"] = wanted[line["line_id"]]  # how many of the pick the list asks for; under the hash
        picked = next((c for c in line["candidates"] if c["picked"]), None)
        line["line_total_cents"] = picked["product"]["price_cents"] * line["quantity"] if picked else None
        for c in line["candidates"]:
            key = (c["product"]["store"], c["product"]["product_id"])
            facts = variants.get(key + (c["product"]["variant_id"],))
            c["product"]["quantity"] = line["quantity"]
            if facts:
                c["product"].update(variant_title=facts["variant_title"], currency=facts["currency"])
                if facts.get("image_url"):
                    c["product"]["image_url"] = facts["image_url"]  # the store's own picture; not under the hash
                c["variants"] = facts["variants"]
                c["variant"] = {"title": facts["variant_title"], "options": facts["option_labels"],
                                "on_sale": facts["variants"], "listed": facts["variants_listed"],
                                "figures_read_from": "the product's text" if facts["variants_listed"] > 1 else "the product's text (one variant)"}
            # whose answer this is: the store's general one, or its reply to a question about this very product
            c["arrival"]["scope"] = "store-wide"
            if c["undo"]:
                c["undo"] = dict(c["undo"], scope="store-wide")
            own = replies.get(key)
            if own:
                d, r = own["delivery"], own["returns"]
                if d.get("stated") and c["arrival"]["status"] == "stated":  # same status, the product's own words
                    c["arrival"].update(quote=d["quote"], days_low=d["days_low"], days_high=d["days_high"],
                                        scope="this product", asked_at=own["asked_at"], question=own["question"])
                elif d.get("stated"):
                    c["arrival"]["product_reply"] = dict(d, scope="this product", note="the store's general answer "
                                                         "states no delivery time; this reply about the product does")
                if r.get("quote"):
                    # a sentence that says the store does not say is "unclear", whatever word it happens to contain
                    unsaid = re.search(r"(?i)does\s*n[o’']t\s+specify|not\s+specif|unclear|doesn[’']t\s+say|does not say", r["quote"])
                    c["undo"] = {"returnable": "unclear" if unsaid else r["returnable"], "fee": r.get("fee"), "quote": r["quote"],
                                 "applies_to": c["product"]["title"], "scope": "this product",
                                 "asked_at": own["asked_at"], "question": own["question"]}
    state["sheet_hash"] = hashlib.sha256(_canonical(state).encode()).hexdigest()
    # Text checks belong to the sheet they were run on: show the ones for this hash; failing that the last
    # ones pushed, marked as not current.
    kept = _s.setdefault("senso_by_hash", {})
    senso = kept.get(state["sheet_hash"], _s.get("senso") or [])
    by_candidate = {}
    for check in senso:
        for key in (check.get("candidate_id"), (check.get("store"), check.get("product_id"))):
            if key and key != (None, None):
                by_candidate.setdefault(key, []).append(check)
    extras = _s.get("extras") or {"instructions": {}, "planted": None, "asked": {}, "scan": None}
    for line in state["lines"]:
        for c in line["candidates"]:
            asked = extras.get("asked", {}).get((c["product"]["store"], c["product"]["product_id"]))
            if asked:  # display only: nothing below reads it, and the pick was made before this point
                c["asked"] = asked
            passages = extras["instructions"].get((c["product"]["store"], c["product"]["product_id"]))
            if passages:
                c["embedded_instructions"] = passages
            found = by_candidate.get(c["id"], []) + by_candidate.get((c["product"]["store"], c["product"]["product_id"]), [])
            if found:
                c["senso"] = {"claims": found}
            cart = carts.get(c["product"]["store"])
            if cart and c["picked"] and line["status"] in ("ready", "next_candidate"):
                c["action"] = {"type": "cart_created", "mode": cart.get("mode"), "cart_url": cart.get("cart_url"),
                               "cart_id": cart.get("cart_id"), "at": cart.get("created_at")}
    if extras.get("scan"):
        state["instruction_scan"] = extras["scan"]
    if extras["planted"]:  # worked out on the side, after the lines and picks above were made without it
        made = planted.candidate(_s["sheet"], [dict(f) for f in extras["planted"]["figures"]],
                                 extras["planted"]["instructions"], _s["answers"])
        if made:
            line = next(l for l in state["lines"] if l["line_id"] == made["line_id"])
            made["cheaper_than_the_pick"] = bool(line["why"]["pick_price_cents"]) and \
                made["candidate"]["product"]["price_cents"] < line["why"]["pick_price_cents"]
            state["planted"] = made
    if extras.get("asked"):  # the stores' own agents are asked about delivery and returns only
        replies = extras.get("delivery_replies") or {}
        state["counts"]["store_agent"] = {
            "questions": sum(len(group) for group in extras["asked"].values()), "products_asked": len(extras["asked"]),
            "delivery_time_stated": sum(1 for r in replies.values() if r["delivery"].get("stated")),
            "returns_answered": sum(1 for r in replies.values() if r["returns"].get("quote"))}
    state["sheet"], order = _with_order(state["sheet"])
    if order:
        state["order"] = order
    held = _s.get("signing")
    if held and time.time() < held["until"]:
        state["signing"] = {"in_progress": True, "sheet_hash": held["sheet_hash"], "since": held["since"]}
    tally = {"inside": 0, "outside": 0, "unclear": 0, "not_stated": 0, "struck": 0}
    for line in state["lines"]:
        mine = {k: 0 for k in tally}
        for c in line["candidates"]:
            mine[c["status"]] += 1
            tally[c["status"]] += 1
        line["why"].update(outside=mine["outside"], unclear=mine["unclear"], not_stated=mine["not_stated"])
    state["counts"].update(candidates=sum(tally.values()), outside=tally["outside"], unclear=tally["unclear"],
                           not_stated=tally["not_stated"])
    state["degraded"] = health.all()  # every fallback in use is named here; empty when all is well
    try:
        state["receipts"] = receipts.summary()
    except Exception:  # noqa: BLE001  (the chain is a record; it never stops a change)
        state["receipts"] = {"count": None, "verified": None, "last_hash": None}
    state["issuer_key"] = dict(_s["issuer_key"])
    state["readers"] = _s.get("readers")
    if _s.get("readers"):
        used = next((f.get("extractor") for f in _s["figures"]), None) or _s["readers"]["reference"]
        state["readers"] = dict(_s["readers"], deciding=used, switched=bool(_s.get("reader")))
    state["senso"] = list(senso)
    state["senso_current"] = state["sheet_hash"] in kept
    state["seal"] = _seal(state, state["sheet_hash"])
    return state


def _recompute(record=True, why="load"):
    started = time.perf_counter()
    state = rules.build_state(_s["sheet"], _s["pool"], _s["figures"], _s["answers"], _s["strikes"], _s["mode"])
    _s["version"] += 1
    state["version"] = _s["version"]
    _s["state"] = _attach(state)
    _s["json"] = json.dumps(_s["state"]).encode()
    if record:
        _record(_s["state"])
    obs.tool_call("check_run", {"why": why, "sheet_id": state["sheet"]["id"], "version": state["version"]},
                  dict(state["counts"], total_cents=state["total_cents"], sheet_hash=state["sheet_hash"][:12]),
                  True, obs.ms_since(started))
    return _s["state"]


def _ensure():
    if not _s["loaded"]:
        _load()
        _recompute(record=False)


def _key_id(action):
    signer = action.get("signer")
    return action.get("key_id") or (signer.get("key_id") if isinstance(signer, dict) else None)


def _open_for_changes():
    if _s.get("seal"):
        raise EngineError("this sheet is signed and its carts exist; reset to start again", 409)
    held = _s.get("signing")
    if held and time.time() < held["until"]:
        raise EngineError("the sheet is being signed right now (hash %s); try again in a moment" % held["sheet_hash"][:12], 409)


# --- decision records go to the database in the background; the app works with the database down ---
_pending, _wake = {}, threading.Event()


def _record(state):
    _pending["state"] = state
    if not _pending.get("worker"):
        _pending["worker"] = threading.Thread(target=_record_loop, daemon=True, name="records")
        _pending["worker"].start()
    _wake.set()


def _record_loop():
    while True:
        _wake.wait()
        _wake.clear()
        state = _pending.pop("state", None)
        if state is None:
            continue
        try:
            from signoff.db import records
            records.write(state)
            health.clear("decision records")
        except Exception as error:  # noqa: BLE001  (the database writer is missing or failed: the app goes on)
            health.note("decision records", "decision records are not reaching the database (%s)" % type(error).__name__)


# --- the contract's in-process calls ---
def get_state() -> dict:
    with _lock:
        _ensure()
        return _s["state"]


def state_json(gzipped=False) -> bytes:
    """The state as JSON bytes, made once per version. Gzipped it is about a tenth of the size, which matters
    for the phone on the tunnel."""
    with _lock:
        _ensure()
        if not gzipped:
            return _s["json"]
        if _s.get("gz_version") != _s["version"]:
            _s.update(gz=gzip.compress(_s["json"], 5), gz_version=_s["version"])
        return _s["gz"]


def version() -> int:
    return _s["version"]


def apply_issuer(action: dict) -> dict:
    """A verified issuer request: `set_limit`, `strike` or `unstrike`. Only `signoff.sign` calls this."""
    with _lock:
        _ensure()
        kind = action.get("type")
        if kind == "sign_sheet":  # signing is `mark_signed`, after the carts exist; here only the hash is checked
            if action.get("sheet_hash") != _s["state"]["sheet_hash"]:
                raise EngineError("the sheet changed since this hash was made", 409)
            return _s["state"]
        _open_for_changes()
        if kind == "set_limit":
            line, limit = _limit(action.get("limit_id"))
            bound = limit["bound"]
            if bound["source"] != "issuer":
                raise EngineError("%s is bounded by a measurement of the shopper's, not by an issuer value" % limit["id"])
            was = bound["value"]
            bound["value"] = _number(action.get("value"), bound.get("min"), bound.get("max"), limit["id"])
            limit["set_at"] = action.get("at") or _now()
            receipts.append("limit_set", "issuer", _key_id(action), action,
                            {"limit_id": limit["id"], "from": was, "to": bound["value"], "unit": limit["unit"]})
        elif kind in ("strike", "unstrike"):
            line_id, key = action.get("line_id"), action.get("product_key")
            if not any(l["id"] == line_id for l in _s["sheet"]["lines"]):
                raise EngineError("no line %r on this sheet" % (line_id,), 404)
            if not key or not any(p["product_key"] == key and line_id in p["line_ids"] for p in _s["pool"]):
                raise EngineError("no product %r on line %s" % (key, line_id), 404)
            _s["strikes"] = [s for s in _s["strikes"] if not (s["line_id"] == line_id and s["product_key"] == key)]
            if kind == "strike":
                _s["strikes"].append({"line_id": line_id, "product_key": key, "by": "issuer",
                                      "reason": str(action.get("reason") or "").strip() or "no reason given",
                                      "at": action.get("at") or _now()})
            receipts.append("strike" if kind == "strike" else "unstrike", "issuer", _key_id(action), action,
                            {"line_id": line_id, "product_key": key})
        else:
            raise EngineError("unknown issuer request type %r" % (kind,))
        return _recompute(why=kind)


def set_shopper_fact(fact_id, value) -> dict:
    with _lock:
        _ensure()
        _open_for_changes()
        fact = next((f for f in _s["sheet"]["shopper_facts"] if f["id"] == fact_id), None)
        if fact is None:
            raise EngineError("no shopper fact %r on this sheet" % (fact_id,), 404)
        was = fact["value"]
        fact["value"] = _number(value, fact.get("min"), fact.get("max"), fact_id)
        receipts.append("shopper_fact", "shopper", None, {"fact_id": fact_id, "value": value},
                        {"fact_id": fact_id, "from": was, "to": fact["value"], "unit": fact["unit"]})
        return _recompute(why="shopper_fact")


def canonical_sheet() -> str:
    with _lock:
        _ensure()
        return _canonical(_s["state"])


def sheet_hash() -> str:
    with _lock:
        _ensure()
        return _s["state"]["sheet_hash"]


def signed_picks(sheet_hash: str) -> list:
    """Not in the contract's list: the picks of exactly the sheet that was signed, for `signoff.sign` to create
    carts from and nothing else: `[{store, variant_id, quantity, line_id, candidate_id, product_id, title,
    price_cents}]`. Refused if `sheet_hash` is not the sheet as it stands now. From this call until
    `mark_signed` (or `release_signing`, or 90 seconds) the sheet is held: a change by anyone is refused, so
    what is sealed is what was signed and what the carts were made from."""
    with _lock:
        _ensure()
        _open_for_changes()
        if sheet_hash != _s["state"]["sheet_hash"]:
            raise EngineError("the sheet changed since this hash was made: signed %s, now %s" % (
                str(sheet_hash)[:12], _s["state"]["sheet_hash"][:12]), 409)
        picks = [{"store": c["product"]["store"], "variant_id": c["product"]["variant_id"],
                  "quantity": c["product"].get("quantity", 1), "line_id": line["line_id"], "candidate_id": c["id"],
                  "product_id": c["product"]["product_id"], "title": c["product"]["title"],
                  "variant_title": c["product"].get("variant_title"), "currency": c["product"].get("currency"),
                  "price_cents": c["product"]["price_cents"]}
                 for line in _s["state"]["lines"] if line["status"] in ("ready", "next_candidate")
                 for c in line["candidates"] if c["picked"]]
        _s["signing"] = {"sheet_hash": sheet_hash, "picks": picks, "since": _now(), "until": time.time() + 90}
        return [dict(p) for p in picks]


def release_signing() -> dict:
    """Ends a hold that `signed_picks` began, when the signing did not go through (a store refused a cart)."""
    with _lock:
        _ensure()
        _s["signing"] = None
        return _recompute(record=False, why="signing_released")


def mark_signed(signature: dict, carts: list) -> dict:
    """Called by `signoff.sign` after a verified `sign_sheet` and after the carts were created. The seal records
    the hash that was signed, `signature["sheet_hash"]`. If the sheet no longer has that hash (someone changed a
    measurement or a limit while the stores were being called), nothing is sealed and the refusal says so."""
    with _lock:
        _ensure()
        signature, carts = dict(signature or {}), list(carts or [])
        signed = signature.get("sheet_hash")
        if not signed:
            raise EngineError("the signature names no sheet hash, so nothing can be sealed")
        if signed != _s["state"]["sheet_hash"]:
            _s["signing"] = None
            raise EngineError("the sheet changed after it was signed (signed %s, now %s): nothing is sealed. "
                              "Any cart just created belongs to the signed sheet, not to this one." % (
                                  str(signed)[:12], _s["state"]["sheet_hash"][:12]), 409)
        _s["signing"] = None
        again = _s.get("seal") if (_s.get("seal") or {}).get("sheet_hash") == signed else None
        name = signature.get("name") or signature.get("signer") or _s["sheet"]["issuer"]["name"]
        at = signature.get("at") or signature.get("signed_at") or _now()
        if again:  # the same signature again, when a store that had not answered now has: the time of signing stands
            at = again["signed_at"]
        made = [c for c in carts if c.get("cart_url")]
        waiting = [c for c in carts if c.get("mode") == "pending"]
        failed = [c for c in carts if c.get("mode") == "failed"]
        n = len(made)
        text = "Signed by %s at %s. %d cart%s created." % (name, str(at)[11:16] or at, n, "" if n == 1 else "s")
        if waiting:
            text += " %d store%s not answered yet." % (len(waiting), " has" if len(waiting) == 1 else "s have")
        if failed:
            text += " %d cart%s failed." % (len(failed), "" if len(failed) == 1 else "s")
        _s["seal"] = {"signed": True, "text": text, "sheet_hash": signed,
                      "signature": signature, "carts": carts, "signed_at": at, "signer": name,
                      "carts_created": n, "carts_pending": len(waiting), "carts_failed": len(failed)}
        if not again:
            receipts.append("signed", "issuer", _key_id(signature), signature,
                            {"sheet_hash": signed, "signer": name, "total_cents": _s["state"]["total_cents"]})
        receipts.append("carts_created" if not again else "carts_updated", "system", _key_id(signature), carts,
                        {"sheet_hash": signed,
                         "carts": [{k: c.get(k) for k in ("store", "cart_id", "total_cents", "mode")} for c in carts]})
        return _recompute(why="signed" if not again else "carts_updated")


def set_issuer_key(info: dict) -> dict:
    """Not in the contract's list: lets `signoff.sign` show the enrolled key and the Persona result."""
    with _lock:
        _ensure()
        _s["issuer_key"] = {"enrolled": False, "key_id": None, "persona": None, **(info or {})}
        return _recompute(record=False)


def set_senso(checks: list) -> dict:
    with _lock:
        _ensure()
        _s["senso"] = list(checks or [])
        _s.setdefault("senso_by_hash", {})[_s["state"]["sheet_hash"]] = _s["senso"]
        return _recompute(record=False, why="set_senso")


def set_reader(name=None) -> dict:
    """Not in the contract's list: which reader's figures count. `None` is the default (the reference reader's,
    as combined in data/figures/); a name such as "sie:Qwen/Qwen3.8-27B-FP8" uses that reader's own run. For the
    reader gate: the outcome to compare is `readers` in the state (agreement with the reference)."""
    with _lock:
        _ensure()
        _open_for_changes()
        slug = re.sub(r"[^A-Za-z0-9.]+", "-", name).strip("-") if name else None
        if slug and not (_dirs()[2] / "_runs" / slug).is_dir():
            raise EngineError("no run of reader %r under data/figures/_runs" % (name,), 404)
        was = _s.get("reader")
        _s["reader"] = slug
        _load(keep_changes=True)
        receipts.append("reader_switched", "system", None, {"reader": name}, {"from": was or "reference", "to": slug or "reference"})
        return _recompute(why="set_reader")


def use_sheet(sheet_id: str) -> dict:
    """Not in the contract's list: puts another sheet file on the table (one sheet at a time), as after a reset.
    The engine has no line of code about what a sheet is for: lines, limits, units and figure names come from
    `sheets/<id>.json`, the products from that sheet's pool."""
    with _lock:
        if not (SHEETS / (str(sheet_id) + ".json")).exists():
            raise EngineError("no sheet %r" % (sheet_id,), 404)
        _s.update(sheet_id=sheet_id, reader=None, sheet=None)
        _load()
        receipts.start("sheet %s" % sheet_id)
        obs.session(sheet_id)
        return _recompute(why="use_sheet")


def set_order_delivery(info: dict) -> dict:
    """Not in the contract's list: how the order reached the app (for example an Airbyte sync's job id and
    time). Shown as `order.delivered_by`; it changes nothing else."""
    with _lock:
        _ensure()
        _s["order_delivery"] = dict(info or {}) or None
        return _recompute(record=False, why="order_delivery")


def reload_data() -> dict:
    """Reads pool, store answers and figures again; the issuer's limits, strikes and the seal are kept."""
    with _lock:
        _load(keep_changes=_s["loaded"])
        return _recompute()


def reset() -> dict:
    """Back to unsigned, no key, sheet as on disk: limits, the shopper's measurements, strikes, the seal and its
    carts, the issuer's key, the reader switch and the chat's memory. Pool, store answers and figures are read
    again from disk. Text checks are kept per sheet hash, so the ones run on the sheet as on disk show again.
    About 7 ms with the real pool."""
    with _lock:
        _s["reader"] = None
        _s["signing"] = None
        _load()
        receipts.start("reset")
        try:
            from signoff.agent import chat
            chat.forget()
        except Exception:  # noqa: BLE001
            pass
        obs.session(_s["sheet"]["id"])
        return _recompute(why="reset")
