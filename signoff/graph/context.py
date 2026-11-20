"""The event an order comes out of: `sheets/<sheet id>_context.json` (people, messages, facts quoted from them).

Read with the same discipline as a store's page: a fact is kept only if its quote is found in its message at the
stated offsets; anything else is dropped and listed. A fact may feed the sheet (`feeds`: a JSON pointer and a
verb); where a feed says `equals`, code compares the fact's value with the value at that pointer and reports
whether they match. A sheet without such a file has no event. Nothing here is keyed to one event's names.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def load(sheet_id, folder: pathlib.Path | None = None) -> tuple[dict | None, str]:
    """(the file's content or None, its path relative to the repo)."""
    name = "sheets/%s_context.json" % sheet_id
    path = (folder or ROOT / "sheets") / ("%s_context.json" % sheet_id)
    try:
        return json.loads(path.read_text()), name
    except (OSError, ValueError):
        return None, name


def at_pointer(doc, pointer: str):
    """The value at a JSON pointer, as (found, value)."""
    value = doc
    for token in [t for t in str(pointer).split("/") if t != ""]:
        if isinstance(value, list) and token.isdigit() and int(token) < len(value):
            value = value[int(token)]
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            return False, None
    return True, value


def _same(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-9
    return a == b


def read(context: dict | None, sheet: dict, file: str = "") -> dict | None:
    """The context with every fact checked against its message and every feed checked against the sheet."""
    if not isinstance(context, dict):
        return None
    messages = {m.get("id"): m for m in context.get("messages") or [] if isinstance(m, dict)}
    facts, dropped = [], []
    for i, f in enumerate(context.get("facts") or []):
        m = messages.get(f.get("source"))
        start, end, quote = f.get("start"), f.get("end"), f.get("quote")
        if m is None:
            dropped.append({"id": f.get("id"), "why": "no such message"})
            continue
        if not quote or not isinstance(start, int) or not isinstance(end, int) or (m.get("text") or "")[start:end] != quote:
            dropped.append({"id": f.get("id"), "why": "the quote is not in the message at the stated place"})
            continue
        feeds = []
        for feed in f.get("feeds") or []:
            found, value = at_pointer(sheet, feed.get("to"))
            matches = None
            if feed.get("equals"):
                matches = bool(found and _same(f.get("value"), value))
            feeds.append({"to": feed.get("to"), "verb": feed.get("verb"), "equals": bool(feed.get("equals")),
                          "found": found, "matches": matches, "sheet_value": value if feed.get("equals") else None})
        facts.append(dict(f, feeds=feeds, index=i))
    return {"file": file, "invented": context.get("invented"), "event": context.get("event"),
            "people": context.get("people") or [], "messages": list(messages.values()), "facts": facts,
            "dropped": dropped, "classes": context.get("classes") or {}}
