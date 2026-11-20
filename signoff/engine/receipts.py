"""A tamper-evident chain of receipts: one for every change the engine applies and for every signed request,
accepted or refused.

Each receipt is `{n, at, type, actor, key_id, body_hash, prev_hash, hash}` plus an optional small `detail`.
`hash` is the SHA-256 of the canonical JSON of all the other fields, and `prev_hash` is the hash of the
receipt before it, so changing, dropping or reordering any receipt breaks every hash after it. `body_hash`
is the SHA-256 of the canonical JSON of what was asked (the request payload, or the change applied).

The chain lives in memory and in a JSON-lines file, one file per chain, under data/receipts/. A reset starts
a new chain whose first receipt names the chain before it and that chain's last hash. `verify()` reads the
file back and recomputes everything. Tamper-evident, not tamper-proof: whoever can rewrite the whole file
and this process's memory can forge a chain; an edit to any part of it shows.

Nothing here raises into the caller: a receipt that cannot be written is logged and the change still applies.
"""
import datetime
import hashlib
import json
import logging
import os
import pathlib
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FOLDER = ROOT / "data" / "receipts"
ZERO = "0" * 64
log = logging.getLogger("signoff.receipts")
_lock = threading.RLock()
_c = {"id": None, "receipts": [], "file": None, "previous": None}


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(obj) -> str:
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def hash_of(receipt: dict) -> str:
    return digest({k: v for k, v in receipt.items() if k != "hash"})


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _to_disk():
    return os.environ.get("SIGNOFF_RECEIPTS", "file") == "file"


def start(reason="start") -> dict:
    """A new chain. Its first receipt records why, and the last hash of the chain before it."""
    with _lock:
        before = {"chain": _c["id"], "last_hash": _c["receipts"][-1]["hash"] if _c["receipts"] else None,
                  "count": len(_c["receipts"])} if _c["id"] else None
        _c.update(id=datetime.datetime.now().strftime("%Y%m%dT%H%M%S.%f"), receipts=[], file=None, previous=before)
        if _to_disk():
            try:
                FOLDER.mkdir(parents=True, exist_ok=True)
                _c["file"] = FOLDER / (_c["id"] + ".jsonl")
            except OSError as error:
                log.warning("receipts are in memory only (%s)", type(error).__name__)
        return _append("chain_started", "system", None, {"reason": reason},
                       {"reason": reason, "chain": _c["id"], "previous": before})


def _append(kind, actor, key_id, body, detail):
    prev = _c["receipts"][-1]["hash"] if _c["receipts"] else ZERO
    receipt = {"n": len(_c["receipts"]) + 1, "at": _now(), "type": kind, "actor": actor, "key_id": key_id,
               "body_hash": digest(body), "prev_hash": prev}
    if detail:
        receipt["detail"] = detail
    receipt["hash"] = hash_of(receipt)
    _c["receipts"].append(receipt)
    if _c["file"] is not None:
        try:
            with open(_c["file"], "a") as f:
                f.write(canonical(receipt) + "\n")
        except OSError as error:
            log.warning("a receipt was not written to disk (%s)", type(error).__name__)
    return receipt


def append(kind: str, actor: str, key_id=None, body=None, detail=None):
    """One receipt at the end of the chain. `body` is what was asked or applied (only its hash is kept);
    `detail` is a small readable summary kept in the receipt and covered by its hash. Never raises."""
    try:
        with _lock:
            if _c["id"] is None:
                start("process start")
            return _append(kind, actor, key_id, body, detail)
    except Exception as error:  # noqa: BLE001
        log.warning("no receipt for %s (%s)", kind, type(error).__name__)
        return None


def signed_request(payload, key_id, accepted: bool, reason=None, actor="issuer"):
    """For `signoff.sign`: call once for every signed request that arrives, whether it was accepted or refused
    (bad signature, replayed seq, stale hash, a refusal by the engine, a Senso block). `payload` is the request's
    payload (the JSON string as signed, or the parsed dict); `reason` says why a request was refused."""
    kind = None
    try:
        parsed = json.loads(payload) if isinstance(payload, str) else (payload or {})
        kind = parsed.get("type") if isinstance(parsed, dict) else None
    except ValueError:
        parsed = None
    detail = {"request": kind, "accepted": bool(accepted)}
    if isinstance(parsed, dict):
        detail.update({k: parsed[k] for k in ("seq", "limit_id", "value", "line_id", "product_key", "sheet_hash")
                       if k in parsed})
    if not accepted:
        detail["refused_because"] = str(reason or "not stated")[:300]
    return append("request_accepted" if accepted else "request_refused", actor, key_id, payload, detail)


def chain() -> dict:
    with _lock:
        if _c["id"] is None:
            start("process start")
        return {"chain": _c["id"], "previous": _c["previous"], "file": str(_c["file"].relative_to(ROOT)) if _c["file"] and
                ROOT in _c["file"].parents else (str(_c["file"]) if _c["file"] else None),
                "receipts": list(_c["receipts"])}


def check(receipts) -> dict:
    """Recomputes every hash and every link. `{count, verified, first_bad}`; `first_bad` is the `n` of the
    first receipt that does not hold (or its place in the list if its own `n` is wrong)."""
    prev = ZERO
    for i, r in enumerate(receipts):
        ok = isinstance(r, dict) and r.get("n") == i + 1 and r.get("prev_hash") == prev and r.get("hash") == hash_of(r)
        if not ok:
            return {"count": len(receipts), "verified": False, "first_bad": i + 1}
        prev = r["hash"]
    return {"count": len(receipts), "verified": True, "first_bad": None}


def verify() -> dict:
    """The chain as it stands on disk, read back and recomputed, and compared with the chain in memory."""
    with _lock:
        held = chain()
        memory = check(held["receipts"])
        if _c["file"] is None or not _c["file"].exists():
            return dict(memory, checked="memory")
        try:
            lines = [l for l in _c["file"].read_text().splitlines() if l.strip()]
            on_disk = [json.loads(l) for l in lines]
        except (OSError, ValueError):
            return {"count": len(held["receipts"]), "verified": False, "first_bad": None, "checked": "file",
                    "error": "the file cannot be read as receipts"}
        result = check(on_disk)
        if result["verified"] and memory["verified"]:
            for i, r in enumerate(held["receipts"]):
                if i >= len(on_disk) or on_disk[i]["hash"] != r["hash"]:
                    result.update(verified=False, first_bad=i + 1)
                    break
            else:
                if len(on_disk) != len(held["receipts"]):
                    result.update(verified=False, first_bad=len(held["receipts"]) + 1)
        elif not memory["verified"]:
            result = dict(memory)
        return dict(result, checked="file and memory", chain=held["chain"])


def summary() -> dict:
    """For `/api/state`: `{count, verified, last_hash}`. The chain in memory is recomputed (a few ms at most)."""
    with _lock:
        held = chain()["receipts"]
        return {"count": len(held), "verified": check(held)["verified"], "last_hash": held[-1]["hash"] if held else None,
                "chain": _c["id"]}
