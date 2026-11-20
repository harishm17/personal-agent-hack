"""The run of one item as a picture: what each party said (left), what the model sees (centre), what code
checked (right), then the message to the store's own agent and what is remembered.

`build(state, steps, summary, talk, memory)` is pure and returns only what a record supports. A part with no
record is None, and the page shows it as a quiet card that says so; nothing is invented.

One item of the sheet is followed (`focus`: the first item that has a pick, else the first). The store's page goes
into the model call. The issuer's limit and the home's measurement do not: they are compared with the quoted
figure in code (`bypass`), which is what the engine's check records say (`checks[].terms` and `checks[].bound`).

Until the outbound ledger's rows carry the prompt's `parts`, what the frame holds is what the reader's prompt is
built from (`signoff/extract/reader.py:prompt_for`: the figures' meanings and the page's text), and `model.source`
says "prompt builder" instead of "ledger".
"""

OPS = {">=": "≥", "<=": "≤", "==": "="}
OP_WORDS = {">=": "at least", "<=": "at most", "==": "exactly"}


def _money(cents) -> str:
    return "$%.2f" % (cents / 100.0) if isinstance(cents, (int, float)) and not isinstance(cents, bool) else ""


def _num(value, unit="") -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return ""
    return ("%g %s" % (value, unit or "")).strip()


def _plain(s) -> str:
    return str(s if s is not None else "").replace("_", " ").strip()


def _excerpt(figures: list) -> list:
    """The page's own sentences that state the figures, each with where its quote sits: [{text, quote: [a, b]}]."""
    out, seen = [], set()
    for f in figures:
        text, span = f.get("sentence") or f.get("quote") or "", f.get("quote_in_sentence")
        if not text or (text, tuple(span or ())) in seen:
            continue
        seen.add((text, tuple(span or ())))
        out.append({"text": text, "quote": span if isinstance(span, list) and len(span) == 2 else [0, len(text)]})
    return out


def _guard(messages, product_id):
    """One real message to a store's agent, for the guard row: the one about this product in which the guard removed
    the most (so the line it stops things at is seen), else the first about it, else the first of all."""
    messages = [m for m in messages or [] if isinstance(m, dict) and m.get("draft")]
    if not messages:
        return None
    mine = [m for m in messages if (m.get("product") or {}).get("id") == product_id] or messages
    m = max(mine, key=lambda m: len(m.get("removed") or []))
    reply = m.get("reply") if isinstance(m.get("reply"), dict) else {}
    return {"store": m.get("store"), "origin": m.get("origin"), "at": str(m.get("at") or "")[11:16],
            "draft": m.get("draft"), "decision": _plain(m.get("decision")), "why": m.get("why"), "sent": m.get("sent"),
            "removed": [{"text": r.get("text"), "mark": r.get("mark") or _plain(r.get("class"))} for r in m.get("removed") or []],
            "left": [l.get("mark") or _plain(l.get("class")) for l in m.get("left") or []],
            "reply": reply.get("text") or "", "messages": len(messages),
            "stopped": sum(len(k.get("removed") or []) for k in messages)}


def _shelf(shelf, sheet=None):
    """Memory's four owner slots, each with what a new run would recall: [{slot, owner, label, items: [{text, age}], count}].
    A remembered measurement is worded from the sheet: its own label, value and unit, and the name of who measured."""
    if not isinstance(shelf, list) or not shelf:
        return None
    sheet = sheet or {}
    facts = {f.get("id"): f for f in sheet.get("shopper_facts") or []}
    who = (sheet.get("shopper") or {}).get("name")

    def words(item):
        f = facts.get(item.get("key"))
        if not f:
            return item.get("text") or ""
        label = str(f.get("label") or _plain(f.get("id")))
        return "%s: %s%s" % (label[:1].upper() + label[1:], _num(f.get("value"), f.get("unit")), " · %s measured" % who if who else "")

    out = []
    for slot in shelf:
        items = slot.get("items") or []
        name = slot.get("name")
        label = {"stores": "Each store's", "bought": "Bought"}.get(slot.get("slot")) or ("%s's" % name if name else _plain(slot.get("slot")))
        out.append({"slot": slot.get("slot"), "owner": "store" if slot.get("slot") == "stores" else slot.get("owner"), "label": label,
                    "count": len(items), "keys": [i.get("key") for i in items if i.get("key")],
                    "items": [{"text": words(i)} for i in items[:2]]})   # no ages: they change by the minute, the picture does not
    return out


def _read_record(events, extractors):
    """The ledger's record of the calls to the readers that read this product's figures (the ledger's recipient is
    the figure's `extractor`), joined: what every such call was given, and what none of them was."""
    mine = [e["context"] for e in events or [] if e.get("context") and e.get("to_lane") == "reader"
            and str(e.get("detail") or "").split(" · ")[0] in extractors]
    if not mine:
        return None
    labels = lambda c, key: [g["label"] for g in c.get(key) or []]
    outside = [l for l in labels(mine[0], "not_given") if all(l in labels(c, "not_given") for c in mine)]
    found = {}
    for c in mine:
        for hit in c.get("found") or []:
            found[hit["label"]] = found.get(hit["label"], 0) + hit["calls"]
    return {"calls": sum(c.get("calls") or 0 for c in mine),
            "parts": [p["name"] for c in mine[:1] for p in c.get("parts") or []],
            "outside": [w["name"] for c in mine[:1] for w in c.get("withheld") or []] or outside,
            "found": [{"label": k, "calls": v} for k, v in found.items()]}


def _never_enters(events) -> str:
    """What the limit and the measurement never enter, as far as the ledger's rows go. "a model call" only when
    the ledger has model calls and none of them was given, or was found to hold, a limit or a home measurement.
    Otherwise the claim is about the page-reading call alone (the call the frame shows), which is how its prompt is
    built: another call, such as the one that reads the order, does receive the limit."""
    calls = [e["context"] for e in events or [] if e.get("context") and e.get("to_lane") == "reader"]
    sealed = {"limit", "home_measurement"}
    held = any(g.get("id") in sealed for c in calls for g in (c.get("given") or []) + (c.get("found") or []))
    return "a model call" if calls and not held else "the page-reading call"


def build(state: dict, steps: list, events: list, talk=None, memory=None) -> dict:
    state = state or {}
    sheet, seal = state.get("sheet") or {}, state.get("seal") or {}
    lines = state.get("lines") or []
    if not lines:
        return None
    focus = next((l for l in lines if l.get("pick")), lines[0])
    spec = next((l for l in sheet.get("lines") or [] if l.get("id") == focus.get("line_id")), {})
    cands = focus.get("candidates") or []
    pick = next((c for c in cands if c.get("id") and c.get("id") == focus.get("pick")), None)
    product = (pick or {}).get("product") or {}
    figures = [f for f in (pick or {}).get("figures") or [] if f.get("quote")]
    issuer, shopper = sheet.get("issuer") or {}, sheet.get("shopper") or {}
    limits = [l for l in spec.get("limits") or [] if isinstance(l.get("from_order"), dict)]

    # what each party said
    order = {"who": issuer.get("name"), "role": issuer.get("role_label") or issuer.get("role"),
             "sentences": [{"text": l["from_order"].get("quote") or "", "marked": l["from_order"].get("value") is not None}
                           for l in limits if l["from_order"].get("quote")]}
    used = {(l.get("bound") or {}).get("fact") for l in spec.get("limits") or []} | \
           {t.get("fact") for l in spec.get("limits") or [] for t in l.get("terms") or []}
    shelf = _shelf(memory, sheet)
    recalled = {k for slot in shelf or [] if slot["slot"] == "shopper" for k in slot["keys"]}
    home = [{"who": shopper.get("name"), "label": f.get("label") or _plain(f.get("id")), "value": _num(f.get("value"), f.get("unit")),
             "recalled": f.get("id") in recalled}
            for f in sheet.get("shopper_facts") or [] if f.get("id") in used]
    page = {"store": product.get("store"), "title": product.get("title"), "price": _money(product.get("price_cents")),
            "image": product.get("image_url"), "link": product.get("url"), "excerpt": _excerpt(figures)} if pick else None

    # what the model sees: one page and the meanings of the figures to look for
    names = [t.get("figure") for l in spec.get("limits") or [] for t in l.get("terms") or [] if t.get("figure")]
    meanings = [{"name": _plain(n), "text": (sheet.get("figures") or {}).get(n)} for n in dict.fromkeys(names)
                if (sheet.get("figures") or {}).get(n)]
    extractors = sorted({str(f.get("extractor")) for f in figures if f.get("extractor")})
    record = _read_record(events, extractors)
    model = {"reader": ", ".join(e.split(":")[-1] for e in extractors), "calls": record["calls"] if record else 0,
             "source": "ledger" if record and record["parts"] else "prompt builder",
             "page": page["excerpt"] if page else [], "meanings": meanings,
             "quoted": [f.get("quote") for f in figures],
             "outside": record["outside"] if record else None,
             "found": record["found"] if record else [],
             "never_enters": _never_enters(events)} if pick else None

    # what goes round the model and is compared in code
    checks, bypass = [], []
    for c in (pick or {}).get("checks") or []:
        terms, bound = c.get("terms") or [], c.get("bound") or {}
        left = terms[0] if len(terms) == 1 else {}
        unit = bound.get("unit") or left.get("unit") or ""
        margin = c.get("margin")
        checks.append({"left": {"owner": left.get("owner") or "store", "text": _num(c.get("lhs"), left.get("unit") or unit)},
                       "op": OPS.get(c.get("op"), str(c.get("op") or "")),
                       "right": {"owner": bound.get("owner"), "text": _num(bound.get("value"), unit)},
                       "ok": c.get("pass"), "name": c.get("name") or "",
                       "margin": ("%s to spare" % _num(abs(margin), unit)) if c.get("pass") and isinstance(margin, (int, float)) else ""})
        words = OP_WORDS.get(c.get("op"), "") if bound.get("owner") == "issuer" else ""
        bypass.append({"owner": bound.get("owner"), "text": " ".join(x for x in (words, _num(bound.get("value"), unit)) if x)})

    # the cheaper product that was refused, the pick, the signature
    price = product.get("price_cents")
    cheaper = [c for c in cands if isinstance(price, (int, float)) and c.get("status") != "inside"
               and isinstance((c.get("product") or {}).get("price_cents"), (int, float)) and c["product"]["price_cents"] < price]
    nearest = max(cheaper, key=lambda c: c["product"]["price_cents"]) if cheaper else None
    refused = {"price": _money(nearest["product"]["price_cents"]), "title": nearest["product"].get("title"),
               "reason": str(nearest.get("reason") or _plain(nearest.get("status"))).split(": ")[-1],
               "more": len(cheaper) - 1} if nearest else None
    picked = {"price": _money(price), "title": product.get("title"),
              "rule": _plain((focus.get("why") or {}).get("rule")) or ""} if pick else None
    carts = [c for c in seal.get("carts") or [] if c.get("cart_url")]
    signature = {"who": issuer.get("name"), "signed": bool(seal.get("signed")),
                 "text": ("signed %s · %d cart%s" % (str(seal.get("signed_at") or "")[11:16], len(carts), "" if len(carts) == 1 else "s"))
                 if seal.get("signed") else "not signed · no cart exists",
                 "carts": [{"store": c.get("store"), "link": c.get("cart_url"), "total": _money(c.get("total_cents"))} for c in carts]}

    # the question our agent put to the store's own agent, and the store's words back (the pick's own records)
    asked = next((a for a in (pick or {}).get("asked") or [] if a.get("question")), None)
    said = {"store": product.get("store"), "question": asked.get("question"), "at": str(asked.get("asked_at") or "")[11:16],
            "reply": asked.get("quote") or asked.get("reply") or ""} if asked else None

    return {
        "title": " · ".join(x for x in (sheet.get("title"), focus.get("need")) if x),
        "focus": {"line_id": focus.get("line_id"), "need": focus.get("need"), "others": max(0, len(lines) - 1)},
        "rail": [{"id": s["id"], "label": s["label"], "sub": s["sub"], "done": s["done"]} for s in steps],
        "said": {"order": order if order["sentences"] else None, "home": home, "page": page},
        "model": model, "bypass": bypass, "checks": checks, "refused": refused, "pick": picked, "signature": signature,
        "asked": said, "talk": _guard(talk, product.get("product_id")), "memory": shelf,
    }
