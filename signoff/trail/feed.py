"""The run as one ordered feed, merged from records that already exist. Read-only: nothing here changes the app.

`collect()` reads every source in-process (each one guarded: a source that fails is an empty list and is named in
`sources`). `build(src)` is a pure function over what was collected, so tests feed it plain dicts.

An event exists only if a record does. Records of the same kind, between the same two lanes, about the same party,
that follow each other within GAP_S seconds are one event with a `count` (37 pages from one store are one mark, not
37); `duration_ms` is then the time from the first to the last of them. A record with its own measured duration
keeps it. Where no timing was recorded, `duration_ms` is null.
"""
import datetime
import re
import threading
import time

GAP_S = 90          # records of one kind closer together than this are one event
ITEMS = 30          # at most this many records are listed inside one event; the rest are counted in `more`

# The seven steps of the run, in order (the decision screen's stepper uses the same ids), and the five kinds
# of event: evidence (a fact from a source), reading (what the model concluded from it), check (what code
# computed), approval (a signed request and what it changed), action (a message sent out, a cart created).
STEP_IDS = ("list_read", "stores_searched", "pages_read", "checked", "picked", "signs", "carts")
KINDS = ("evidence", "reading", "check", "approval", "action")

# Who is on each end of an event. Labels are filled from the active sheet in `lanes()`.
LANE_IDS = ("approver", "shopper", "stores", "reader", "agent", "checks", "records")
# Services whose answer is a verdict, and the step that verdict belongs to. Every other service keeps or
# measures records; a message to one belongs to the step in progress when it was sent.
CHECKERS = {"senso": "checked", "persona": "signs"}
# The stores' three tools (UCP) and the step each one serves.
STORE_TOOL_STEP = {"search_catalog": "stores_searched", "ask_business": "pages_read", "create_cart": "carts"}

# A receipt by its type: (from, to, kind, step, mark). Step None: the step in progress when it was written.
# A type not listed is still a receipt: a check, on the agent's lane.
RECEIPT_PLACE = {
    "chain_started": ("records", "records", "check", None, "receipt"),
    "request_accepted": ("approver", "agent", "approval", "signs", "request"),
    "request_refused": ("approver", "agent", "approval", "signs", "request"),
    "limit_set": ("agent", "agent", "approval", "signs", "limit"),
    "strike": ("agent", "agent", "approval", "signs", "strike"),
    "unstrike": ("agent", "agent", "approval", "signs", "strike"),
    "signed": ("agent", "agent", "approval", "signs", "signature"),
    "shopper_fact": ("shopper", "agent", "evidence", None, "measurement"),
    "carts_created": ("agent", "stores", "action", "carts", "cart"),
    "carts_updated": ("agent", "stores", "action", "carts", "cart"),
    "reader_switched": ("agent", "reader", "action", None, "reader"),
}
# The agent's own tool calls, as logged with their measured time (signoff.obs.recent), by the last part of the
# name: (step, kind, one, many). A name not listed is an action in the step in progress, "<name> call".
TOOL_PLACE = {"figure_read": ("pages_read", "reading", "page read", "pages read"),
              "check_run": ("checked", "check", "check run", "check runs"),
              "search_catalog": ("stores_searched", "action", "search", "searches"),
              "ask_business": ("pages_read", "action", "question asked", "questions asked"),
              "create_cart": ("carts", "action", "cart request", "cart requests")}
# A receipt whose type is not in RECEIPT_PLACE is placed by who wrote it: (from, to, kind, step).
ACTOR_PLACE = {"issuer": ("approver", "agent", "approval", "signs"), "shopper": ("shopper", "agent", "evidence", None),
               "system": ("agent", "agent", "check", None)}
# Steps whose results outlive a reset (cached evidence and its reading). The other steps are worked out again
# for every run, so a record of theirs from before the current receipt chain began belongs to an earlier run.
KEPT_ACROSS_RESETS = {"list_read", "stores_searched", "pages_read"}
# The ledger's fact classes, in the order they are shown, with two words for each. A class the ledger adds later
# is shown by its own name. SEALED are the ones a model call is not meant to carry unless its job is to read them.
CLASS_WORDS = {"store_text": "page text", "product": "product name", "order": "the order", "limit": "limits",
               "home_measurement": "home measurements", "person": "people", "price": "prices"}
SEALED = ("limit", "home_measurement", "person")
# What a signed request carried, by its own `type`.
REQUEST_MARK = {"set_limit": "limit", "strike": "strike", "unstrike": "strike", "sign_sheet": "signature"}


def _plain(s) -> str:
    return str(s if s is not None else "").replace("_", " ").strip()


def _epoch(at, naive=datetime.timezone.utc):
    """Seconds since the epoch for an ISO time or a number; None when it cannot be read. A time written without
    a zone is taken as `naive` (the services that write such times write UTC)."""
    if isinstance(at, (int, float)) and not isinstance(at, bool):
        return float(at) / (1000.0 if at > 1e11 else 1.0)
    if not isinstance(at, str) or not at.strip():
        return None
    try:
        d = datetime.datetime.fromisoformat(at.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=naive)
    return d.timestamp()


def _iso(t) -> str:
    return datetime.datetime.fromtimestamp(t).astimezone().isoformat(timespec="milliseconds")


def _iso_duration_ms(text):
    """'PT1M31S' -> 91000. None when it is not an ISO 8601 duration."""
    m = re.fullmatch(r"PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?", str(text or ""))
    if not m or not any(m.groups()):
        return None
    h, mi, s = (float(g) if g else 0.0 for g in m.groups())
    return int(round((h * 3600 + mi * 60 + s) * 1000))


def _money(cents) -> str:
    return "$%.2f" % (cents / 100.0) if isinstance(cents, (int, float)) and not isinstance(cents, bool) else ""


def _scalars(detail) -> str:
    """A receipt's small detail as words: its scalar fields in the order they were written; long hashes cut."""
    if not isinstance(detail, dict):
        return ""
    parts = []
    for k, v in detail.items():
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            continue
        if isinstance(v, str) and len(v) > 16 and re.fullmatch(r"[0-9a-f]+", v):
            v = v[:8]
        parts.append("%s %s" % (_plain(k), v))
    return " · ".join(parts)


def lanes(state: dict) -> list:
    sheet = (state or {}).get("sheet") or {}
    issuer, shopper = sheet.get("issuer") or {}, sheet.get("shopper") or {}
    stores = sheet.get("stores") or []
    reader = ((state or {}).get("readers") or {}).get("reference") or ""
    named = {
        "approver": (issuer.get("name") or "Approver", issuer.get("role_label") or ""),
        "shopper": (shopper.get("name") or "Shopper", shopper.get("role_label") or ""),
        "stores": ("Stores", "%d" % len(stores) if stores else ""),
        "reader": ("Reading model", reader.split(":")[-1]),
        "agent": ("Agent", ""),
        "checks": ("Checks", ""),
        "records": ("Records", ""),
    }
    return [{"id": i, "label": named[i][0], "sub": named[i][1]} for i in LANE_IDS]


def _service(row: dict) -> str:
    return str(row.get("recipient") or "").split(":")[0].lower()


def _lane_of(row: dict) -> str:
    kind = row.get("kind")
    if kind == "store":
        return "stores"
    if kind == "model":
        return "reader"
    return "checks" if _service(row) in CHECKERS else "records"


def _message_step(row: dict, lane: str, facts: list):
    """The step an outbound message serves; None means the step in progress when it was sent."""
    if lane == "stores":
        return STORE_TOOL_STEP.get(row.get("purpose"))
    if lane == "reader":   # a model call: reading the order, reading store text, or (the chat) neither
        return "list_read" if "order" in facts else ("pages_read" if "store_text" in facts else None)
    return CHECKERS.get(_service(row))


def _yes(v):
    """True, False or None from a record's flag, without turning a missing flag into a no."""
    return v if isinstance(v, bool) else None


def _span(low, high, value) -> str:
    if isinstance(low, (int, float)) and isinstance(high, (int, float)) and low != high:
        return "%g to %g" % (low, high)
    return "%g" % value if isinstance(value, (int, float)) and not isinstance(value, bool) else ""


def _atoms(src: dict) -> list:
    """One atom per record. A record with no time of its own is kept, without a time, in the step it belongs to."""
    out = []

    def add(at, step, kind, mark, lane, to_lane, one, many, **more):
        t = _epoch(at)
        if t is None and step is None:
            return
        out.append({"t": t, "step": step, "kind": kind, "mark": mark, "lane": lane, "to_lane": to_lane,
                    "one": one, "many": many, "detail": "", "ref": None, "duration_ms": None, "verified": None,
                    "stopped": False, "facts": [], "source": "", "group": None, "units": 1, "item": {}, "proof": None,
                    **more})

    state = src.get("state") or {}
    sheet = state.get("sheet") or {}

    # the order: each sentence the limits were read from (evidence), and each limit as read (reading)
    o = state.get("order") or {}
    for line in sheet.get("lines") or []:
        for lim in line.get("limits") or []:
            f = lim.get("from_order")
            if not isinstance(f, dict):
                continue
            add(o.get("derived_at"), "list_read", "evidence", "order", "approver", "agent", "order sentence",
                "order sentences", detail=o.get("title") or "", ref=f.get("doc"), source="order", facts=["order"],
                group=("order_sentence",), verified=_yes(f.get("span_found_in_text")), proof="quoted in the order",
                item={"title": line.get("need") or "", "quote": f.get("quote") or "", "source": f.get("doc"),
                      "at": o.get("derived_at")})
            value = " ".join(x for x in (_span(None, None, f.get("value")), f.get("unit") or lim.get("unit") or "") if x) \
                if f.get("value") is not None else "(%s)" % ((f.get("measurement") or {}).get("label") or "a measurement")
            add(o.get("derived_at"), "list_read", "reading", "limit", "reader", "agent", "limit read", "limits read",
                detail=str(f.get("extractor") or "").split(":")[-1], source="order", group=("order_limit",),
                verified=_yes(f.get("matches")), proof="match the sheet",
                item={"title": " ".join(x for x in (lim.get("label") or lim.get("name") or "", value) if x),
                      "quote": f.get("quote") or "", "about": line.get("need") or "", "by": f.get("extractor")})

    # per line: pages and answers from the stores (evidence), figures (reading), comparisons and the pick (check)
    pages, answers, figures = {}, {}, {}
    for line in state.get("lines") or []:
        need, cands = line.get("need") or line.get("line_id") or "", line.get("candidates") or []
        for c in cands:
            p = c.get("product") or {}
            if p.get("fetched_at"):
                pages.setdefault((p.get("store"), p.get("product_id")), p)
            for a in c.get("asked") or []:
                if a.get("asked_at"):
                    answers.setdefault((p.get("store"), a.get("asked_at"), a.get("question")), (p, a))
            for f in c.get("figures") or []:
                figures.setdefault((line.get("line_id"), p.get("store"), p.get("product_id"), f.get("figure")), (need, p, f))
        if cands:
            tally = {}
            for c in cands:
                tally[c.get("status")] = tally.get(c.get("status"), 0) + 1
            priced = sorted(cands, key=lambda c: (c.get("product") or {}).get("price_cents") or 0)
            add(None, "checked", "check", "comparison", "agent", "agent", "product checked", "products checked",
                units=len(cands), source="checks", group=("checked", line.get("line_id")),
                detail=" · ".join([need] + ["%d %s" % (n, _plain(st)) for st, n in sorted(tally.items(), key=lambda kv: -kv[1])]),
                items=[{"title": (c.get("product") or {}).get("title") or "", "status": _plain(c.get("status")),
                        "quote": c.get("reason") or "; ".join(str(k.get("expr") or "") for k in c.get("checks") or []),
                        "source": (c.get("product") or {}).get("store"), "link": (c.get("product") or {}).get("url"),
                        "price": _money((c.get("product") or {}).get("price_cents"))} for c in priced])
            pick = next((c for c in cands if c.get("id") and c.get("id") == line.get("pick")), None)
            why = line.get("why") or {}
            if pick:
                p = pick.get("product") or {}
                add(None, "picked", "check", "pick", "agent", "agent", "%s picked" % need.capitalize(), "",
                    detail=" · ".join(x for x in (_money(p.get("price_cents")), p.get("store") or "") if x), source="pick",
                    item={"title": p.get("title") or "", "quote": _plain(why.get("rule")), "source": p.get("store"),
                          "link": p.get("url"), "price": _money(p.get("price_cents"))})
            else:
                add(None, "picked", "check", "pick", "agent", "agent", "%s not picked" % need.capitalize(), "",
                    detail=str(line.get("reason") or _plain(line.get("status"))), source="pick",
                    item={"title": need, "quote": str(line.get("reason") or "")})
    for (store, _), p in pages.items():
        add(p["fetched_at"], "stores_searched", "evidence", "page", "stores", "agent", "page", "pages",
            detail=store or "", source="pool", facts=["store_text"], group=("page", store),
            item={"title": p.get("title") or "", "source": store, "link": p.get("url"),
                  "price": _money(p.get("price_cents")), "at": p.get("fetched_at")})
    for (store, _, _), (p, a) in answers.items():
        found = bool(a.get("answered")) and a.get("start") is not None
        add(a["asked_at"], "pages_read", "evidence", "answer", "stores", "agent", "answer", "answers",
            detail=store or "", source="asked", facts=["store_text"], group=("answer", store),
            verified=True if found else None, proof="stated, quote found",
            item={"title": a.get("question") or "", "quote": a.get("quote") or a.get("reply") or "",
                  "about": p.get("title") or "", "source": store, "at": a.get("asked_at")})
    for a in state.get("store_answers") or []:
        if a.get("asked_at"):
            add(a["asked_at"], "pages_read", "evidence", "answer", "stores", "agent", "answer", "answers",
                detail=a.get("store") or "", source="store_answers", facts=["store_text"],
                group=("answer", a.get("store")),
                item={"title": a.get("question") or "", "quote": a.get("answer") or "", "source": a.get("store"),
                      "at": a.get("asked_at")})
    for (_, store, _, _), (need, p, f) in figures.items():
        found = _yes(f.get("span_found_in_text"))
        add(f.get("read_at"), "pages_read", "reading", "figure", "reader", "agent", "figure read", "figures read",
            detail=need, source="figures", group=("figure", need),
            verified=None if f.get("unsure") else found, proof="quotes found in the text",
            item={"title": " ".join(x for x in (_plain(f.get("figure")) + ":", _span(f.get("low"), f.get("high"), f.get("value")),
                                                f.get("unit") or "") if x),
                  "quote": f.get("quote") or "", "about": p.get("title") or "", "source": store, "link": p.get("url"),
                  "by": f.get("extractor"), "status": "unsure" if f.get("unsure") else None,
                  "at": f.get("read_at"), "page_at": p.get("fetched_at")})

    # everything that left the process
    for r in src.get("egress") or []:
        lane = _lane_of(r)
        facts = [c for c in r.get("fact_classes") or [] if c != "none"]
        hits = r.get("sealed_hits") or []
        add(r.get("at"), _message_step(r, lane, facts) if _epoch(r.get("at")) is not None else None, "action", "message",
            "agent", lane, "message sent" if not r.get("blocked") else "message blocked",
            "messages sent" if not r.get("blocked") else "messages blocked", source="ledger", facts=facts,
            detail="%s · %s" % (r.get("recipient") or "", r.get("purpose") or ""), ref="ledger %s" % r.get("n"),
            group=("message", r.get("recipient"), r.get("purpose"), bool(r.get("blocked"))),
            stopped=bool(r.get("blocked")), verified=(not hits) if lane == "stores" else None, proof="carry no limit",
            item={"title": r.get("purpose") or "", "source": r.get("recipient"), "hash": r.get("payload_sha256"),
                  "bytes": r.get("bytes"), "ledger": r.get("n"), "facts": facts, "at": r.get("at"),
                  "declared": [c for c in r.get("declared_classes") or [] if c != "none"],
                  "found": r.get("sealed_found_in_payload") or [],
                  "parts": r.get("parts") or [], "withheld": r.get("withheld") or []})

    # the receipt chain
    chain = src.get("receipts") or []
    check = src.get("receipt_check")
    bad = (check or {}).get("first_bad")
    for r in chain:
        d = r.get("detail") if isinstance(r.get("detail"), dict) else {}
        actor = str(r.get("actor") or "")
        by_actor = ("checks", "agent", "check", CHECKERS[actor]) if actor in CHECKERS else ACTOR_PLACE.get(actor, ACTOR_PLACE["system"])
        lane, to_lane, kind, step, mark = RECEIPT_PLACE.get(r.get("type"), by_actor + ("receipt",))
        refused = bool(d.get("refused_because")) or d.get("accepted") is False
        words = _plain(r.get("type"))
        if mark == "request":
            mark = REQUEST_MARK.get(d.get("request"), "request")
            words = "%s %s" % (_plain(d.get("request")) or "request", "refused" if refused else "accepted")
        carts = d.get("carts") if isinstance(d.get("carts"), list) else None
        add(r.get("at"), step if _epoch(r.get("at")) is not None else None, kind, mark, lane, to_lane,
            words.capitalize(), "", source="receipt", units=len(carts) if carts else 1, stopped=refused,
            ref="receipt %s" % r.get("n"), detail=str(d.get("refused_because") or _scalars(d)),
            verified=(bad is None or r.get("n", 0) < bad) if check else None, proof="hash and link hold",
            item={"title": words, "receipt": r.get("n"), "hash": r.get("hash"), "prev_hash": r.get("prev_hash"),
                  "body_hash": r.get("body_hash"), "actor": r.get("actor"), "key_id": r.get("key_id")})

    # the agent's tool calls, each with the time it took
    for c in src.get("tools") or []:
        name = str(c.get("name") or "tool").split(".")[-1]
        words = _plain(name)
        step, kind, one, many = TOOL_PLACE.get(name, (None, "action", words + " call", words + " calls"))
        ok, ms = c.get("success") is not False, c.get("duration_ms")
        add(c.get("at"), step if _epoch(c.get("at")) is not None else None, kind, "tool", "agent", "agent",
            one if ok else one + " failed", many if ok else many + " failed", source="tools",
            detail="measured" if ok else str(c.get("error") or "failed"), stopped=not ok, group=("tool", c.get("name"), ok),
            duration_ms=int(round(ms)) if isinstance(ms, (int, float)) and not isinstance(ms, bool) else None,
            item={"title": _plain(c.get("name")), "status": None if ok else "failed", "quote": str(c.get("error") or ""),
                  "at": c.get("at"), "ms": ms})

    # the reader gate's changes
    for h in (src.get("gate") or {}).get("history") or []:
        add(h.get("at"), None, "action", "gate", "records", "agent",
            "Reader gate %s" % ("on" if h.get("value") else "off"), "", detail=_plain(h.get("arm")), source="gate",
            item={"title": "reader: %s" % _plain(h.get("arm"))})

    # Senso's verdicts on the sheet's sentences
    s = src.get("senso") or {}
    checks = s.get("checks") or []
    if checks:
        ok = sum(1 for c in checks if c.get("verdict") == "verified")
        add(s.get("ran_at"), "checked", "check", "verdict", "checks", "agent", "verdict", "verdicts", units=len(checks),
            source="senso", detail="Senso · %d of %d verified" % (ok, len(checks)),
            ref=("sheet %s" % s["for_hash"][:8]) if s.get("for_hash") else None, facts=["order"],
            items=[{"title": c.get("sentence") or "", "quote": c.get("quote") or "", "status": c.get("verdict"),
                    "source": "Senso", "run": c.get("run_id")} for c in checks])

    # that a person, not the agent, tapped Sign (Relay). Persona's inquiry results are receipts in the chain.
    rl = src.get("relay") or {}
    if rl.get("claim_type"):
        add(rl.get("at"), "signs", "check", "identity", "checks", "agent",
            _plain(rl.get("claim_type")).capitalize(), "", source="relay",
            detail="%s%s" % (_plain(rl.get("result")), " · sandbox" if rl.get("sandbox") else ""),
            item={"title": _plain(rl.get("claim_type")), "status": _plain(rl.get("result")), "source": "Persona Relay"})

    # Airbyte's jobs
    last = (src.get("airbyte") or {}).get("last") or {}
    for j in last.get("jobs") or []:
        rows = j.get("rows_synced")
        add(last.get("finished_at"), None, "action", "sync", "records", "agent", "row synced", "rows synced",
            units=rows if isinstance(rows, int) and not isinstance(rows, bool) and rows > 0 else 1, source="airbyte",
            detail="Airbyte · %s" % _plain(j.get("stream")), ref="airbyte job %s" % j.get("job_id"),
            duration_ms=_iso_duration_ms(j.get("duration")), stopped=j.get("status") != "succeeded",
            item={"title": _plain(j.get("stream")), "status": j.get("status"), "source": "Airbyte",
                  "copied": j.get("rows_copied_to_singlestore")})

    # carts, as the stores returned them
    for c in (state.get("seal") or {}).get("carts") or []:
        made = bool(c.get("cart_url"))
        add(c.get("created_at"), "carts", "action", "cart", "stores", "agent", "Cart created" if made else "Cart pending",
            "", detail=" · ".join(x for x in (c.get("store") or "", _money(c.get("total_cents")), c.get("mode") or "") if x),
            ref=c.get("cart_id"), source="cart", facts=["price"],
            item={"title": c.get("store") or "", "source": c.get("store"), "link": c.get("cart_url"),
                  "price": _money(c.get("total_cents"))})
    return out


def _class(c) -> dict:
    return {"id": c, "label": CLASS_WORDS.get(c) or _plain(c)}


def _context(rows: list, classes=()) -> dict:
    """What a set of outbound messages was given and not given, from their ledger rows alone.
    `given`: the fact classes the sender declared, with how many of the messages carried each. `found`: sealed values
    the ledger's code search met in the text sent although the sender declared none (a page that states the same
    number as a limit shows here; the ledger cannot tell that from a limit that was added). `not_given`: the ledger's
    other classes, absent from every message. `parts` and `withheld` are the sender's own lists when it wrote them."""
    order = list(CLASS_WORDS) + sorted(c for c in classes if c not in CLASS_WORDS and c != "none")
    given, found, parts, withheld = {}, {}, {}, {}
    for r in rows:
        for c in r.get("declared") or []:
            given[c] = given.get(c, 0) + 1
        seen = {}
        for hit in r.get("found") or []:
            cls, _, match = str(hit).partition(": ")
            if cls not in (r.get("declared") or []):
                seen.setdefault(cls, set()).add(match)
        for cls, matches in seen.items():
            slot = found.setdefault(cls, {"calls": 0, "matches": set()})
            slot["calls"] += 1
            slot["matches"] |= matches
        for part in r.get("parts") or []:
            if isinstance(part, dict) and part.get("name"):
                slot = parts.setdefault(str(part["name"]), {"calls": 0, "chars": []})
                slot["calls"] += 1
                if isinstance(part.get("chars"), (int, float)):
                    slot["chars"].append(part["chars"])
        for name in r.get("withheld") or []:
            withheld[str(name)] = withheld.get(str(name), 0) + 1
    sizes = sorted(r["bytes"] for r in rows if isinstance(r.get("bytes"), (int, float)) and not isinstance(r.get("bytes"), bool))
    known = [c for c in order if c in given] + sorted(c for c in given if c not in order)
    return {"calls": len(rows),
            "given": [dict(_class(c), calls=given[c]) for c in known],
            "found": [dict(_class(c), calls=v["calls"], matches=sorted(v["matches"])[:6]) for c, v in found.items()],
            "not_given": [_class(c) for c in order if c not in given and c not in found],
            "only": sum(1 for r in rows if not (set(r.get("declared") or []) | {str(h).partition(": ")[0] for h in r.get("found") or []}) & set(SEALED)),
            "bytes": {"min": sizes[0], "median": sizes[len(sizes) // 2], "max": sizes[-1], "total": sum(sizes)} if sizes else None,
            "parts": [{"name": k, "calls": v["calls"], "chars": sorted(v["chars"])[len(v["chars"]) // 2] if v["chars"] else None}
                      for k, v in parts.items()],
            "withheld": [{"name": k, "calls": v} for k, v in withheld.items()]}


def _events(atoms: list, run_started=None, classes=()) -> tuple:
    """Atoms in time order (those without a time after them). An atom with no step of its own takes the step in
    progress at its time (`own_step` false: it happened during the step; such records of one kind are one event per
    step however far apart, and their span is not a duration). Atoms that share a `group` and a step, and follow each other within GAP_S, are one event."""
    timed = sorted((a for a in atoms if a["t"] is not None), key=lambda a: a["t"])
    current = STEP_IDS[0]
    for a in timed:
        a["own_step"] = a["step"] is not None
        if a["step"] is None:
            a["step"] = current
        else:
            current = a["step"]
    # the run began with the receipt chain: exactly then, so a reset straight after a signed rehearsal shows none of it
    kept = [a for a in timed if run_started is None or a["t"] >= run_started or a["step"] in KEPT_ACROSS_RESETS]
    earlier = len(timed) - len(kept)
    open_groups, events = {}, []
    untimed = sorted((a for a in atoms if a["t"] is None), key=lambda a: STEP_IDS.index(a["step"]))   # by step; stable
    for a in kept + untimed:
        items = a.pop("items", None) or [a["item"]]
        key = (a["group"], a["step"]) if a["group"] else None
        g = open_groups.get(key) if key else None
        if g is not None and (a["t"] is None or g["_last"] is None or not g["own_step"] or a["t"] - g["_last"] <= GAP_S):
            g["count"] += a["units"]
            g["_last"] = a["t"] if a["t"] is not None else g["_last"]
            g["_items"].extend(items)
            g["_verified"].append(a["verified"])
            g["_measured"].append(a["duration_ms"])
            continue
        e = {k: a[k] for k in ("t", "step", "kind", "mark", "lane", "to_lane", "detail", "ref", "duration_ms",
                               "stopped", "facts", "source", "proof")}
        e["own_step"] = a.get("own_step", True)
        e.update(count=a["units"], _one=a["one"], _many=a["many"], _last=a["t"], _items=list(items),
                 _verified=[a["verified"]], _measured=[a["duration_ms"]])
        events.append(e)
        if key:
            open_groups[key] = e
    out = []
    for n, e in enumerate(events, 1):
        seen, items, one, many, last = e.pop("_verified"), e.pop("_items"), e.pop("_one"), e.pop("_many"), e.pop("_last")
        t, measured = e.pop("t"), [m for m in e.pop("_measured") if m is not None]
        spans = t is not None and last is not None and last > t
        if measured:                      # times that were measured add up
            e["duration_ms"] = sum(measured)
        elif spans and e["own_step"]:     # otherwise the time from the first record to the last
            e["duration_ms"] = int(round((last - t) * 1000))
        first = items[0] if items else {}
        out.append({"n": n, "at": _iso(t) if t is not None else None, "end_at": _iso(last) if spans else None,
                    "t": int(t * 1000) if t is not None else None, "step": e["step"], "own_step": e["own_step"],
                    "kind": e["kind"],
                    "mark": e["mark"], "lane": e["lane"], "to_lane": e["to_lane"],
                    "label": ("%d %s" % (e["count"], many if e["count"] != 1 else one)) if many else one,
                    "detail": e["detail"][:200], "ref": e["ref"], "duration_ms": e["duration_ms"], "count": e["count"],
                    "verified": False if False in seen else (True if seen and all(v is True for v in seen) else None),
                    "verified_count": sum(1 for v in seen if v is True) if any(v is not None for v in seen) else None,
                    "proof": e["proof"], "stopped": e["stopped"], "facts": e["facts"], "source": e["source"],
                    "receipt": first.get("receipt") if e["source"] == "receipt" else None,
                    "hash": first.get("hash") if e["source"] == "receipt" else None,
                    "timed": "measured" if measured else ("first to last" if e["duration_ms"] is not None else None),
                    "context": _context(items, classes) if e["source"] == "ledger" else None,
                    "_rows": items if e["source"] == "ledger" else None,
                    "items": items[:ITEMS], "more": max(0, len(items) - ITEMS)})
    return out, earlier


def _step_labels(state: dict) -> dict:
    issuer = (state.get("sheet") or {}).get("issuer") or {}
    who = str(issuer.get("role") or issuer.get("name") or "approver")   # the role, as the decision screen's stepper says it
    return {"list_read": "List read", "stores_searched": "Stores searched", "pages_read": "Pages read",
            "checked": "Checked", "picked": "Picked", "signs": "%s signs" % (who[:1].upper() + who[1:]), "carts": "Carts"}


def _step_subs(state: dict) -> dict:
    """Each step's few words, read from the state's own counts. A count that is not there gives no words."""
    sheet, counts, seal, order = (state.get(k) or {} for k in ("sheet", "counts", "seal", "order"))
    carts = [c for c in seal.get("carts") or [] if c.get("cart_url")]
    at = str(seal.get("signed_at") or "")[11:16]

    def n(value, one, many):
        return "%d %s" % (value, one if value == 1 else many) if isinstance(value, int) and not isinstance(value, bool) else ""

    return {"list_read": n(order.get("limits_derived"), "limit, quoted", "limits, quoted"),
            "stores_searched": n(len(sheet.get("stores") or []) or None, "store", "stores"),
            "pages_read": n(counts.get("products_found"), "page", "pages"),
            "checked": n(counts.get("inside_limits"), "inside", "inside"),
            "picked": _money(state.get("total_cents")) if counts.get("lines_ready") else "",
            "signs": ("signed %s" % at).strip() if seal.get("signed") else ("not signed" if state else ""),
            "carts": n(len(carts), "cart", "carts") if carts else ("none exist" if state else "")}


def _steps(events: list, state: dict, classes=()) -> list:
    labels, subs = _step_labels(state), _step_subs(state)
    seal = state.get("seal") or {}
    done = {"signs": bool(seal.get("signed")), "carts": any(c.get("cart_url") for c in seal.get("carts") or [])}
    out = []
    for i, step_id in enumerate(STEP_IDS, 1):
        mine = [e for e in events if e["step"] == step_id]
        timed = [e for e in mine if e["at"]]
        spans = [e["duration_ms"] for e in mine if e["duration_ms"] is not None and e["own_step"]]
        out.append({"id": step_id, "n": i, "label": labels[step_id], "sub": subs[step_id],
                    "done": done.get(step_id, any(not e["stopped"] for e in mine)),
                    "events": len(mine), "records": sum(len(e["items"]) + e["more"] for e in mine),
                    "kinds": {k: sum(1 for e in mine if e["kind"] == k) for k in KINDS},
                    "receipts": sum(1 for e in mine if e["receipt"] is not None),
                    "refused": sum(1 for e in mine if e["stopped"]),
                    "first_at": timed[0]["at"] if timed else None,
                    "last_at": (timed[-1]["end_at"] or timed[-1]["at"]) if timed else None,
                    "duration_ms": sum(spans) if spans else None,
                    # what this step's model calls were given, all of them together
                    "context": _context([r for e in mine if e["to_lane"] == "reader" for r in e["_rows"] or []], classes)
                    if any(e["to_lane"] == "reader" and e["_rows"] for e in mine) else None})
    return out


def _flow(state, steps, events, src, chain, check, bad) -> dict:
    """The replay's cards (signoff/trail/flow.py). A failure there leaves the timeline whole and names itself."""
    try:
        from signoff.trail import flow
        calls = {"model_calls": {"calls": sum((s.get("context") or {}).get("calls") or 0 for s in steps)}}
        return flow.build(state, steps, calls, src.get("talk"), src.get("memory"))
    except Exception as error:  # noqa: BLE001
        src.setdefault("sources", []).append({"id": "flow", "ok": False, "note": type(error).__name__})
        return None


def build(src: dict) -> dict:
    """The feed. `src` is what `collect()` returns; every key may be missing."""
    src = src or {}
    state = src.get("state") or {}
    chain = src.get("receipts") or []
    classes = src.get("egress_classes") or ()
    events, earlier = _events(_atoms(src), _epoch(chain[0].get("at")) if chain else None, classes)
    steps = _steps(events, state, classes)
    calls = [r for e in events if e["to_lane"] == "reader" for r in e["_rows"] or []]
    for e in events:
        e.pop("_rows")
    check = src.get("receipt_check") or {}
    bad = check.get("first_bad")
    held = len(chain) if check.get("verified") else (max(0, bad - 1) if isinstance(bad, int) else 0)
    eg = src.get("egress_summary") or {}
    sheet = state.get("sheet") or {}
    return {
        "sheet": {"id": sheet.get("id"), "title": sheet.get("title"), "invented": sheet.get("invented"),
                  "items": len(state.get("lines") or []), "total_cents": state.get("total_cents")},
        "mode": state.get("mode"),
        "state_version": state.get("version"),
        "signed": bool((state.get("seal") or {}).get("signed")),
        "signed_at": (state.get("seal") or {}).get("signed_at"),
        "kinds": list(KINDS),
        "lanes": lanes(state),
        "steps": steps,
        "events": events,
        "chain": [{"n": r.get("n"), "at": r.get("at"), "type": r.get("type"), "hash": r.get("hash"),
                   "prev_hash": r.get("prev_hash"), "verified": bool(check) and (bad is None or r.get("n", 0) < bad)}
                  for r in chain],
        "summary": {"events": len(events), "records": sum(len(e["items"]) + e["more"] for e in events),
                    "kinds": {k: sum(1 for e in events if e["kind"] == k) for k in KINDS},
                    "messages_out": eg.get("messages"), "to_stores": eg.get("to_stores"),
                    "limits_to_stores": eg.get("limits_in_store_messages"), "blocked": eg.get("blocked"),
                    "receipts": len(chain), "receipts_verified": held,
                    "model_calls": _context(calls, classes),
                    "earlier_runs": earlier},
        "flow": _flow(state, steps, events, src, chain, check, bad),
        "sources": src.get("sources") or [],
    }


# A source that asks a database is read at most every SLOW_S seconds, in the background after the first time,
# so the feed answers at the speed of memory. The value shown is the last one read.
SLOW_S = 20
_slow = {}
_slow_lock = threading.Lock()


def _held(name, fn):
    def refresh():
        try:
            value, error = fn(), None
        except Exception as e:  # noqa: BLE001
            value, error = None, e
        with _slow_lock:
            _slow[name].update(value=value, error=error, at=time.monotonic(), busy=False)

    with _slow_lock:
        slot = _slow.setdefault(name, {"value": None, "error": None, "at": None, "busy": False})
        first = slot["at"] is None and not slot["busy"]
        stale = slot["at"] is not None and time.monotonic() - slot["at"] > SLOW_S and not slot["busy"]
        if first or stale:
            slot["busy"] = True
    if first:
        refresh()
    elif stale:
        threading.Thread(target=refresh, daemon=True).start()
    with _slow_lock:
        if _slow[name]["error"] is not None:
            raise _slow[name]["error"]
        return _slow[name]["value"]


def collect() -> dict:
    """Every source, read in-process. Never raises: a source that fails is left out and named in `sources`."""
    src, sources = {}, []

    def read(name, fn):
        try:
            value = fn()
            sources.append({"id": name, "ok": True})
            return value
        except Exception as error:  # noqa: BLE001
            sources.append({"id": name, "ok": False, "note": type(error).__name__})
            return None

    def _state():
        from signoff.engine import state
        return state.get_state()

    def _receipts():
        from signoff.engine import receipts
        held = receipts.chain()["receipts"]
        src["receipt_check"] = receipts.check(held)
        return held

    def _egress():
        from signoff.obs import egress as ledger_module  # noqa: F401  (the package attribute is the function)
        from signoff.obs.egress import CLASSES, rows, summary
        rs = rows()
        src["egress_summary"] = summary(rs)
        src["egress_classes"] = sorted(CLASSES)
        return rs

    def _tools():
        from signoff import obs
        return obs.recent(2000)

    def _gate():
        from signoff.obs import gate
        return {"history": list(gate._s.get("history") or [])}

    def _senso():
        from signoff.sign import senso
        return senso.checks()

    def _relay():
        from signoff.relay import core
        return core.status()

    def _airbyte():
        from signoff.airbyte import api
        return api.status()

    for name, fn in (("state", _state), ("receipts", _receipts), ("egress", _egress), ("tools", _tools), ("gate", _gate),
                     ("senso", _senso), ("relay", _relay),
                     ("airbyte", lambda: _held("airbyte", _airbyte))):
        src[name] = read(name, fn)
    src["sources"] = sources
    return src
