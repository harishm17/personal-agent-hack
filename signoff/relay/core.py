"""Relay session state, in memory. relayToken, relaySecret and the Privacy Pass never leave this process;
only the hosted-flow link (which carries relaySessionAccessToken) goes to the client.
The Node helper (signoff/relay/node/relay.mjs) is called with JSON in and out. The sandbox key is read through
signoff.config and handed to the helper's environment only."""
import json
import os
import pathlib
import subprocess
import threading
import time
from urllib.parse import quote

from signoff import config

NODE_DIR = pathlib.Path(__file__).resolve().parent / "node"
CLAIM_TYPE = "live_human_presence"
SESSION_SECONDS = 30 * 60
_lock = threading.Lock()
_session: dict | None = None  # relay_token, relay_secret, access_token, started, expires, pass_token
_result: dict | None = None


def _helper(payload: dict, timeout: int = 60) -> dict:
    key = config.env("PERSONA_API_KEY")
    if not key:
        return {"ok": False, "message": "no sandbox key"}
    try:
        p = subprocess.run(["node", "relay.mjs"], cwd=NODE_DIR, input=json.dumps(payload), capture_output=True,
                           text=True, timeout=timeout, env={**os.environ, "PERSONA_API_KEY": key})
        return json.loads(p.stdout) if p.stdout.strip() else {"ok": False, "message": (p.stderr or "no output")[-200:]}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "message": repr(error)[:200]}


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))


def start() -> dict:
    """New session; returns what the client needs and nothing secret."""
    global _session, _result
    out = _helper({"op": "create"})
    if not out.get("ok"):
        return {"ok": False, "error": out.get("message")}
    now = time.time()
    with _lock:
        _session = {"relay_token": out["relayToken"], "relay_secret": out["relaySecret"],
                    "access_token": out["relaySessionAccessToken"], "started": now, "expires": now + SESSION_SECONDS,
                    "pass_token": None}
        _result = None
    hosted = "https://relay.withpersona.com/relay?relay-session-access-token=" + quote(out["relaySessionAccessToken"], safe="") + "&theme=light"
    return {"ok": True, "access_token": out["relaySessionAccessToken"], "hosted_url": hosted, "expires_at": _iso(now + SESSION_SECONDS), "sandbox": True}


def complete() -> dict:
    """Issues the Privacy Pass (once per session), redeems the claim. {"pending": true} until the person has
    finished the hosted step."""
    global _result
    with _lock:
        s = _session
        if s is None:
            return {"ok": False, "error": "no session started"}
        if _result:
            return {"ok": True, **_result}
        if time.time() > s["expires"]:
            return {"ok": False, "error": "session expired"}
        if not s["pass_token"]:
            issued = _helper({"op": "issue"})
            if not issued.get("ok"):
                return {"ok": False, "error": issued.get("message")}
            s["pass_token"] = issued["privacyPassToken"]
        out = _helper({"op": "claim", "privacyPassToken": s["pass_token"], "relayToken": s["relay_token"],
                       "relaySecret": s["relay_secret"]})
        if not out.get("ok"):
            if str(out.get("status")) == "403" or "not yet" in str(out.get("message", "")).lower():
                return {"ok": True, "pending": True}
            return {"ok": False, "error": out.get("message"), "status": out.get("status")}
        try:
            payload = json.loads(out["claimPayload"])
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": "claim payload was not JSON"}
        _result = {"claim_type": payload.get("claim_type", CLAIM_TYPE), "result": payload.get("claim_result"),
                   "sandbox": True, "at": _iso(time.time()),
                   "methodology": [m.get("method") for m in payload.get("methodology", [])],
                   "token_consumed": out.get("tokenConsumed")}
        return {"ok": True, **_result}


def status() -> dict | None:
    """The stored claim for the signature record: {claim_type, result, sandbox: true, at}; None until a pass.
    Never raises."""
    try:
        if not _result:
            return None
        return {k: _result[k] for k in ("claim_type", "result", "sandbox", "at")}
    except Exception:  # noqa: BLE001
        return None


def session_state() -> dict:
    s = _session
    return {"started": bool(s), "expires_at": _iso(s["expires"]) if s else None,
            "expired": bool(s and time.time() > s["expires"]), "result": status()}
