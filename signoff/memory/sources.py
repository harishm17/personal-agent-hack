"""What may become a memory: only a record that already exists.

Three kinds of record are read, and nothing else:
- a receipt in a chain file under data/receipts/ whose chain recomputes (every hash and link);
- an entry in a saved store-answer file under data/**/store_answers/;
- a turn of a saved conversation with a store's own agent under data/talk/threads/ in which the store replied
  (only the store's reply is remembered; what our agent drafted or sent is never a memory).

`derive()` turns every such record into the memories it proves; `prove(source)` does the same for one named
record. No model text is read here and no model is called.
"""
import json
import pathlib

from signoff.engine import receipts

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SHEETS = ROOT / "sheets"
_cache = {}


class Refused(ValueError):
    """A memory that no record proves. `code` is short and stable; the message says what is missing."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _rel(path) -> str:
    path = pathlib.Path(path)
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _cached(path: pathlib.Path, load):
    """`load(path)` once per version of the file (mtime and size)."""
    try:
        stat = path.stat()
    except OSError:
        return None
    stamp = (stat.st_mtime_ns, stat.st_size)
    held = _cache.get(str(path))
    if held is None or held[0] != stamp:
        try:
            held = (stamp, load(path))
        except (OSError, ValueError):
            held = (stamp, None)
        _cache[str(path)] = held
    return held[1]


def _json(path):
    return json.loads(path.read_text())


def _jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sheet(sheet_id) -> dict:
    return (_cached(SHEETS / ("%s.json" % sheet_id), _json) or {}) if sheet_id else {}


def _pool_rows() -> list:
    """The few fields memory needs of every product in the saved pools (read once per version of each file)."""
    from signoff.store import sheetctx
    keep = ("store", "product_id", "product_key", "title", "line_ids")
    out = []
    for folder in sheetctx.all_pool_dirs():
        for path in sorted(folder.glob("*.json")):
            out += _cached(path, lambda f: [{k: p.get(k) for k in keep} for p in _json(f) if isinstance(p, dict)]) or []
    return out


def _titles() -> dict:
    """product_key -> title, from the saved pools. Used only to write a memory's sentence."""
    out = {}
    for p in _pool_rows():
        if p["product_key"]:
            out.setdefault(p["product_key"], p["title"])
    return out


# --- receipts -------------------------------------------------------------------------------------------------

def chains() -> dict:
    """Every chain file on disk: `{chain id: {id, file, receipts, verified}}`. A chain kept in memory only has no
    record on disk and yields no memory; a run that keeps no receipts on disk (SIGNOFF_RECEIPTS=memory) reads none."""
    out = {}
    if not receipts._to_disk():
        return out
    for path in sorted(receipts.FOLDER.glob("*.jsonl")) if receipts.FOLDER.is_dir() else []:
        held = _cached(path, _jsonl)
        if held is None:
            out[path.stem] = {"id": path.stem, "file": _rel(path), "receipts": [], "verified": False}
            continue
        out[path.stem] = {"id": path.stem, "file": _rel(path), "receipts": held,
                          "verified": bool(held) and receipts.check(held)["verified"]}
    return out


def sheet_of(chain: dict, every: dict):
    """The sheet a chain is about: named in its first receipt, else in the chain it follows. None when no record says."""
    seen = set()
    while chain and chain["id"] not in seen and chain["receipts"]:
        seen.add(chain["id"])
        detail = chain["receipts"][0].get("detail") or {}
        if detail.get("sheet_id"):
            return str(detail["sheet_id"])
        reason = str(detail.get("reason") or "")
        if reason.startswith("sheet "):
            return reason[len("sheet "):]
        chain = every.get(((detail.get("previous") or {}).get("chain")))
    return None


def _signed_request(chain, receipt, kind, same):
    """The receipt of the verified signed request behind `receipt`: accepted, same key, same request, same fields."""
    if receipt.get("actor") != "issuer" or not receipt.get("key_id"):
        return None
    for other in chain["receipts"]:
        detail = other.get("detail") or {}
        if (other.get("type") == "request_accepted" and other.get("n", 0) > receipt["n"] and detail.get("accepted") is True
                and other.get("key_id") == receipt["key_id"] and detail.get("request") == kind
                and all(detail.get(k) == v for k, v in same.items())):
            return other
    return None


def _money(cents) -> str:
    return "$%.2f" % (cents / 100) if isinstance(cents, (int, float)) and not isinstance(cents, bool) else "an unstated sum"


def _from_receipt(chain, receipt, sheet_id):
    """The memory one receipt proves, or a Refused that says why it proves none. None for receipts that are not memories."""
    kind, detail = receipt.get("type"), receipt.get("detail") or {}
    sheet = _sheet(sheet_id)
    source = {"type": "receipt", "chain": chain["id"], "n": receipt["n"], "hash": receipt["hash"], "file": chain["file"],
              "at": receipt["at"]}
    base = {"source": source, "created_at": receipt["at"], "sheet_id": sheet_id}
    if kind == "shopper_fact":
        if receipt.get("actor") != "shopper":
            raise Refused("wrong_actor", "a home measurement is the shopper's; this receipt is by %r" % receipt.get("actor"))
        who = sheet.get("shopper") or {}
        fact = next((f for f in sheet.get("shopper_facts") or [] if f.get("id") == detail.get("fact_id")), {})
        return dict(base, owner="shopper", owner_id=who.get("id"), owner_name=who.get("name"), kind="home_measurement",
                    key=detail.get("fact_id"), value={"value": detail.get("to"), "unit": detail.get("unit"), "was": detail.get("from")},
                    text="%s measured the %s: %s %s." % (who.get("name") or "The shopper", fact.get("label") or detail.get("fact_id"),
                                                         detail.get("to"), detail.get("unit") or ""))
    if kind in ("strike", "unstrike"):
        request = _signed_request(chain, receipt, kind, {"line_id": detail.get("line_id"), "product_key": detail.get("product_key")})
        if request is None:
            raise Refused("no_signed_request", "a strike is the approver's: receipt %d has no accepted signed request "
                          "with the same key behind it" % receipt["n"])
        who = sheet.get("issuer") or {}
        line = next((l for l in sheet.get("lines") or [] if l.get("id") == detail.get("line_id")), {})
        title = _titles().get(detail.get("product_key")) or detail.get("product_key")
        name, need = who.get("name") or "The approver", line.get("need") or detail.get("line_id")
        reason = detail.get("reason")
        text = ("%s struck %s from the %s%s." % (name, title, need, ": " + str(reason).rstrip(".") if reason else "")
                if kind == "strike" else "%s put %s back on the %s." % (name, title, need))
        return dict(base, owner="issuer", owner_id=who.get("id"), owner_name=who.get("name"), kind="strike",
                    key=detail.get("product_key"), text=text,
                    value={"struck": kind == "strike", "line_id": detail.get("line_id"), "product_key": detail.get("product_key"),
                           "reason": reason, "title": title},
                    source=dict(source, key_id=receipt["key_id"], signed_request={"n": request["n"], "hash": request["hash"]}))
    if kind == "signed":
        request = _signed_request(chain, receipt, "sign_sheet", {"sheet_hash": detail.get("sheet_hash")})
        if request is None:
            raise Refused("no_signed_request", "a signature is the approver's: receipt %d has no accepted signed request "
                          "with the same key behind it" % receipt["n"])
        who = sheet.get("issuer") or {}
        carts = next(((r.get("detail") or {}).get("carts") or [] for r in chain["receipts"]
                      if r.get("type") == "carts_created" and (r.get("detail") or {}).get("sheet_hash") == detail.get("sheet_hash")), [])
        return dict(base, owner="issuer", owner_id=who.get("id"), owner_name=who.get("name"), kind="purchase",
                    key=detail.get("sheet_hash"),
                    value={"sheet_hash": detail.get("sheet_hash"), "total_cents": detail.get("total_cents"),
                           "signer": detail.get("signer"), "carts": carts},
                    text="%s signed the order: %s, %d cart%s." % (who.get("name") or "The approver", _money(detail.get("total_cents")),
                                                                 len(carts), "" if len(carts) == 1 else "s"),
                    source=dict(source, key_id=receipt["key_id"], signed_request={"n": request["n"], "hash": request["hash"]}))
    return None


# --- saved store answers --------------------------------------------------------------------------------------

def answer_files() -> list:
    """(path, sheet id) of every saved store-answer file: the stores' own words, with the time asked."""
    from signoff.store import sheetctx
    out = []
    for folder in sheetctx.all_answer_dirs():
        sheet_id = "sheet1" if folder.parent == sheetctx.DATA else folder.parent.name
        out += [(path, sheet_id) for path in sorted(folder.glob("*.json")) + sorted((folder / "asked").glob("*.json"))]
    return out


def _from_answer(path, index, entry, sheet_id):
    """The memories one saved answer proves: one per quoted part, or one for a reply about a product."""
    store, asked_at = entry.get("store"), entry.get("asked_at")
    if not store or not asked_at:
        return []
    source = {"type": "file", "file": _rel(path), "index": index, "at": asked_at, "entry_hash": receipts.digest(entry)}
    base = {"owner": store, "owner_id": store, "owner_name": store, "kind": "store_answer", "source": source,
            "created_at": asked_at, "sheet_id": sheet_id}
    out = []
    for part, said in entry.items():
        if isinstance(said, dict) and said.get("quote"):
            out.append(dict(base, key=part, value=dict(said, question=entry.get("question")),
                            text="%s on %s: \"%s\"." % (store, part, str(said["quote"]).rstrip("."))))
    if entry.get("reply"):
        about = entry.get("title") or entry.get("product_id") or "a product"
        out.append(dict(base, key="%s:%s" % (entry.get("figure") or "reply", entry.get("product_id") or index),
                        value={k: entry.get(k) for k in ("question", "reply", "figure", "product_id", "title", "line_id")},
                        text="%s on %s: %s" % (store, about, entry["reply"])))
    return out


# --- saved conversations with a store's own agent ---------------------------------------------------------------

TALK = ROOT / "data" / "talk" / "threads"


def talk_files() -> list:
    return sorted(TALK.glob("*/*.json")) if TALK.is_dir() else []


def _lines_of_products() -> dict:
    """(store, product id) -> the line ids the saved pools put that product on."""
    out = {}
    for p in _pool_rows():
        out.setdefault((p["store"], p["product_id"]), set()).update(p["line_ids"] or [])
    return out


def _from_talk(path, thread):
    """One memory per turn in which the store's agent replied: the store's words, owned by the store."""
    store, out = thread.get("store"), []
    if not store:
        return out
    on_lines = sorted(_lines_of_products().get((store, thread.get("product_id")), ()))
    for turn in thread.get("turns") or []:
        if not isinstance(turn, dict) or not turn.get("reply") or not turn.get("reply_at"):
            continue
        source = {"type": "file", "file": _rel(path), "turn": turn.get("n"), "at": turn["reply_at"],
                  "entry_hash": receipts.digest(turn)}
        out.append({"owner": store, "owner_id": store, "owner_name": store, "kind": "store_answer", "source": source,
                    "created_at": turn["reply_at"], "sheet_id": thread.get("sheet"),
                    "key": "talk:%s:%s:%s" % (thread.get("product_id"), thread.get("id"), turn.get("n")),
                    "value": {"question": turn.get("sent"), "reply": turn["reply"], "product_id": thread.get("product_id"),
                              "title": thread.get("title"), "line_id": on_lines[0] if len(on_lines) == 1 else None,
                              "thread": thread.get("id"), "said_by": "the store's own agent"},
                    "text": "%s's agent on %s: %s" % (store, thread.get("title") or "a product", turn["reply"])})
    return out


# --- all records, and one record ------------------------------------------------------------------------------

def _with_id(memory: dict) -> dict:
    ref = {k: memory["source"].get(k) for k in ("type", "chain", "n", "hash", "file", "index", "turn", "entry_hash")}
    return dict(memory, id="m_" + receipts.digest({"source": ref, "kind": memory["kind"], "key": memory["key"]})[:16])


def derive() -> dict:
    """Every memory the records on disk prove: `{memories, not_memories}`; the second lists records that look like a
    memory and are refused, with the reason (a broken chain, an approver's receipt with no signed request)."""
    memories, refused = [], []
    every = chains()
    for chain in every.values():
        if not chain["verified"]:
            if chain["receipts"]:
                refused.append({"source": {"type": "receipt", "chain": chain["id"], "file": chain["file"]},
                                "code": "chain_broken", "why": "the chain does not recompute; nothing in it is remembered"})
            continue
        sheet_id = sheet_of(chain, every)
        for receipt in chain["receipts"]:
            try:
                memory = _from_receipt(chain, receipt, sheet_id)
            except Refused as no:
                refused.append({"source": {"type": "receipt", "chain": chain["id"], "n": receipt["n"], "file": chain["file"]},
                                "code": no.code, "why": str(no)})
                continue
            if memory:
                memories.append(_with_id(memory))
    for path, sheet_id in answer_files():
        entries = _cached(path, _json)
        for index, entry in enumerate(entries if isinstance(entries, list) else []):
            if isinstance(entry, dict):
                memories += [_with_id(m) for m in _from_answer(path, index, entry, sheet_id)]
    for path in talk_files():
        thread = _cached(path, _json)
        if isinstance(thread, dict):
            memories += [_with_id(m) for m in _from_talk(path, thread)]
    memories.sort(key=lambda m: (str(m["created_at"]), m["id"]))
    return {"memories": memories, "not_memories": refused}


def prove(source) -> list:
    """The memories the one record `source` names proves. Raises Refused when there is no such record, when its chain
    does not recompute, or when an approver's receipt has no signed request behind it."""
    if not isinstance(source, dict):
        raise Refused("no_source", "a memory must name the record it comes from")
    if source.get("type") == "receipt":
        every = chains()
        chain = every.get(str(source.get("chain")))
        if chain is None:
            raise Refused("no_such_record", "no receipt chain %r on disk" % (source.get("chain"),))
        if not chain["verified"]:
            raise Refused("chain_broken", "chain %s does not recompute" % chain["id"])
        receipt = next((r for r in chain["receipts"] if r["n"] == source.get("n") and r["hash"] == source.get("hash")), None)
        if receipt is None:
            raise Refused("no_such_record", "chain %s has no receipt %r with that hash" % (chain["id"], source.get("n")))
        memory = _from_receipt(chain, receipt, sheet_of(chain, every))
        if memory is None:
            raise Refused("not_a_memory", "a %r receipt is not something to remember" % receipt.get("type"))
        return [_with_id(memory)]
    if source.get("type") == "file":
        for path, sheet_id in answer_files():
            if _rel(path) == source.get("file"):
                entries = _cached(path, _json)
                index = source.get("index")
                if not isinstance(entries, list) or isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(entries):
                    break
                return [_with_id(m) for m in _from_answer(path, index, entries[index], sheet_id)]
        for path in talk_files():
            if _rel(path) == source.get("file"):
                thread = _cached(path, _json)
                proved = [_with_id(m) for m in _from_talk(path, thread if isinstance(thread, dict) else {})
                          if m["source"]["turn"] == source.get("turn")]
                if proved:
                    return proved
        raise Refused("no_such_record", "no saved store answer at %r, entry %r" % (
            source.get("file"), source.get("index", source.get("turn"))))
    raise Refused("no_source", "a memory must name a receipt, a saved store answer or a store's reply in a saved conversation")
