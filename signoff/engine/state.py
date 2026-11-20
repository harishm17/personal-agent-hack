"""The sheet's state, held in memory and recomputed by code on every change.

Signatures are fixed by CONTRACT.md "In-process calls". The dict returned by these functions is shared:
read it, do not change it. Limits and strikes change only through `apply_issuer`, which `signoff.sign`
calls after it has verified a signed request. Nothing here is reachable from a model.
"""
import datetime
import hashlib
import json
import os
import pathlib
import re
import threading
import time

from signoff import config
from signoff.engine import obs, rules

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


def _has_data_pool():
    return any((DATA / "pool").glob("*.json"))


def _load_pool():
    """Pool and store answers through the STORE stream's loader; the same fallback when it is not there."""
    try:
        from signoff.store import pool as store_pool
        pool, answers = store_pool.load()
        return list(pool), list(answers)
    except Exception:  # noqa: BLE001  (module not merged yet, or it failed: read the files directly)
        pass
    if _has_data_pool():
        answers = _read_dir(DATA / "store_answers") if (DATA / "store_answers").is_dir() else []
        return _read_dir(DATA / "pool"), answers
    return _read(FIXTURES / "pool.json"), _read(FIXTURES / "store_answers.json")


def _load_figures(pool, from_data):
    """Figures from data/figures (fixtures for the fixture pool). The span is checked again here, in code."""
    run = DATA / "figures" / "_runs" / str(_s.get("reader")) if _s.get("reader") else None
    if from_data and run is not None and run.is_dir():
        figures = _read_dir(run)
    elif from_data:
        figures = _read_dir(DATA / "figures") if (DATA / "figures").is_dir() else []
    else:
        figures = _read(FIXTURES / "figures.json")
    text = {(p["store"], p["product_id"]): p.get("text") for p in pool}
    for f in figures:
        page = text.get((f["store"], f["product_id"]))
        f["span_found_in_text"] = rules.span_found(f, page)
        if f["span_found_in_text"]:  # the store's whole sentence, for the screen to show around the quote
            sentence, a, b = rules.sentence_around(page, f["start"], f["end"])
            f.update(sentence=sentence, quote_in_sentence=[a, b])
    return figures


def _load_readers(from_data):
    """Which reader decided, and how far the others agree with it (signoff.extract.score writes the file)."""
    path = DATA / "figures" / "_runs" / "comparison.json"
    if not from_data or not path.exists():
        return None
    try:
        made = _read(path)
        return {"reference": made["reference"], "measure": made["measure"], "note": made["note"],
                "products": made["products"], "made_at": made["made_at"],
                "readers": [{k: v for k, v in r.items() if k != "differences"} for r in made["readers"]]}
    except (ValueError, KeyError):
        return None


def _load(keep_changes=False):
    sheet_id = os.environ.get("SIGNOFF_SHEET") or "sheet1"
    pool, answers = _load_pool()
    from_data = _has_data_pool() and not any(str(p["store"]).endswith(".example") for p in pool)
    mode = "fixture" if not from_data else ("replay" if config.mode() == "replay" else "live")
    _s.update(pool=pool, answers=answers, figures=_load_figures(pool, from_data), mode=mode, loaded=True,
              readers=_load_readers(from_data))
    if keep_changes and _s.get("sheet", {}).get("id") == sheet_id:
        return
    strikes_file = (DATA if from_data else FIXTURES) / "strikes.json"
    _s.update(sheet=_read(SHEETS / (sheet_id + ".json")),
              strikes=_read(strikes_file) if strikes_file.exists() else [],
              seal=None, issuer_key={"enrolled": False, "key_id": None, "persona": None}, senso=[])


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
        out = {"line_id": line["line_id"], "need": line["need"], "status": line["status"], "limits": limits,
               "struck": sorted(s["product_key"] for s in line["struck"]), "pick": None}
        pick = next((c for c in line["candidates"] if c["picked"]), None)
        if pick:
            p = pick["product"]
            out["pick"] = {"id": pick["id"], "store": p["store"], "product_id": p["product_id"],
                           "variant_id": p["variant_id"], "product_key": p["product_key"],
                           "price_cents": p["price_cents"],
                           "checks": [{"limit_id": c["limit_id"], "expr": c["expr"]} for c in pick["checks"]],
                           "quotes": [t["quote"] for c in pick["checks"] for t in c["terms"] if t.get("quote")]}
        lines.append(out)
    return {"sheet_id": state["sheet"]["id"], "lines": lines, "total_cents": state["total_cents"]}


def _canonical(state):
    return json.dumps(_canonical_obj(state), sort_keys=True, separators=(",", ":"))


def _seal(state, current_hash):
    seal = _s.get("seal")
    if not seal:
        return state["seal"]
    return dict(seal, current=seal["sheet_hash"] == current_hash)


def _attach(state):
    """Adds what is not a rule: who signed, the carts, the issuer's key and the text checks."""
    carts = {c.get("store"): c for c in (_s.get("seal") or {}).get("carts", [])}
    by_candidate = {}
    for check in _s.get("senso") or []:
        for key in (check.get("candidate_id"), (check.get("store"), check.get("product_id"))):
            if key and key != (None, None):
                by_candidate.setdefault(key, []).append(check)
    for line in state["lines"]:
        for c in line["candidates"]:
            found = by_candidate.get(c["id"], []) + by_candidate.get((c["product"]["store"], c["product"]["product_id"]), [])
            if found:
                c["senso"] = {"claims": found}
            cart = carts.get(c["product"]["store"])
            if cart and c["picked"] and line["status"] in ("ready", "next_candidate"):
                c["action"] = {"type": "cart_created", "mode": cart.get("mode"), "cart_url": cart.get("cart_url"),
                               "cart_id": cart.get("cart_id"), "at": cart.get("created_at")}
    state["issuer_key"] = dict(_s["issuer_key"])
    state["readers"] = _s.get("readers")
    if _s.get("readers"):
        used = next((f["extractor"] for f in _s["figures"]), _s["readers"]["reference"])
        state["readers"] = dict(_s["readers"], deciding=used, switched=bool(_s.get("reader")))
    state["senso"] = list(_s.get("senso") or [])
    state["sheet_hash"] = hashlib.sha256(_canonical(state).encode()).hexdigest()
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


def _open_for_changes():
    if _s.get("seal"):
        raise EngineError("this sheet is signed and its carts exist; reset to start again", 409)


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
        except Exception:  # noqa: BLE001  (not merged yet, or the database is down)
            pass


# --- the contract's in-process calls ---
def get_state() -> dict:
    with _lock:
        _ensure()
        return _s["state"]


def state_json() -> bytes:
    with _lock:
        _ensure()
        return _s["json"]


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
            bound["value"] = _number(action.get("value"), bound.get("min"), bound.get("max"), limit["id"])
            limit["set_at"] = action.get("at") or _now()
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
        fact["value"] = _number(value, fact.get("min"), fact.get("max"), fact_id)
        return _recompute(why="shopper_fact")


def canonical_sheet() -> str:
    with _lock:
        _ensure()
        return _canonical(_s["state"])


def sheet_hash() -> str:
    with _lock:
        _ensure()
        return _s["state"]["sheet_hash"]


def mark_signed(signature: dict, carts: list) -> dict:
    """Called by `signoff.sign` after a verified `sign_sheet` and after the carts were created."""
    with _lock:
        _ensure()
        signature, carts = dict(signature or {}), list(carts or [])
        name = signature.get("name") or signature.get("signer") or _s["sheet"]["issuer"]["name"]
        at = signature.get("at") or signature.get("signed_at") or _now()
        n = len(carts)
        text = "Signed by %s at %s. %d cart%s created." % (name, str(at)[11:16] or at, n, "" if n == 1 else "s")
        _s["seal"] = {"signed": True, "text": text, "sheet_hash": _s["state"]["sheet_hash"],
                      "signature": signature, "carts": carts, "signed_at": at, "signer": name}
        return _recompute()


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
        return _recompute(record=False)


def set_reader(name=None) -> dict:
    """Not in the contract's list: which reader's figures count. `None` is the default (the reference reader's,
    as combined in data/figures/); a name such as "sie:Qwen/Qwen3.8-27B-FP8" uses that reader's own run. For the
    reader gate: the outcome to compare is `readers` in the state (agreement with the reference)."""
    with _lock:
        _ensure()
        _open_for_changes()
        slug = re.sub(r"[^A-Za-z0-9.]+", "-", name).strip("-") if name else None
        if slug and not (DATA / "figures" / "_runs" / slug).is_dir():
            raise EngineError("no run of reader %r under data/figures/_runs" % (name,), 404)
        _s["reader"] = slug
        _load(keep_changes=True)
        return _recompute(why="set_reader")


def reload_data() -> dict:
    """Reads pool, store answers and figures again; the issuer's limits, strikes and the seal are kept."""
    with _lock:
        _load(keep_changes=_s["loaded"])
        return _recompute()


def reset() -> dict:
    """Back to unsigned, no key, sheet as on disk."""
    with _lock:
        _s["reader"] = None
        _load()
        obs.session(_s["sheet"]["id"])
        return _recompute(why="reset")
