"""Signed-request verification and the enrolled-key store.

A request is `{payload, sig, key_id}`. `payload` is a JSON string, `sig` is base64url of the WebCrypto ECDSA
P-256 signature (raw r||s, 64 bytes) over the UTF-8 bytes of `payload`. Nothing here talks to the engine or the
stores; `api.py` does that after `verify_request` returns.
"""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import re
import secrets
import threading
import time
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

TYPES = ("set_limit", "strike", "unstrike", "sign_sheet", "decline_ask", "persona_start")
RUNTIME = pathlib.Path(__file__).resolve().parent / "_runtime"


class Refused(Exception):
    """A request the server will not act on. `code` is stable and shown to the phone; `status` is HTTP."""

    def __init__(self, code: str, detail: str, status: int = 403, retry_ok: bool = False):
        super().__init__(detail)
        self.code, self.detail, self.status, self.retry_ok = code, detail, status, retry_ok


def b64u_decode(text: str) -> bytes:
    text = text.strip()
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def public_key_from_jwk(jwk: dict) -> ec.EllipticCurvePublicKey:
    if not isinstance(jwk, dict) or jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise Refused("bad_key", "the key must be an EC P-256 public key (JWK)", 400)
    try:
        x, y = b64u_decode(jwk["x"]), b64u_decode(jwk["y"])
        if len(x) != 32 or len(y) != 32:
            raise ValueError("coordinate length")
        numbers = ec.EllipticCurvePublicNumbers(int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1())
        return numbers.public_key()
    except (KeyError, ValueError, TypeError) as error:
        raise Refused("bad_key", "the public key could not be read: %s" % error, 400) from error


def clean_jwk(jwk: dict) -> dict:
    """Only the public parts, so a private `d` that a client sent by mistake is never stored."""
    return {"kty": "EC", "crv": "P-256", "x": jwk["x"], "y": jwk["y"]}


def key_id_for(jwk: dict) -> str:
    return hashlib.sha256(("%s.%s" % (jwk["x"], jwk["y"])).encode()).hexdigest()[:16]


def check_signature(jwk: dict, payload: str, sig: str) -> None:
    key = public_key_from_jwk(jwk)
    try:
        raw = b64u_decode(sig)
    except Exception as error:  # noqa: BLE001
        raise Refused("bad_signature", "the signature is not base64url", 403) from error
    if len(raw) != 64:
        raise Refused("bad_signature", "the signature must be 64 bytes (r||s)", 403)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    try:
        key.verify(der, payload.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as error:
        raise Refused("bad_signature", "the signature does not match the enrolled key", 403) from error


@dataclass
class IssuerKey:
    key_id: str
    name: str
    jwk: dict
    enrolled_at: str
    last_seq: int = 0
    persona: dict = field(default_factory=dict)


class KeyStore:
    """One issuer key per run, and the one-time code that enrolling it needs. Kept in memory and in
    `_runtime/keystore.json` so a server restart during a rehearsal keeps both; `POST /api/admin/reset` clears the
    key and makes a new code. The code is shown only on the laptop (`GET /api/issuer/enroll-code`)."""

    MAX_WRONG, LOCK_S = 5, 60

    def __init__(self, path: pathlib.Path | None = RUNTIME / "keystore.json"):
        self.path = path
        self.lock = threading.RLock()
        self.key: IssuerKey | None = None
        self.code: str = ""
        self.wrong, self.locked_until = 0, 0.0
        self._load()
        if not self.code:
            self.code = self._new_code()
            self._save()

    @staticmethod
    def _new_code() -> str:
        return secrets.token_hex(3)  # six hex characters, typed or read from a link

    def _load(self) -> None:
        try:
            if self.path and self.path.exists():
                raw = json.loads(self.path.read_text())
                self.code = raw.get("code", "")
                if raw.get("key"):
                    self.key = IssuerKey(**raw["key"])
        except Exception:  # noqa: BLE001
            self.key, self.code = None, ""

    def _save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"code": self.code, "key": self.key.__dict__ if self.key else None}))
        except OSError:
            pass  # the in-memory copy still works

    def enroll(self, jwk: dict, name: str, now: str, code: str = "") -> IssuerKey:
        with self.lock:
            if time.time() < self.locked_until:
                raise Refused("code_locked", "too many wrong codes; wait a minute or use the laptop", 429)
            if not code or not secrets.compare_digest(str(code), self.code):
                self.wrong += 1
                if self.wrong >= self.MAX_WRONG:
                    self.wrong, self.locked_until = 0, time.time() + self.LOCK_S
                raise Refused("bad_code", "the enrolment code is missing or wrong (it is shown on the laptop)", 403)
            if self.key:
                raise Refused("already_enrolled", "an issuer key is already enrolled; reset first", 409)
            public_key_from_jwk(jwk)
            self.wrong = 0
            self.key = IssuerKey(key_id_for(jwk), (name or "Issuer").strip()[:60] or "Issuer", clean_jwk(jwk), now)
            self._save()
            return self.key

    def reset(self) -> None:
        with self.lock:
            self.key = None
            self.code = self._new_code()
            self.wrong, self.locked_until = 0, 0.0
            self._save()

    def update(self, **fields) -> None:
        with self.lock:
            if self.key:
                for k, v in fields.items():
                    setattr(self.key, k, v)
                self._save()


def verify_request(store: KeyStore, body: dict, sheet_id: str | None = None, current_hash: str | None = None) -> dict:
    """Checks one signed request and returns the parsed payload. `last_seq` is advanced as soon as the signature
    and the sequence number hold, so the same request can never be applied twice and one refused for a stale hash
    can never be sent again. Raises `Refused` with a stable code otherwise."""
    unsigned = Refused("unsigned", "not signed by the approver's key", 401)   # one answer, whatever the reason
    if not isinstance(body, dict) or not body.get("payload") or not body.get("sig"):
        raise unsigned
    with store.lock:
        key = store.key
        if key is None:
            # nothing is enrolled, so nothing can have been signed by the approver. A request that names a key id
            # in the form of ours is a phone whose key the server no longer has (a reset): say so, once, as no_key.
            if re.fullmatch(r"[0-9a-f]{16}", str(body.get("key_id") or "")):
                raise Refused("no_key", "no approver key is enrolled on this server; enrol this phone again", 401)
            raise unsigned
        if body.get("key_id") != key.key_id:
            raise unsigned
        payload_text = body["payload"]
        if not isinstance(payload_text, str):
            raise Refused("bad_payload", "payload must be the signed JSON string", 400)
        try:
            check_signature(key.jwk, payload_text, str(body["sig"]))
        except Refused as bad:
            if bad.code == "bad_signature":
                raise unsigned from bad  # a forged or altered request is not signed by the approver's key either
            raise
        try:
            payload = json.loads(payload_text)
        except ValueError as error:
            raise Refused("bad_payload", "payload is not JSON", 400) from error
        if not isinstance(payload, dict) or payload.get("type") not in TYPES:
            raise Refused("bad_payload", "type must be one of %s" % ", ".join(TYPES), 400)
        seq = payload.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int):
            raise Refused("bad_payload", "seq must be an integer", 400)
        if seq <= key.last_seq:
            raise Refused("replayed_seq", "seq %d is not greater than the last one (%d)" % (seq, key.last_seq), 409)
        # A request the key really signed is spent from here on, accepted or refused: one refused for the wrong
        # sheet or a stale hash must not become valid later, when the sheet is back where it was, with nobody tapping.
        key.last_seq = seq
        store._save()
        if sheet_id is not None and payload.get("sheet_id") != sheet_id:
            raise Refused("wrong_sheet", "the request is for another sheet", 409)
        if payload["type"] == "sign_sheet" and current_hash is not None and payload.get("sheet_hash") != current_hash:
            raise Refused("stale_hash", "the sheet changed after it was shown; look again and sign again", 409)
        return payload
