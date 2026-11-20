"""Enrolment needs the one-time code; the seal names the signer as self-declared until an identity check passes;
the store's cart total is compared with the signed total; a sheet that moves while signing is refused."""
from signoff.sign import api, persona

from .conftest import Phone


def enroll(client, code, name="Mallory"):
    return client.post("/api/issuer/enroll", json={"public_key_jwk": Phone().jwk, "name": name, "code": code})


def fresh(env):
    env.client.post("/api/admin/reset")
    return env


def test_enrolment_needs_the_code(env):
    fresh(env)
    assert enroll(env.client, "").json()["error"] == "bad_code"
    assert enroll(env.client, "000000").status_code == 403
    assert not api.keystore.key
    assert enroll(env.client, api.keystore.code, "Dana").status_code == 200


def test_wrong_codes_lock_enrolment_for_a_minute(env):
    fresh(env)
    for _ in range(5):
        assert enroll(env.client, "nope").status_code == 403
    locked = enroll(env.client, api.keystore.code)
    assert locked.status_code == 429 and locked.json()["error"] == "code_locked"
    api.keystore.locked_until = 0
    assert enroll(env.client, api.keystore.code).status_code == 200


def test_a_reset_makes_a_new_code(env):
    before = api.keystore.code
    env.client.post("/api/admin/reset")
    assert api.keystore.code != before
    assert enroll(env.client, before).status_code == 403          # the old code is dead


def test_the_code_is_shown_on_the_laptop_only(env):
    local = env.client.get("/api/issuer/enroll-code")
    assert local.status_code == 200 and local.json()["code"] == api.keystore.code and "code=" + api.keystore.code in local.json()["url"]
    tunnel = env.client.get("/api/issuer/enroll-code", headers={"cf-connecting-ip": "203.0.113.9"})
    assert tunnel.status_code == 403 and tunnel.json()["error"] == "local_only" and api.keystore.code not in tunnel.text
    forwarded = env.client.get("/api/issuer/enroll-code", headers={"x-forwarded-for": "203.0.113.9"})
    assert forwarded.status_code == 403
    monkey = env.client.get("/api/issuer/enroll-code", headers={"cf-ray": "abc", "x-admin-token": "wrong"})
    assert monkey.status_code == 403


def test_the_code_through_the_tunnel_with_the_admin_token(env, monkeypatch):
    monkeypatch.setenv("SIGNOFF_ADMIN_TOKEN", "s3cret")
    ok = env.client.get("/api/issuer/enroll-code", headers={"cf-ray": "abc", "x-admin-token": "s3cret"})
    assert ok.status_code == 200


def test_seal_says_self_declared_until_an_identity_check_passes(env, monkeypatch):
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    assert env.client.post("/api/issuer/request", json=body).status_code == 200
    seal = env.engine.state["seal"]["signature"]
    assert seal["name_basis"] == "self-declared" and seal["name"] == "Dana (self-declared)"


def test_seal_says_identity_checked_after_an_approved_inquiry(env, monkeypatch):
    monkeypatch.setattr(persona, "record", lambda: {"inquiry_id": "inq_1", "status": "approved", "verified": True, "sandbox": True,
                                                    "label": "identity checked (sandbox)"})
    monkeypatch.setattr(persona, "status", lambda: persona.record())
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    assert env.client.post("/api/issuer/request", json=body).status_code == 200
    seal = env.engine.state["seal"]["signature"]
    assert seal["name"] == "Dana (identity checked, sandbox)" and seal["persona"]["inquiry_id"] == "inq_1"


def test_a_store_total_that_differs_is_shown_with_both_numbers(env, monkeypatch):
    class Drift:
        calls = []
        def create_carts(self, picks):
            return [{"store": picks[0]["store"], "cart_id": "c", "cart_url": "https://x/c", "total_cents": 1234, "created_at": "t", "mode": "live"}]
    monkeypatch.setattr(api, "get_cart", lambda: Drift())
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    r = env.client.post("/api/issuer/request", json=body).json()
    assert r["ok"]
    for c in r["carts"]:
        assert c["total_differs"] is True and c["signed_total_cents"] != 1234
        assert "store total differs" in c["note"] and "$12.34" in c["note"] and "$%.2f" % (c["signed_total_cents"] / 100) in c["note"]


def test_matching_totals_are_not_flagged(env, monkeypatch):
    class Same:
        calls = []
        def create_carts(self, picks):
            price = {c["product"]["variant_id"]: c["product"]["price_cents"] for l in env.engine.state["lines"] for c in l["candidates"]}
            return [{"store": picks[0]["store"], "cart_id": "c", "cart_url": "https://x/c", "created_at": "t", "mode": "live",
                     "total_cents": sum(price[p["variant_id"]] for p in picks)}]
    monkeypatch.setattr(api, "get_cart", lambda: Same())
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    r = env.client.post("/api/issuer/request", json=body).json()
    assert r["ok"] and not any(c.get("total_differs") for c in r["carts"])


def test_a_sheet_that_moves_while_signing_is_not_signed(env, monkeypatch):
    class MovesTheSheet:
        calls = []
        def create_carts(self, picks):
            env.engine.state["total_cents"] += 1                   # a shopper fact changed the sheet mid-sign
            return [{"store": picks[0]["store"], "cart_id": "c", "cart_url": "https://x/c", "total_cents": None, "created_at": "t", "mode": "live"}]
    monkeypatch.setattr(api, "get_cart", lambda: MovesTheSheet())
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    r = env.client.post("/api/issuer/request", json=body)
    assert r.status_code == 409 and r.json()["error"] == "sheet_moved"
    assert not env.engine.state["seal"]["signed"]
