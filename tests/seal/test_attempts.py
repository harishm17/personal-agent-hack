"""K6: the page's four attempts as real POSTs to SIGN's real route (`/api/issuer/request`), before she signs and
after. Each asserts the server's status and error, that the refusal is a receipt in the run's chain, and that the key,
`seq`, the engine and the carts are as they were. The engine and the store are SIGN's own test stand-ins."""
import json

import pytest
from signoff.engine import receipts
from signoff.seal import api as seal
from signoff.sign import api as sign
from signoff.sign.verify import KeyStore
from tests.sign.conftest import Phone, _make_env
from tests.sign.standin import FakeEngine


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SIGNOFF_RECEIPTS", "memory")  # the chain is kept in memory: no file in data/receipts
    receipts.start("test")
    return _make_env(monkeypatch, FakeEngine(), "sheet1")


def bodies(env, signed_request=None):
    """The requests web/seal/seal.js builds, in its own layout."""
    base = lambda kind: {"type": kind, "sheet_id": "sheet1", "seq": 1795215600000, "at": "2026-11-20T15:15:00.000Z"}  # noqa: E731
    sign_sheet = json.dumps({**base("sign_sheet"), "sheet_hash": env.engine.sheet_hash()})
    stranger = Phone("sheet1")  # a new P-256 key that was never enrolled
    out = {"nosig": ({"payload": sign_sheet, "key_id": env.phone.key_id}, 401, "unsigned", "sign_sheet"),
           "newkey": ({"payload": sign_sheet, "sig": stranger.sign(sign_sheet), "key_id": env.phone.key_id}, 401, "unsigned", "sign_sheet"),
           "limit": ({"payload": json.dumps({**base("set_limit"), "limit_id": "L1.capacity", "value": 250}),
                      "key_id": env.phone.key_id}, 401, "unsigned", "set_limit")}
    if signed_request:
        out["replay"] = (signed_request, 409, "replayed_seq", "sign_sheet")
    return out


def run(env, attempts):
    for name, (body, status, error, request) in attempts.items():
        before = seal.refused(receipts.chain()["receipts"])
        calls, carts, seq = list(env.engine.calls), list(env.cart.calls), sign.keystore.key.last_seq
        answer = env.client.post("/api/issuer/request", json=body)
        assert (answer.status_code, answer.json()["error"]) == (status, error), name
        after = seal.refused(receipts.chain()["receipts"])
        assert len(after) == len(before) + 1 and after[-1]["request"] == request and after[-1]["why"].startswith(error), name
        assert env.engine.calls == calls and env.cart.calls == carts and sign.keystore.key.last_seq == seq, name


def test_before_she_signs_every_attempt_is_refused_and_recorded(env):
    run(env, bodies(env))
    assert not env.engine.get_state()["seal"].get("signed")


def test_after_she_signs_every_attempt_is_refused_and_recorded(env):
    real = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    assert env.client.post("/api/issuer/request", json=real).status_code == 200
    run(env, bodies(env, signed_request=real))
    assert receipts.check(receipts.chain()["receipts"])["verified"] is True  # the chain with the refusals in it still links


def test_with_no_key_enrolled_a_new_key_is_told_so(env, monkeypatch):
    monkeypatch.setattr(sign, "keystore", KeyStore(path=None))
    stranger = Phone("sheet1")
    text = json.dumps({"type": "sign_sheet", "sheet_id": "sheet1", "seq": 1, "sheet_hash": env.engine.sheet_hash()})
    from signoff.sign.verify import key_id_for
    answer = env.client.post("/api/issuer/request", json={"payload": text, "sig": stranger.sign(text), "key_id": key_id_for(stranger.jwk)})
    assert (answer.status_code, answer.json()["error"]) == (401, "no_key")
    assert env.client.post("/api/issuer/request", json={"payload": text}).json()["error"] == "unsigned"
    assert [r["why"].split(":")[0] for r in seal.refused(receipts.chain()["receipts"])][-2:] == ["no_key", "unsigned"]
