"""SIGN routes: enrol the issuer's phone key, accept signed requests, Persona, Senso, reset.

The only way a limit changes, a line is struck or carts are created is `POST /api/issuer/request` with a
verified signature. Engine and store are reached through `get_engine()` and `get_cart()` so tests can stand in
for them."""
from __future__ import annotations

import importlib
import inspect
import json
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from signoff import config

from . import handcheck, persona, senso
from .verify import KeyStore, Refused, verify_request

router = APIRouter()
router.include_router(handcheck.router)
keystore = KeyStore()
_lock = threading.RLock()


def get_engine():
    return importlib.import_module("signoff.engine.state")


def get_cart():
    return importlib.import_module("signoff.store.cart")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def receipt(kind: str, outcome: str, detail: str = "", payload: dict | None = None) -> None:
    """Writes a receipt for a signed request, accepted or refused, if the engine's receipt chain is on main.
    Never raises, never waits."""
    try:
        mod = importlib.import_module("signoff.engine.receipts")
        fn = getattr(mod, "add", None) or getattr(mod, "record", None) or getattr(mod, "append", None)
        if fn:
            key = keystore.key
            fn(type=kind, actor=key.name if key else None, key_id=key.key_id if key else None,
               body={"outcome": outcome, "reason": detail, **(payload or {})})
    except Exception:  # noqa: BLE001
        pass


def _kind_of(body: dict) -> str:
    try:
        return str(json.loads(body["payload"]).get("type") or "request")
    except Exception:  # noqa: BLE001
        return "request"


def _fail(error: Refused) -> JSONResponse:
    return JSONResponse({"ok": False, "error": error.code, "detail": error.detail}, status_code=error.status)


async def _json(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return {}
    return body if isinstance(body, dict) else {}


def _issuer_info() -> dict:
    key = keystore.key
    return {"enrolled": bool(key), "key_id": key.key_id if key else None, "name": key.name if key else None,
            "persona": persona.record() if key else None}


def _push_issuer_key(engine) -> None:
    """Optional hook: tells the engine who is enrolled so /api/state shows `issuer_key`. Skipped if absent."""
    hook = getattr(engine, "set_issuer_key", None)
    if hook:
        try:
            hook(_issuer_info())
        except Exception:  # noqa: BLE001
            pass


@router.post("/api/issuer/enroll")
async def enroll(request: Request):
    body = await _json(request)
    try:
        key = keystore.enroll(body.get("public_key_jwk"), str(body.get("name") or ""), _now())
    except Refused as error:
        return _fail(error)
    try:
        _push_issuer_key(get_engine())
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "key_id": key.key_id}


@router.get("/api/issuer/status")
def issuer_status():
    ensure_watcher()
    return {**_issuer_info(), "senso": senso.checks()}


# ---- the signed request -------------------------------------------------------------------------------

def _find_limit(state: dict, limit_id: str):
    for line in state["sheet"]["lines"]:
        for limit in line["limits"]:
            if limit["id"] == limit_id:
                return limit
    return None


def _check_action(payload: dict, state: dict) -> None:
    """Shape and range checks on top of the signature, so a signed but nonsensical request is still refused."""
    kind = payload["type"]
    if kind == "set_limit":
        limit = _find_limit(state, str(payload.get("limit_id")))
        value = payload.get("value")
        if limit is None or limit["bound"].get("source") != "issuer":
            raise Refused("not_an_issuer_limit", "that limit is not one the issuer sets", 400)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise Refused("bad_value", "value must be a number", 400)
        b = limit["bound"]
        if not (b["min"] <= value <= b["max"]):
            raise Refused("out_of_range", "value %g is outside %g to %g" % (value, b["min"], b["max"]), 400)
        steps = (value - b["min"]) / b["step"]
        if abs(steps - round(steps)) > 1e-6:
            raise Refused("off_step", "value %g is not a multiple of %g from %g" % (value, b["step"], b["min"]), 400)
    elif kind in ("strike", "unstrike"):
        line = next((l for l in state["lines"] if l["line_id"] == payload.get("line_id")), None)
        if line is None or not any(c["product"]["product_key"] == payload.get("product_key") for c in line["candidates"]):
            raise Refused("unknown_product", "no such product on that line", 400)
        if kind == "strike" and not str(payload.get("reason") or "").strip():
            raise Refused("reason_needed", "a strike needs a reason", 400)


def _picks(state: dict) -> list[dict]:
    """What goes in the carts: each ready line's pick, one of each. Pick-up lines are never bought through a cart."""
    out = []
    for line in state["lines"]:
        if line["status"] not in ("ready", "next_candidate") or not line.get("pick"):
            continue
        cand = next(c for c in line["candidates"] if c["id"] == line["pick"])
        out.append({"store": cand["product"]["store"], "variant_id": cand["product"]["variant_id"], "quantity": 1})
    return out


_late: dict = {}  # the signed record, so a cart that answers after the seal can still be added to it


def _carts_within(picks: list[dict], budget: float) -> list[dict]:
    """One thread per store, one try each, answers within `budget` seconds in all. A store that has not answered gets
    a `pending` entry (its thread goes on and the entry is filled in when it answers); a store that errors gets a
    `failed` entry. Never a hang."""
    by_store: dict[str, list[dict]] = {}
    for p in picks:
        by_store.setdefault(p["store"], []).append(p)
    box: dict[str, dict] = {}

    def work(store: str, items: list[dict]) -> None:
        try:
            create = get_cart().create_carts
            extra = {k: v for k, v in (("timeout_s", 20), ("tries", 1)) if k in inspect.signature(create).parameters}
            made = create(items, **extra)
            box[store] = {"carts": made}
        except Exception as error:  # noqa: BLE001
            box[store] = {"error": type(error).__name__}
        if store in _late.get("pending", set()):
            _late_fill(store, box[store])

    _late["pending"] = set()
    threads = {store: threading.Thread(target=work, args=(store, items), daemon=True) for store, items in by_store.items()}
    for t in threads.values():
        t.start()
    deadline = time.time() + budget
    for t in threads.values():
        t.join(max(0.0, deadline - time.time()))
    out = []
    for store in by_store:
        got = box.get(store)
        now = _now()
        if got and got.get("carts"):
            out += got["carts"]
        elif got:
            out.append({"store": store, "cart_id": None, "cart_url": None, "total_cents": None, "created_at": now,
                        "mode": "failed", "note": "the store answered with an error (%s); no cart was created" % got["error"]})
        else:
            _late["pending"].add(store)
            out.append({"store": store, "cart_id": None, "cart_url": None, "total_cents": None, "created_at": now,
                        "mode": "pending", "note": "the store had not answered in %g s; the cart is still being created" % budget})
    return out


def _late_fill(store: str, got: dict) -> None:
    """A store answered after the seal: put its cart in the signed record."""
    ctx = _late.get("ctx")
    if not ctx:
        return
    with ctx["lock"]:
        carts = [c for c in ctx["carts"] if not (c["store"] == store and c["mode"] == "pending")]
        if got.get("carts"):
            carts += got["carts"]
        else:
            carts.append({"store": store, "cart_id": None, "cart_url": None, "total_cents": None, "created_at": _now(),
                          "mode": "failed", "note": "the store answered with an error (%s)" % got.get("error")})
        ctx["carts"] = carts
        try:
            ctx["engine"].mark_signed(ctx["signature"], carts)
        except Exception:  # noqa: BLE001
            pass


@router.post("/api/issuer/request")
async def issuer_request(request: Request):
    body = await _json(request)
    return await run_in_threadpool(_handle_request, body)  # blocking work stays off the event loop


def _handle_request(body: dict):
    ensure_watcher()
    with _lock:
        try:
            engine = get_engine()
            state = engine.get_state()
            prev_seq = keystore.key.last_seq if keystore.key else None
            payload = verify_request(keystore, body, sheet_id=state["sheet"]["id"], current_hash=engine.sheet_hash())
            if state["seal"].get("signed"):
                raise Refused("already_signed", "the sheet is signed; reset to sign again", 409)
            _check_action(payload, state)
            signer = {"key_id": keystore.key.key_id, "name": keystore.key.name}
            if payload["type"] != "sign_sheet":
                result = engine.apply_issuer({**payload, "signer": signer})
                return {"ok": True, "applied": payload["type"], "version": _version(result, engine)}
            who = persona.status() if persona.record().get("inquiry_id") else persona.record()  # read from Persona's backend
            if config.env("PERSONA_REQUIRED") == "1" and not who.get("verified"):
                raise Refused("identity_not_verified", "identity not verified", 403, retry_ok=True)
            gate = _senso_gate(engine)
            if gate["blocking"]:
                raise Refused("senso_blocked", "Senso found %d sentence(s) in conflict or unsupported" % len(gate["blocking"]), 409, retry_ok=True)
            picks = _picks(state)
            if not picks:
                raise Refused("nothing_to_buy", "no line has a pick to put in a cart", 409, retry_ok=True)
            carts = _carts_within(picks, CART_BUDGET_S)
            if not any(c["mode"] in ("pending",) or c.get("cart_url") for c in carts):
                raise Refused("cart_failed", "no store created a cart (%s); nothing is signed" % "; ".join(c.get("note", "") for c in carts), 502, retry_ok=True)
            at = _now()
            signature = {"name": signer["name"], "signer": signer, "at": at, "signed_at": at, "sheet_hash": payload["sheet_hash"], "sig": body["sig"],
                         "payload": body["payload"], "seq": payload["seq"], "persona": who,
                         "senso": {"status": gate["status"], "for_hash": gate.get("for_hash"), "checks": gate["checks"],
                                   "label": "Senso check still running" if gate["status"] == "pending" else None}}
            result = engine.mark_signed(signature, carts)
            _late["ctx"] = {"engine": engine, "signature": signature, "carts": carts, "lock": threading.Lock()}
            receipt("sign_sheet", "accepted", "", {"sheet_hash": payload["sheet_hash"]})
            return {"ok": True, "applied": "sign_sheet", "carts": carts, "senso": gate["status"], "version": _version(result, engine)}
        except Refused as error:
            if error.retry_ok and keystore.key and prev_seq is not None:
                keystore.update(last_seq=prev_seq)  # nothing happened, so the same signed request may be sent again
            if error.retry_ok or error.code in ("stale_hash", "replayed_seq", "bad_signature", "unsigned", "not_enrolled", "unknown_key", "wrong_sheet", "already_signed"):
                receipt(_kind_of(body), "refused", error.code + ": " + error.detail)
            return _fail(error)
        except ModuleNotFoundError as error:
            return _fail(Refused("engine_unavailable", "the engine is not loaded (%s)" % error.name, 503))
        except ValueError as error:  # the engine's own refusal (EngineError carries an HTTP status)
            if hasattr(error, "status"):
                return _fail(Refused("engine_refused", str(error), error.status))
            raise


def _version(result, engine):
    if isinstance(result, dict) and "version" in result:
        return result["version"]
    try:
        return engine.get_state().get("version")
    except Exception:  # noqa: BLE001
        return None


# ---- Persona, Senso, reset ------------------------------------------------------------------------------

@router.post("/api/issuer/persona/start")
def persona_start():
    key = keystore.key
    return persona.start(key.key_id if key else None)


@router.get("/api/issuer/persona/status")
def persona_status():
    return persona.status()


# Senso never runs inside a signing request. A background watcher runs it whenever the sheet hash changes (after a
# short debounce), when the Sign view opens or after a reset; `sign_sheet` only reads what is there, waits a little
# for a run in progress, and otherwise signs with the check marked pending.
DEBOUNCE_S = 1.5
SENSO_WAIT_S = 3.0
CART_BUDGET_S = 5.0
_watcher: dict = {"thread": None}


def _senso_run_now(engine) -> None:
    state = engine.get_state()
    if state["seal"].get("signed"):
        return
    h = engine.sheet_hash()
    senso.run_checks(state, h)
    if hasattr(engine, "set_senso"):
        engine.set_senso(senso.checks()["checks"])


def _watch() -> None:
    last, changed_at = None, 0.0
    while True:
        time.sleep(0.4)
        try:
            if not senso.configured():
                continue
            engine = get_engine()
            h = engine.sheet_hash()
            now = time.time()
            if h != last:
                last, changed_at = h, now
            if senso.checks()["for_hash"] == h or senso.running_for() is not None:
                continue
            if now - changed_at < DEBOUNCE_S and not senso.kicked():
                continue
            _senso_run_now(engine)
        except Exception as error:  # noqa: BLE001
            senso._meta["error"] = type(error).__name__
            senso._kick.clear()
            time.sleep(2)


def ensure_watcher() -> None:
    t = _watcher["thread"]
    if t is None or not t.is_alive():
        _watcher["thread"] = threading.Thread(target=_watch, name="senso-watcher", daemon=True)
        _watcher["thread"].start()


def _senso_gate(engine) -> dict:
    """What `sign_sheet` does about Senso: apply verdicts for the current hash if they exist, wait at most
    SENSO_WAIT_S for a run in progress, otherwise go on with status "pending". Only a verdict that actually came back
    as blocking blocks."""
    if not senso.configured():
        c = senso.checks()
        return {"status": "not_connected", "blocking": c["blocking"], "checks": c["checks"]}
    h = engine.sheet_hash()
    senso.kick()  # make sure a run is on its way; the watcher starts it, not this request
    deadline = time.time() + SENSO_WAIT_S
    while senso.checks()["for_hash"] != h and time.time() < deadline:
        time.sleep(0.2)
    c = senso.checks()
    if c["for_hash"] == h:
        return {"status": "complete", "blocking": c["blocking"], "checks": c["checks"], "for_hash": h}
    return {"status": "pending", "blocking": [], "checks": [], "for_hash": h}


@router.get("/api/senso/checks")
def senso_checks():
    ensure_watcher()
    return senso.checks()


@router.post("/api/senso/run")
def senso_run():
    """Asks for a run now and returns at once; the phone polls `GET /api/senso/checks` for the answer."""
    ensure_watcher()
    senso.kick()
    return senso.checks()


@router.post("/api/senso/load")
def senso_load():
    """Puts the order, the handout and the store texts in the knowledge base (asynchronous on Senso's side)."""
    if not senso.configured():
        return {"configured": False}
    result = senso.load_documents()
    return {**result, "processing": senso.wait_processed(timeout=5)}


@router.post("/api/admin/persona/simulate")
async def admin_persona_simulate(request: Request):
    """Rehearsal control, not on the phone's path: `{"action": "decline"}` or `{"action": "approve"}` on the current
    sandbox inquiry, so the identity gate can be seen holding and then letting the same signature through."""
    body = await _json(request)
    return await run_in_threadpool(persona.simulate, str(body.get("action", "")))


@router.post("/api/admin/reset")
def admin_reset():
    ensure_watcher()
    with _lock:
        keystore.reset()
        persona.reset()
        senso.reset()
        try:
            engine = get_engine()
            result = engine.reset()
            _push_issuer_key(engine)
        except ModuleNotFoundError:
            result = None
        return {"ok": True, "state_version": result.get("version") if isinstance(result, dict) else None}
