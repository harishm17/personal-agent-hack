"""SIGN routes: enrol the issuer's phone key, accept signed requests, Persona, Senso, reset.

The only way a limit changes, a line is struck or carts are created is `POST /api/issuer/request` with a
verified signature. Engine and store are reached through `get_engine()` and `get_cart()` so tests can stand in
for them."""
from __future__ import annotations

import importlib
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

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


@router.post("/api/issuer/request")
async def issuer_request(request: Request):
    body = await _json(request)
    with _lock:
        try:
            engine = get_engine()
            state = engine.get_state()
            payload = verify_request(keystore, body, sheet_id=state["sheet"]["id"], current_hash=engine.sheet_hash())
            if state["seal"].get("signed"):
                raise Refused("already_signed", "the sheet is signed; reset to sign again", 409)
            _check_action(payload, state)
            signer = {"key_id": keystore.key.key_id, "name": keystore.key.name}
            if payload["type"] != "sign_sheet":
                result = engine.apply_issuer({**payload, "signer": signer})
                return {"ok": True, "applied": payload["type"], "version": _version(result, engine)}
            blocked = senso.blocking()
            if blocked:
                raise Refused("senso_blocked", "Senso found %d sentence(s) in conflict or unsupported" % len(blocked), 409)
            picks = _picks(state)
            if not picks:
                raise Refused("nothing_to_buy", "no line has a pick to put in a cart", 409)
            try:
                carts = get_cart().create_carts(picks)
            except Exception as error:  # noqa: BLE001
                raise Refused("cart_failed", "the stores did not create the carts (%s); nothing is signed" % type(error).__name__, 502) from error
            if not carts:
                raise Refused("cart_failed", "no cart came back; nothing is signed", 502)
            signature = {"signer": signer, "at": _now(), "sheet_hash": payload["sheet_hash"], "sig": body["sig"],
                         "payload": body["payload"], "seq": payload["seq"], "persona": persona.record(),
                         "senso": senso.checks()["checks"]}
            result = engine.mark_signed(signature, carts)
            return {"ok": True, "applied": "sign_sheet", "carts": carts, "version": _version(result, engine)}
        except Refused as error:
            return _fail(error)
        except ModuleNotFoundError as error:
            return _fail(Refused("engine_unavailable", "the engine is not loaded (%s)" % error.name, 503))


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


@router.get("/api/senso/checks")
def senso_checks():
    return senso.checks()


@router.post("/api/admin/reset")
def admin_reset():
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
