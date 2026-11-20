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
    assert r.status_code == 401 and r.json()["error"] == "unsigned" and r.json()["detail"] == "not signed by the approver's key"
    assert env.engine.calls == []


def test_tampered_payload_is_refused(env):
    body = env.phone.request("set_limit", **LIMIT)
    body["payload"] = body["payload"].replace("20.0", "16.0")
    assert post(env, body).json()["error"] == "unsigned"
    assert env.engine.calls == []


def test_garbage_signature_is_refused(env):
    body = env.phone.request("set_limit", **LIMIT)
    for sig in ("!!!", "AAAA", ""):
        body["sig"] = sig
        assert post(env, body).json()["error"] == "unsigned"
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
    assert post(env, body).json()["error"] == "unsigned"


def test_second_key_cannot_enrol(env):
    from tests.sign.conftest import Phone
    r = env.client.post("/api/issuer/enroll", json={"public_key_jwk": Phone().jwk, "name": "Mallory", "code": api.keystore.code})
    assert r.status_code == 409 and r.json()["error"] == "already_enrolled"


def test_enrol_again_only_after_reset(env):
    from tests.sign.conftest import Phone
    env.client.post("/api/admin/reset")
    r = env.client.post("/api/issuer/enroll", json={"public_key_jwk": Phone().jwk, "name": "Dana", "code": api.keystore.code})
    assert r.status_code == 200


def test_private_key_part_is_never_stored(env):
    from tests.sign.conftest import Phone
    env.client.post("/api/admin/reset")
    p = Phone()
    r = env.client.post("/api/issuer/enroll", json={"public_key_jwk": {**p.jwk, "d": "secret"}, "name": "Dana", "code": api.keystore.code})
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
    picks = [x for call in env.cart.calls for x in call]
    assert picks and all({"store", "variant_id", "quantity"} <= set(p) for p in picks)
    kind, signature, carts = env.engine.calls[-1]
    assert kind == "mark_signed" and signature["sheet_hash"] == env.engine.sheet_hash() and carts
    assert signature["name"] == "Dana (self-declared)" and signature["signer"]["name"] == "Dana" and signature["signer"]["key_id"] and signature["persona"]["label"] == "identity not checked"
    assert env.engine.state["seal"]["signed"]


def test_pick_up_lines_get_no_cart(env):
    sign(env)
    picked = {p["variant_id"] for call in env.cart.calls for p in call}
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
    made = len(env.cart.calls)  # one call per store
    assert post(env, body).status_code == 409
    assert len(env.cart.calls) == made


def test_signed_sheet_cannot_be_signed_or_changed_again(env):
    sign(env)
    made = len(env.cart.calls)
    assert sign(env).json()["error"] == "already_signed"
    assert post(env, env.phone.request("set_limit", **LIMIT)).json()["error"] == "already_signed"
    assert len(env.cart.calls) == made


def test_cart_failure_signs_nothing(env):
    env.cart.fail = True
    r = sign(env)
    assert r.status_code == 502 and r.json()["error"] == "cart_failed"
    assert not env.engine.state["seal"]["signed"]
    env.cart.fail = False
    assert sign(env).status_code == 200


def test_senso_conflict_blocks_signing(env):
    senso.set_checks([{"sentence": "A grab bar must be bought through a cart.", "verdict": "conflict", "blocks": True}])
    r = sign(env)
    assert r.status_code == 409 and r.json()["error"] == "senso_blocked"
    assert env.cart.calls == []


def test_unsupported_blocks_unless_relaxed(env, monkeypatch):
    rows = [{"sentence": "Our order requires a stair lift for the hall.", "verdict": "unsupported", "blocks": True}]
    senso.set_checks(rows)
    assert sign(env).json()["error"] == "senso_blocked"
    monkeypatch.setenv("SENSO_BLOCK_UNSUPPORTED", "0")
    assert sign(env).status_code == 200


def test_moved_limit_conflict_does_not_stop_the_signer(env):
    # a moved limit or a store sentence is shown with its verdict but does not stop the signature
    senso.set_checks([{"sentence": "The raised toilet seat must hold at least 350 lb.", "verdict": "conflict", "blocks": False}])
    assert sign(env).status_code == 200


def test_reset_clears_enrolment(env):
    env.client.post("/api/admin/reset")
    assert env.client.get("/api/issuer/status").json()["enrolled"] is False
    assert post(env, env.phone.request("set_limit", **LIMIT)).json()["error"] == "no_key"


def test_an_unsigned_request_gets_one_answer_whether_or_not_a_key_is_enrolled(env):
    """The laptop's "change this limit without the key" control: random signature bytes, a key id that is not ours."""
    import base64, os
    payload = '{"type":"set_limit","sheet_id":"sheet1","seq":5,"at":"x","limit_id":"L2.height","value":16}'
    forged = {"payload": payload, "sig": base64.urlsafe_b64encode(os.urandom(64)).decode().rstrip("="), "key_id": "this-screen"}
    with_key = post(env, forged)
    env.client.post("/api/admin/reset")                        # now nothing is enrolled
    without_key = post(env, forged)
    for r in (with_key, without_key):
        assert r.status_code == 401 and r.json()["error"] == "unsigned" and r.json()["detail"] == "not signed by the approver's key"
    # a phone that carries its own key id after a reset is told that no key is enrolled, as a different thing
    phone_after_reset = post(env, env.phone.request("set_limit", **LIMIT))
    assert phone_after_reset.json()["error"] == "no_key"
    assert env.engine.calls == []


def test_a_sign_request_refused_as_stale_is_spent_and_never_accepted_later(env):
    """The reviewer's sequence (H4): signed for hash A, the sheet moves to B, the request is refused; the sheet
    returns to A and the same bytes are sent again. Nobody tapped, so nothing is signed and no cart exists."""
    hash_a = env.engine.sheet_hash()
    body = env.phone.request("sign_sheet", sheet_hash=hash_a)        # she tapped once, for A
    was = env.engine.state["total_cents"]
    env.engine.state["total_cents"] = was + 100                        # the sheet moves to B without her
    assert env.engine.sheet_hash() != hash_a
    refused = post(env, body)
    assert refused.status_code == 409 and refused.json()["error"] == "stale_hash"
    env.engine.state["total_cents"] = was                              # and back to A
    assert env.engine.sheet_hash() == hash_a
    again = post(env, body)                                            # the same bytes, no new tap
    assert again.status_code == 409 and again.json()["error"] == "replayed_seq"
    assert env.cart.calls == [] and not env.engine.get_state()["seal"].get("signed")
    fresh = post(env, env.phone.request("sign_sheet", sheet_hash=hash_a))   # a new tap, a higher number: accepted
    assert fresh.status_code == 200 and fresh.json()["applied"] == "sign_sheet"


def test_the_approver_cannot_sign_over_a_measurement_its_owner_has_not_confirmed(env):
    """E34: while the engine's state lists an unconfirmed measurement, a sign request is refused in plain words,
    nothing is created, and the refused request is spent like any other."""
    env.engine.state["unconfirmed"] = ["tub_inside_width", "door_clear_opening"]
    env.engine.state["unconfirmed_text"] = "Elena has not confirmed: tub inside width, bathroom door clear opening"
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    refused = post(env, body)
    assert refused.status_code == 409 and refused.json()["error"] == "measurements_not_confirmed"
    assert refused.json()["detail"] == "Elena has not confirmed: tub inside width, bathroom door clear opening"
    assert env.cart.calls == [] and not env.engine.get_state()["seal"].get("signed")
    env.engine.state["unconfirmed"], env.engine.state["unconfirmed_text"] = [], None     # she confirmed them
    again = post(env, body)                                                              # the old tap is spent
    assert again.status_code == 409 and again.json()["error"] == "replayed_seq" and env.cart.calls == []
    signed = sign(env)                                                                   # a new tap signs
    assert signed.status_code == 200 and signed.json()["applied"] == "sign_sheet"
    limit = post(env, env.phone.request("set_limit", **LIMIT))                           # (already signed: refused as before)
    assert limit.status_code == 409
