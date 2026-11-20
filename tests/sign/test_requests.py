"""Forged, replayed, stale and unsigned requests are refused; a good one reaches the engine and the stores."""
import json

from cryptography.hazmat.primitives.asymmetric import ec

from signoff.sign import api, senso

LIMIT = {"limit_id": "L2.height", "value": 20.0}


def post(env, body):
    return env.client.post("/api/issuer/request", json=body)


def test_good_set_limit_reaches_engine(env):
    r = post(env, env.phone.request("set_limit", **LIMIT))
    assert r.status_code == 200 and r.json()["ok"]
    kind, action = env.engine.calls[-1][:2]
    assert kind == "apply_issuer" and action["limit_id"] == "L2.height" and action["value"] == 20.0
    assert action["signer"]["name"] == "Dana"


def test_unsigned_requests_are_refused(env):
    for body in ({}, {"payload": "{}"}, {"payload": "{}", "sig": "x"}, {"sig": "x", "key_id": env.phone.key_id}):
        r = post(env, body)
        assert r.status_code == 401 and r.json()["error"] == "unsigned"
    assert env.engine.calls == []


def test_forged_signature_is_refused(env):
    other = ec.generate_private_key(ec.SECP256R1())
    body = env.phone.request("set_limit", **LIMIT)
    body["sig"] = env.phone.sign(body["payload"], private=other)
    r = post(env, body)
    assert r.status_code == 403 and r.json()["error"] == "bad_signature"
    assert env.engine.calls == []


def test_tampered_payload_is_refused(env):
    body = env.phone.request("set_limit", **LIMIT)
    body["payload"] = body["payload"].replace("20.0", "16.0")
    assert post(env, body).json()["error"] == "bad_signature"
    assert env.engine.calls == []


def test_garbage_signature_is_refused(env):
    body = env.phone.request("set_limit", **LIMIT)
    for sig in ("!!!", "AAAA", ""):
        body["sig"] = sig
        assert post(env, body).status_code in (401, 403)
    assert env.engine.calls == []


def test_replayed_request_is_refused(env):
    body = env.phone.request("set_limit", **LIMIT)
    assert post(env, body).status_code == 200
    again = post(env, body)
    assert again.status_code == 409 and again.json()["error"] == "replayed_seq"
    assert len(env.engine.calls) == 1


def test_older_seq_is_refused(env):
    assert post(env, env.phone.request("set_limit", seq=50, **LIMIT)).status_code == 200
    assert post(env, env.phone.request("set_limit", seq=49, **LIMIT)).json()["error"] == "replayed_seq"
    assert post(env, env.phone.request("set_limit", seq=51, **LIMIT)).status_code == 200


def test_wrong_key_id_is_refused(env):
    body = env.phone.request("set_limit", **LIMIT)
    body["key_id"] = "0" * 16
    assert post(env, body).json()["error"] == "unknown_key"


def test_second_key_cannot_enrol(env):
    from tests.sign.conftest import Phone
    r = env.client.post("/api/issuer/enroll", json={"public_key_jwk": Phone().jwk, "name": "Mallory"})
    assert r.status_code == 409 and r.json()["error"] == "already_enrolled"


def test_enrol_again_only_after_reset(env):
    from tests.sign.conftest import Phone
    env.client.post("/api/admin/reset")
    r = env.client.post("/api/issuer/enroll", json={"public_key_jwk": Phone().jwk, "name": "Dana"})
    assert r.status_code == 200


def test_private_key_part_is_never_stored(env):
    from tests.sign.conftest import Phone
    env.client.post("/api/admin/reset")
    p = Phone()
    r = env.client.post("/api/issuer/enroll", json={"public_key_jwk": {**p.jwk, "d": "secret"}, "name": "Dana"})
    assert r.status_code == 200 and "d" not in api.keystore.key.jwk


def test_limit_out_of_range_or_not_issuers_is_refused(env):
    assert post(env, env.phone.request("set_limit", limit_id="L2.height", value=40)).json()["error"] == "out_of_range"
    assert post(env, env.phone.request("set_limit", limit_id="L2.height", value=19.3)).json()["error"] == "off_step"
    assert post(env, env.phone.request("set_limit", limit_id="L1.tub", value=20)).json()["error"] == "not_an_issuer_limit"
    assert post(env, env.phone.request("set_limit", limit_id="nope", value=20)).json()["error"] == "not_an_issuer_limit"
    assert env.engine.calls == []


def test_wrong_sheet_is_refused(env):
    env.phone.sheet_id = "sheet2"
    assert post(env, env.phone.request("set_limit", **LIMIT)).json()["error"] == "wrong_sheet"


def test_strike_needs_reason_and_a_real_product(env):
    line = env.engine.state["lines"][1]
    key = line["candidates"][0]["product"]["product_key"]
    assert post(env, env.phone.request("strike", line_id="L2", product_key=key, reason=" ")).json()["error"] == "reason_needed"
    assert post(env, env.phone.request("strike", line_id="L2", product_key="no such", reason="x")).json()["error"] == "unknown_product"
    ok = post(env, env.phone.request("strike", line_id="L2", product_key=key, reason="he does not like it"))
    assert ok.status_code == 200


# ---- sign_sheet -----------------------------------------------------------------------------------------

def sign(env, **over):
    fields = {"sheet_hash": env.engine.sheet_hash(), **over}
    return post(env, env.phone.request("sign_sheet", **fields))


def test_sign_creates_carts_and_marks_signed(env):
    r = sign(env)
    assert r.status_code == 200, r.text
    picks = env.cart.calls[0]
    assert picks and all(set(p) == {"store", "variant_id", "quantity"} for p in picks)
    kind, signature, carts = env.engine.calls[-1]
    assert kind == "mark_signed" and signature["sheet_hash"] == env.engine.sheet_hash() and carts
    assert signature["name"] == "Dana" and signature["signer"]["key_id"] and signature["persona"]["label"] == "identity not checked"
    assert env.engine.state["seal"]["signed"]


def test_pick_up_lines_get_no_cart(env):
    sign(env)
    picked = {p["variant_id"] for p in env.cart.calls[0]}
    state = env.engine.state
    grab_bar = next(l for l in state["lines"] if l["line_id"] == "L5")
    cand = next(c for c in grab_bar["candidates"] if c["id"] == grab_bar["pick"])
    assert cand["product"]["variant_id"] not in picked


def test_stale_hash_is_refused_and_nothing_is_created(env):
    r = sign(env, sheet_hash="0" * 64)
    assert r.status_code == 409 and r.json()["error"] == "stale_hash"
    assert env.cart.calls == [] and env.engine.calls == []


def test_hash_changes_after_a_limit_move(env):
    before = env.engine.sheet_hash()
    post(env, env.phone.request("set_limit", **LIMIT))
    stale = post(env, env.phone.request("sign_sheet", sheet_hash=before))
    assert stale.json()["error"] == "stale_hash" and env.cart.calls == []


def test_replayed_sign_is_refused(env):
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    assert post(env, body).status_code == 200
    assert post(env, body).status_code == 409
    assert len(env.cart.calls) == 1


def test_signed_sheet_cannot_be_signed_or_changed_again(env):
    sign(env)
    assert sign(env).json()["error"] == "already_signed"
    assert post(env, env.phone.request("set_limit", **LIMIT)).json()["error"] == "already_signed"
    assert len(env.cart.calls) == 1


def test_cart_failure_signs_nothing(env):
    env.cart.fail = True
    r = sign(env)
    assert r.status_code == 502 and r.json()["error"] == "cart_failed"
    assert not env.engine.state["seal"]["signed"]
    env.cart.fail = False
    assert sign(env).status_code == 200


def test_senso_conflict_blocks_signing(env):
    senso.set_checks([{"sentence": "Returns in 90 days", "verdict": "conflict"}])
    r = sign(env)
    assert r.status_code == 409 and r.json()["error"] == "senso_blocked"
    assert env.cart.calls == []
    senso.set_checks([{"sentence": "Returns in 30 days", "verdict": "supported"}])
    assert sign(env).status_code == 200


def test_reset_clears_enrolment(env):
    env.client.post("/api/admin/reset")
    assert env.client.get("/api/issuer/status").json()["enrolled"] is False
    assert post(env, env.phone.request("set_limit", **LIMIT)).json()["error"] == "not_enrolled"
