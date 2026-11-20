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
import threading
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

TYPES = ("set_limit", "strike", "unstrike", "sign_sheet")
RUNTIME = pathlib.Path(__file__).resolve().parent / "_runtime"


class Refused(Exception):
    """A request the server will not act on. `code` is stable and shown to the phone; `status` is HTTP."""

    def __init__(self, code: str, detail: str, status: int = 403):
        super().__init__(detail)
        self.code, self.detail, self.status = code, detail, status


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
    """One issuer key per run. Kept in memory and in `_runtime/keystore.json` so a server restart during a
    rehearsal does not lose the enrolment; `POST /api/admin/reset` clears both."""

    def __init__(self, path: pathlib.Path | None = RUNTIME / "keystore.json"):
        self.path = path
        self.lock = threading.RLock()
        self.key: IssuerKey | None = None
        self._load()

    def _load(self) -> None:
        try:
            if self.path and self.path.exists():
                self.key = IssuerKey(**json.loads(self.path.read_text()))
        except Exception:  # noqa: BLE001
            self.key = None

    def _save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.key:
                self.path.write_text(json.dumps(self.key.__dict__))
            elif self.path.exists():
                self.path.unlink()
        except OSError:
            pass  # the in-memory copy still works

    def enroll(self, jwk: dict, name: str, now: str) -> IssuerKey:
        with self.lock:
            if self.key:
                raise Refused("already_enrolled", "an issuer key is already enrolled; reset first", 409)
            public_key_from_jwk(jwk)
            self.key = IssuerKey(key_id_for(jwk), (name or "Issuer").strip()[:60] or "Issuer", clean_jwk(jwk), now)
            self._save()
            return self.key

    def reset(self) -> None:
        with self.lock:
            self.key = None
            self._save()

    def update(self, **fields) -> None:
        with self.lock:
            if self.key:
                for k, v in fields.items():
                    setattr(self.key, k, v)
                self._save()


def verify_request(store: KeyStore, body: dict, sheet_id: str | None = None, current_hash: str | None = None) -> dict:
    """Checks one signed request and returns the parsed payload. On success `last_seq` is advanced, so the same
    request can never be applied twice. Raises `Refused` with a stable code otherwise."""
    if not isinstance(body, dict) or not body.get("payload") or not body.get("sig") or not body.get("key_id"):
        raise Refused("unsigned", "a request needs payload, sig and key_id", 401)
    with store.lock:
        key = store.key
        if key is None:
            raise Refused("not_enrolled", "no issuer key is enrolled", 401)
        if body["key_id"] != key.key_id:
            raise Refused("unknown_key", "key_id is not the enrolled issuer key", 403)
        payload_text = body["payload"]
        if not isinstance(payload_text, str):
            raise Refused("bad_payload", "payload must be the signed JSON string", 400)
        check_signature(key.jwk, payload_text, str(body["sig"]))
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
        if sheet_id is not None and payload.get("sheet_id") != sheet_id:
            raise Refused("wrong_sheet", "the request is for another sheet", 409)
        if payload["type"] == "sign_sheet" and current_hash is not None and payload.get("sheet_hash") != current_hash:
            raise Refused("stale_hash", "the sheet changed after it was shown; look again and sign again", 409)
        key.last_seq = seq  # burned from here on, whatever happens next
        store._save()
        return payload
