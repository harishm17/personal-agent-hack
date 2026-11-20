"""G23: the shopper asks the approver to move a limit; the approver decides on her phone.

An ask is a record and nothing else: it changes nothing in the sheet and nothing under the hash. Accepting it is the
approver's own signed `set_limit` carrying the `ask_id`; declining is a signed `decline_ask`. Both go through the one
signed-request path in `api.py`, so there is no other way to change a limit."""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from signoff.sign import audit

NOTE_MAX = 300
_lock = threading.RLock()
_asks: list[dict] = []
_n = [0]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def reset() -> None:
    with _lock:
        _asks.clear()
        _n[0] = 0


def _num(v) -> str:
    return str(int(v)) if float(v).is_integer() else str(round(float(v), 2))


def _words(ask: dict, approver: str) -> dict:
    """The sentences the screens print as they are."""
    label = ask["label"]
    text = "%s asks: %s %s %s instead of %s %s" % (ask["by"], label, _num(ask["to"]), ask["unit"], _num(ask["from"]), ask["unit"])
    outcome = {"pending": "asked %s · waiting" % approver,
               "accepted": "%s changed it to %s" % (ask.get("settled_by") or approver, _num(ask["to"])),
               "declined": "%s declined" % (ask.get("settled_by") or approver),
               "changed": "%s changed it to %s" % (ask.get("settled_by") or approver, _num(ask["changed_to"])) if ask.get("changed_to") is not None else "changed",
               "replaced": "replaced by a newer ask"}[ask["status"]]
    return {**ask, "text": text, "outcome": outcome}


def listing(state: dict) -> dict:
    """The asks of the sheet that is loaded now, oldest first."""
    sid = state["sheet"]["id"]
    approver = (state["sheet"].get("issuer") or {}).get("name") or "the approver"
    with _lock:
        rows = [_words(a, approver) for a in _asks if a["sheet_id"] == sid]
    return {"asks": rows, "pending": sum(1 for a in rows if a["status"] == "pending")}


def make(state: dict, limit: dict, line_id: str, value, note) -> dict:
    """Records a pending ask for a limit (the caller has checked the limit and the value). A new ask for the same limit
    replaces the pending one."""
    sid = state["sheet"]["id"]
    shopper = (state["sheet"].get("shopper") or {}).get("name") or "the shopper"
    with _lock:
        for a in _asks:
            if a["sheet_id"] == sid and a["limit_id"] == limit["id"] and a["status"] == "pending":
                a["status"], a["settled_at"] = "replaced", _now()
        _n[0] += 1
        ask = {"id": "ask-%d" % _n[0], "sheet_id": sid, "limit_id": limit["id"], "line_id": line_id, "label": limit.get("label") or limit["id"],
               "unit": limit.get("unit") or "", "op": limit.get("op"), "from": limit["bound"]["value"], "to": value,
               "note": (str(note or "").strip())[:NOTE_MAX], "by": shopper, "at": _now(), "status": "pending",
               "settled_at": None, "settled_by": None, "changed_to": None}
        _asks.append(ask)
    audit.receipt("limit_change_asked", "shopper", None, {"ask_id": ask["id"], "limit_id": ask["limit_id"], "from": ask["from"], "to": ask["to"], "note": ask["note"]},
                  {"by": shopper})
    return _words(ask, (state["sheet"].get("issuer") or {}).get("name") or "the approver")


def pending(sheet_id: str, ask_id: str):
    with _lock:
        return next((dict(a) for a in _asks if a["id"] == ask_id and a["sheet_id"] == sheet_id and a["status"] == "pending"), None)


def settle(sheet_id: str, ask_id: str, status: str, by: str, key_id=None, changed_to=None) -> None:
    with _lock:
        ask = next((a for a in _asks if a["id"] == ask_id and a["sheet_id"] == sheet_id and a["status"] == "pending"), None)
        if ask is None:
            return
        ask.update(status=status, settled_at=_now(), settled_by=by, changed_to=changed_to)
        body = {"ask_id": ask_id, "limit_id": ask["limit_id"], "status": status, "from": ask["from"], "asked": ask["to"], "changed_to": changed_to}
    audit.receipt("limit_change_settled", "issuer", key_id, body, {"by": by, "asked_by": ask["by"]})


def moved(sheet_id: str, limit_id: str, value, by: str, key_id=None) -> None:
    """The approver changed a limit herself, not through an ask: an ask waiting for it is settled as `changed`."""
    with _lock:
        ask = next((a for a in _asks if a["sheet_id"] == sheet_id and a["limit_id"] == limit_id and a["status"] == "pending"), None)
    if ask:
        settle(sheet_id, ask["id"], "accepted" if float(ask["to"]) == float(value) else "changed", by, key_id, None if float(ask["to"]) == float(value) else value)
