"""What is remembered for a sheet at the start of a run. Read-only: it returns, the engine applies.

Everything returned is proved again from the records at the moment of recall, so a row put into a table by hand is
never recalled. The newest record wins: the last measurement of a fact, the last strike or unstrike of a product.
"""
import datetime

from signoff.memory import sources, store


def _when(text):
    try:
        return datetime.datetime.fromisoformat(str(text))
    except ValueError:
        return None


def age(at, now=None) -> dict:
    """`{seconds, text}` since `at`; the text is short ("2 h 41 min", "3 d")."""
    then = _when(at)
    if then is None:
        return {"seconds": None, "text": "time not recorded"}
    now = now or datetime.datetime.now(then.tzinfo)
    s = max(0, int((now - then).total_seconds()))
    if s < 3600:
        text = "%d min" % (s // 60)
    elif s < 86400:
        text = "%d h %d min" % (s // 3600, s % 3600 // 60)
    else:
        text = "%d d" % (s // 86400)
    return {"seconds": s, "text": text}


def _order(memory):
    source = memory["source"]
    return (str(memory["created_at"]), str(source.get("chain") or ""), source.get("n") or 0)


def _newest(memories, group):
    held = {}
    for m in sorted(memories, key=_order):
        held[group(m)] = m
    return list(held.values())


def _ref(m):
    return {"memory_id": m["id"], "source": m["source"], "text": m["text"]}


def _same_person(memory, person):
    """A memory with a known owner is recalled only for that same person; an owner no record names is left to the
    engine's own check (the fact id or the product must be on the sheet)."""
    return memory.get("owner_id") is None or memory["owner_id"] == (person or {}).get("id")


def select(sheet: dict, memories: list, now=None) -> dict:
    facts_used = {}
    for line in sheet.get("lines") or []:
        for limit in line.get("limits") or []:
            bound = limit.get("bound") or {}
            if bound.get("source") == "shopper" and bound.get("fact"):
                facts_used.setdefault(bound["fact"], []).append(limit["id"])
    on_sheet = {f["id"]: f for f in sheet.get("shopper_facts") or []}
    lines = {l["id"] for l in sheet.get("lines") or []}
    data_ids = {sheet.get("id"), sheet.get("data_from") or sheet.get("id")}

    facts = []
    mine = [m for m in memories if m["kind"] == "home_measurement" and _same_person(m, sheet.get("shopper"))]
    for m in _newest(mine, lambda m: m["key"]):  # the last measurement of each fact, whoever's record names the sheet
        fact = on_sheet.get(m["key"])
        if fact is None or m["value"].get("unit") != fact.get("unit"):
            continue
        facts.append(dict(_ref(m), fact_id=m["key"], value=m["value"]["value"], unit=m["value"]["unit"], by="shopper",
                          measured_by=m.get("owner_name") or "the shopper", measured_at=m["created_at"],
                          used_by=facts_used.get(m["key"], []), age=age(m["created_at"], now)))

    strikes = []
    mine = [m for m in memories if m["kind"] == "strike" and _same_person(m, sheet.get("issuer"))]
    for m in _newest(mine, lambda m: (m["key"], m["value"].get("line_id"))):  # the last strike or unstrike of each product
        if not m["value"].get("struck") or m["value"].get("line_id") not in lines:
            continue
        entry = dict(_ref(m), line_id=m["value"]["line_id"], product_key=m["key"], title=m["value"].get("title"),
                     reason=m["value"].get("reason"), by="issuer", by_name=m.get("owner_name"), at=m["created_at"],
                     age=age(m["created_at"], now))
        if not entry["reason"]:
            entry["reason_note"] = "the receipt does not keep the reason"
        strikes.append(entry)

    answers = []
    for m in _newest([m for m in memories if m["kind"] == "store_answer" and m["sheet_id"] in data_ids],
                     lambda m: (m["owner"], m["key"])):
        line_id = m["value"].get("line_id")
        if m["owner"] in (sheet.get("stores") or []) and (line_id is None or line_id in lines):
            answers.append(dict(_ref(m), store=m["owner"], key=m["key"], line_id=line_id, asked_at=m["created_at"],
                                age=age(m["created_at"], now)))

    purchases = [dict(_ref(m), signed_at=m["created_at"], total_cents=m["value"].get("total_cents"),
                      carts=m["value"].get("carts"), sheet_hash=m["key"], by_name=m.get("owner_name"))
                 for m in sorted(memories, key=_order)
                 if m["kind"] == "purchase" and m["sheet_id"] == sheet.get("id") and _same_person(m, sheet.get("issuer"))]
    n = len(facts) + len(strikes) + len(answers) + len(purchases)
    return {"sheet_id": sheet.get("id"), "facts": facts, "strikes": strikes, "store_answers": answers,
            "purchases": purchases, "counts": {"recalled": n, "of": len(memories)}}


def recall(sheet: dict) -> dict:
    """For the engine, at a reset or a switch of sheet. Never raises: a failure comes back as `error` with nothing recalled.
    Reads the records and the local mirror only (no network), and says so in `read_from`."""
    try:
        derived = store.sync(database=False)
        return dict(select(sheet or {}, derived["memories"]), read_from="records on disk, kept in the local mirror",
                    not_memories=len(derived["not_memories"]), error=None)
    except Exception as error:  # noqa: BLE001
        return {"sheet_id": (sheet or {}).get("id") if isinstance(sheet, dict) else None, "facts": [], "strikes": [],
                "store_answers": [], "purchases": [], "counts": {"recalled": 0, "of": 0}, "read_from": None,
                "error": "memory could not be read (%s); nothing was recalled" % type(error).__name__}


def for_line(sheet: dict, line_id: str, recalled: dict) -> dict:
    """What of `recalled` bears on one item, each entry with the reason it was recalled."""
    line = next((l for l in sheet.get("lines") or [] if l.get("id") == line_id), None)
    if line is None:
        return {"line_id": line_id, "error": "no line %r on this sheet" % (line_id,), "recalled": []}
    limits = {l["id"]: l for l in line.get("limits") or []}
    out = []
    for f in recalled["facts"]:
        mine = [limits[i] for i in f["used_by"] if i in limits]
        if mine:
            out.append(dict(f, kind="home_measurement", owner="shopper",
                            why="bounds \"%s\" on this item" % mine[0].get("name", mine[0]["id"])))
    out += [dict(s, kind="strike", owner="issuer", why="struck from this item before, by a signed request")
            for s in recalled["strikes"] if s["line_id"] == line_id]
    out += [dict(a, kind="store_answer", owner=a["store"],
                 why="asked about a product on this item" if a["line_id"] else "one of this order's stores")
            for a in recalled["store_answers"] if a["line_id"] in (None, line_id)]
    return {"line_id": line_id, "need": line.get("need"), "recalled": out,
            "counts": {"recalled": len(out), "of": recalled["counts"]["of"]}}
