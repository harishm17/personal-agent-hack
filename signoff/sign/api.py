"""SIGN routes: enrol the issuer's phone key, accept signed requests, Persona, Senso, reset.

The only way a limit changes, a line is struck or carts are created is `POST /api/issuer/request` with a
verified signature. Engine and store are reached through `get_engine()` and `get_cart()` so tests can stand in
for them."""
from __future__ import annotations

import importlib
import inspect
import json
import secrets
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from signoff import config

from . import audit, handcheck, persona, senso
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


def receipt(body: dict, accepted: bool, reason: str = "") -> None:
    """One receipt in the engine's chain for a signed request that arrived, accepted or refused. Never raises."""
    try:
        from signoff.engine import receipts
        key = keystore.key
        receipts.signed_request(body.get("payload") if isinstance(body, dict) else None, key.key_id if key else None,
                                accepted, reason or None)
    except Exception:  # noqa: BLE001
        pass


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
        key = keystore.enroll(body.get("public_key_jwk"), str(body.get("name") or ""), _now(), str(body.get("code") or ""))
    except Refused as error:
        audit.receipt("enrolment_refused", "issuer", None, {"name": str(body.get("name") or "")}, {"refused_because": error.code})
        return _fail(error)
    try:
        _push_issuer_key(get_engine())
    except Exception:  # noqa: BLE001
        pass
    audit.receipt("enrolled", "issuer", key.key_id, key.jwk, {"name": key.name, "key_id": key.key_id})
    return {"ok": True, "key_id": key.key_id}


def _laptop_only(request: Request) -> bool:
    """True for a request from the laptop running the app, or one carrying X-Admin-Token. A request that came through
    the public tunnel (proxy headers, or a client address that is not loopback) is refused. GET routes are not covered
    by the app's admin guard, so this route checks for itself."""
    h = request.headers
    token = config.env("SIGNOFF_ADMIN_TOKEN") or ""
    given = h.get("x-admin-token") or ""
    if token and given and secrets.compare_digest(given, token):
        return True
    if h.get("cf-connecting-ip") or h.get("cf-ray") or h.get("x-forwarded-for"):
        return False
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost", "testclient")


@router.get("/api/issuer/enroll-code")
def enroll_code(request: Request):
    """The one-time code that enrolling the approver's phone needs, and the link that carries it. Laptop only:
    through the tunnel this answers 403 `local_only`. A new code after every reset."""
    if not _laptop_only(request):
        return JSONResponse({"error": "local_only", "detail": "The enrolment code is shown on the laptop."}, status_code=403)
    url = config.public_url() or "http://localhost:8800"
    return {"code": keystore.code, "enrolled": bool(keystore.key), "url": "%s/phone/?code=%s" % (url, keystore.code)}


@router.get("/api/issuer/status")
def issuer_status():
    ensure_watcher()
    return {**_issuer_info(), "senso": senso.checks(), "identity_required": identity_required(), "relay": _relay()}


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


def _signed_picks(engine, signed_hash: str, state: dict) -> list[dict]:
    """The picks of exactly the signed hash from the engine, which holds the sheet until it is sealed or released."""
    fn = getattr(engine, "signed_picks", None)
    if fn is None:
        return _picks(state)
    try:
        return fn(signed_hash)
    except ValueError as error:
        if getattr(error, "status", None) == 409:
            raise Refused("sheet_moved", str(error), 409, retry_ok=True) from error
        raise


def _release(engine) -> None:
    fn = getattr(engine, "release_signing", None)
    if fn:
        try:
            fn()
        except Exception:  # noqa: BLE001
            pass


def _relay() -> dict | None:
    try:
        from signoff import relay
        r = relay.status()
        return r if r and r.get("result") == "passed" else None
    except Exception:  # noqa: BLE001
        return None


def _check_lines(carts: list[dict], picks: list[dict]) -> list[dict]:
    """The store's cart lines against the signed picks: variant id, quantity and unit price. A difference goes on the
    cart with both values, never hidden and never re-priced. A store client that returns no lines is said so."""
    out = []
    for c in carts:
        c = dict(c)
        if c.get("mode") not in ("pending", "failed") and c.get("cart_url"):
            signed = {p["variant_id"]: p for p in picks if p["store"] == c["store"]}
            lines = c.get("lines")
            if lines is None:
                c["lines_checked"] = False
            else:
                c["lines_checked"] = True
                diffs = []
                got = {l.get("variant_id"): l for l in lines}
                for vid, p in signed.items():
                    l = got.get(vid)
                    if l is None:
                        diffs.append({"variant_id": vid, "field": "line", "signed": "present", "store": "missing"})
                        continue
                    if int(l.get("quantity", 1)) != int(p.get("quantity", 1)):
                        diffs.append({"variant_id": vid, "field": "quantity", "signed": p.get("quantity", 1), "store": l.get("quantity")})
                    unit = l.get("unit_price_cents")
                    if unit is not None and p.get("price_cents") is not None and unit != p["price_cents"]:
                        diffs.append({"variant_id": vid, "field": "unit price", "signed": p["price_cents"], "store": unit})
                for vid in got:
                    if vid not in signed:
                        diffs.append({"variant_id": vid, "field": "line", "signed": "absent", "store": "present"})
                if diffs:
                    c["line_differences"] = diffs
                    c["note"] = (c.get("note") + "; " if c.get("note") else "") + "store cart differs from the signed picks: " + "; ".join(
                        "%s %s: signed %s, store %s" % (d["variant_id"].rsplit("/", 1)[-1], d["field"], d["signed"], d["store"]) for d in diffs)
        out.append(c)
    return out


def _check_totals(carts: list[dict], picks: list[dict], state: dict) -> list[dict]:
    """The store's cart total against the signed total, per store. A difference is shown on the cart ("store total
    differs", both numbers), never hidden and never re-priced."""
    price = {}
    for line in state["lines"]:
        for c in line["candidates"]:
            price[(c["product"]["store"], c["product"]["variant_id"])] = c["product"]["price_cents"]
    signed = {}
    for p in picks:
        unit = p["price_cents"] if p.get("price_cents") is not None else price.get((p["store"], p["variant_id"]), 0)
        signed[p["store"]] = signed.get(p["store"], 0) + unit * int(p.get("quantity", 1))
    out = []
    for c in carts:
        c = dict(c, signed_total_cents=signed.get(c["store"]))
        if c.get("total_cents") is not None and c["signed_total_cents"] is not None and c["total_cents"] != c["signed_total_cents"]:
            c["total_differs"] = True
            c["note"] = "store total differs: signed $%.2f, store $%.2f" % (c["signed_total_cents"] / 100, c["total_cents"] / 100)
        out.append(c)
    return out


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
            extra = {k: v for k, v in (("timeout_s", 4), ("tries", 1)) if k in inspect.signature(create).parameters}
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
            carts += _check_lines(_check_totals(got["carts"], ctx["picks"], ctx["state"]), ctx["picks"])
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


def identity_required() -> bool:
    """On by default: the signature is refused until the signer's identity check is approved (sandbox). Switch it off
    explicitly with PERSONA_REQUIRED=0 in the keys file."""
    return (config.env("PERSONA_REQUIRED") or "1").strip() != "0"


def _handle_request(body: dict):
    ensure_watcher()
    with _lock:
        held = False
        try:
            engine = get_engine()
            state = engine.get_state()
            prev_seq = keystore.key.last_seq if keystore.key else None
            snap_hash = state.get("sheet_hash") or engine.sheet_hash()  # the hash of the very state the picks come from
            payload = verify_request(keystore, body, sheet_id=state["sheet"]["id"], current_hash=snap_hash)
            if state["seal"].get("signed"):
                raise Refused("already_signed", "the sheet is signed; reset to sign again", 409)
            _check_action(payload, state)
            signer = {"key_id": keystore.key.key_id, "name": keystore.key.name}
            if payload["type"] != "sign_sheet":
                result = engine.apply_issuer({**payload, "signer": signer})
                receipt(body, True)
                return {"ok": True, "applied": payload["type"], "version": _version(result, engine)}
            who = persona.status() if persona.record().get("inquiry_id") else persona.record()  # read from Persona's backend
            if identity_required() and not who.get("verified"):
                raise Refused("identity_not_verified", "identity not verified", 403, retry_ok=True)
            gate = _senso_gate(engine)
            if gate["blocking"]:
                raise Refused("senso_blocked", "Senso found %d sentence(s) in conflict or unsupported" % len(gate["blocking"]), 409, retry_ok=True)
            picks = _signed_picks(engine, payload["sheet_hash"], state)  # exactly the signed sheet's picks; holds the sheet
            held = True
            if not picks:
                _release(engine)
                raise Refused("nothing_to_buy", "no line has a pick to put in a cart", 409, retry_ok=True)
            carts = _carts_within(picks, CART_BUDGET_S)
            if not any(c["mode"] in ("pending",) or c.get("cart_url") for c in carts):
                _release(engine)
                raise Refused("cart_failed", "no store created a cart (%s); nothing is signed" % "; ".join(c.get("note", "") for c in carts), 502, retry_ok=True)
            at = _now()
            relay = _relay()
            basis = ("identity checked, sandbox" if who.get("verified") else
                     "live human checked, sandbox" if relay else "self-declared")
            carts = _check_lines(_check_totals(carts, picks, state), picks)
            signature = {"name": "%s (%s)" % (signer["name"], basis), "name_basis": basis, "signer": signer, "at": at, "signed_at": at, "sheet_hash": payload["sheet_hash"], "sig": body["sig"],
                         "payload": body["payload"], "seq": payload["seq"], "persona": who, **({"relay": relay} if relay else {}),
                         "senso": {"status": gate["status"], "for_hash": gate.get("for_hash"), "checks": gate["checks"],
                                   "label": "Senso check still running" if gate["status"] == "pending" else None}}
            try:
                result = engine.mark_signed(signature, carts)
            except ValueError as error:  # the engine's own refusal: the sheet no longer has the signed hash
                _release(engine)
                if getattr(error, "status", None) == 409:
                    raise Refused("sheet_moved", "the sheet changed while signing; nothing is signed. Carts made for the signed sheet: %s"
                                  % ", ".join(c["cart_url"] for c in carts if c.get("cart_url")), 409, retry_ok=True) from error
                raise
            _late["ctx"] = {"engine": engine, "signature": signature, "carts": carts, "lock": threading.Lock(), "picks": picks, "state": state}
            receipt(body, True)
            return {"ok": True, "applied": "sign_sheet", "carts": carts, "senso": gate["status"], "version": _version(result, engine)}
        except Refused as error:
            if held:
                _release(get_engine())
            if error.retry_ok and keystore.key and prev_seq is not None:
                keystore.update(last_seq=prev_seq)  # nothing happened, so the same signed request may be sent again
            receipt(body, False, error.code + ": " + error.detail)
            return _fail(error)
        except ModuleNotFoundError as error:
            return _fail(Refused("engine_unavailable", "the engine is not loaded (%s)" % error.name, 503))
        except ValueError as error:  # the engine's own refusal (EngineError carries an HTTP status)
            if hasattr(error, "status"):
                receipt(body, False, "engine: " + str(error))
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
    result = senso.load_documents(get_engine().get_state()["sheet"])
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
