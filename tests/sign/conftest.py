import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from fastapi import FastAPI
from fastapi.testclient import TestClient

from signoff.sign import api, persona, senso
from signoff.sign.verify import KeyStore, b64u_encode

from .standin import FakeCart, FakeEngine


class Phone:
    """What the browser does: an ECDSA P-256 key, a JSON payload string, a raw r||s signature."""

    def __init__(self, sheet_id="sheet1"):
        self.private = ec.generate_private_key(ec.SECP256R1())
        n = self.private.public_key().public_numbers()
        self.jwk = {"kty": "EC", "crv": "P-256", "x": b64u_encode(n.x.to_bytes(32, "big")),
                    "y": b64u_encode(n.y.to_bytes(32, "big"))}
        self.sheet_id, self.seq, self.key_id = sheet_id, 0, None

    def sign(self, payload_text, private=None):
        r, s = decode_dss_signature((private or self.private).sign(payload_text.encode(), ec.ECDSA(hashes.SHA256())))
        return b64u_encode(r.to_bytes(32, "big") + s.to_bytes(32, "big"))

    def request(self, type_, seq=None, **fields):
        if seq is None:
            self.seq += 1
            seq = self.seq
        payload = json.dumps({"type": type_, "sheet_id": self.sheet_id, "seq": seq, "at": "2026-11-20T12:00:00Z", **fields})
        return {"payload": payload, "sig": self.sign(payload), "key_id": self.key_id}


@pytest.fixture
def env(monkeypatch):
    engine, cart = FakeEngine(), FakeCart()
    monkeypatch.setattr(api, "get_engine", lambda: engine)
    monkeypatch.setattr(api, "get_cart", lambda: cart)
    monkeypatch.setattr(api, "keystore", KeyStore(path=None))
    monkeypatch.setattr(persona, "configured", lambda: False)
    monkeypatch.setattr(senso, "configured", lambda: False)  # no real Senso call from a unit test
    persona.reset()
    senso.reset()
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    phone = Phone()
    enrolled = client.post("/api/issuer/enroll", json={"public_key_jwk": phone.jwk, "name": "Dana"})
    assert enrolled.status_code == 200, enrolled.text
    phone.key_id = enrolled.json()["key_id"]
    return type("Env", (), {"client": client, "phone": phone, "engine": engine, "cart": cart})
