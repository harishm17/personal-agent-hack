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


def build(state: dict, steps: list, summary: dict, talk=None, memory=None) -> dict:
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
    home = [{"who": shopper.get("name"), "label": f.get("label") or _plain(f.get("id")), "value": _num(f.get("value"), f.get("unit"))}
            for f in sheet.get("shopper_facts") or [] if f.get("id") in used]
    page = {"store": product.get("store"), "title": product.get("title"), "price": _money(product.get("price_cents")),
            "image": product.get("image_url"), "link": product.get("url"), "excerpt": _excerpt(figures)} if pick else None

    # what the model sees: one page and the meanings of the figures to look for
    names = [t.get("figure") for l in spec.get("limits") or [] for t in l.get("terms") or [] if t.get("figure")]
    meanings = [{"name": _plain(n), "text": (sheet.get("figures") or {}).get(n)} for n in dict.fromkeys(names)
                if (sheet.get("figures") or {}).get(n)]
    context = (next((s for s in steps if s.get("id") == "pages_read"), {}) or {}).get("context")
    readers = sorted({str(f.get("extractor") or "").split(":")[-1] for f in figures if f.get("extractor")})
    model = {"reader": ", ".join(readers), "calls": (summary.get("model_calls") or {}).get("calls"),
             "source": "ledger" if context and context.get("parts") else "prompt builder",
             "page": page["excerpt"] if page else [], "meanings": meanings,
             "quoted": [f.get("quote") for f in figures],
             "outside": ([w["name"] for w in context.get("withheld") or []] or [g["label"] for g in context.get("not_given") or []])
             if context else None,
             "found": [{"label": f["label"], "calls": f["calls"]} for f in (context or {}).get("found") or []]} if pick else None

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
        "asked": said, "talk": talk, "memory": memory,
    }
