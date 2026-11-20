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


def test_carts_are_made_from_the_engines_signed_picks_and_the_sheet_is_released_on_failure(env):
    env.cart.fail = True
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    r = env.client.post("/api/issuer/request", json=body)
    assert r.status_code == 502 and env.engine.held is False       # the hold ends when no store made a cart
    assert any(c[0] == "release_signing" for c in env.engine.calls)
    env.cart.fail = False
    ok = env.client.post("/api/issuer/request", json=body)         # the same request goes through
    assert ok.status_code == 200 and env.engine.held is False
    sent = {p["variant_id"] for call in env.cart.calls for p in call}
    assert sent == {p["variant_id"] for p in env.engine.signed_picks(env.engine.sheet_hash())}


def test_a_stale_hash_at_signed_picks_is_the_sheet_moved_refusal(env, monkeypatch):
    real = env.engine.signed_picks
    def moves(h):
        env.engine.state["total_cents"] += 1
        return real(h)
    monkeypatch.setattr(env.engine, "signed_picks", moves)
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    r = env.client.post("/api/issuer/request", json=body)
    assert r.status_code == 409 and r.json()["error"] == "sheet_moved" and env.cart.calls == []


class LinesCart:
    calls = []
    def __init__(self, change=None):
        self.change = change or {}
    def create_carts(self, picks):
        lines = [{"variant_id": p["variant_id"], "quantity": p["quantity"], "unit_price_cents": p["price_cents"]} for p in picks]
        for l in lines:
            l.update(self.change)
        return [{"store": picks[0]["store"], "cart_id": "c", "cart_url": "https://x/c", "created_at": "t", "mode": "live",
                 "total_cents": sum(l["unit_price_cents"] * l["quantity"] for l in lines), "lines": lines}]


def test_matching_cart_lines_are_checked_and_clean(env, monkeypatch):
    monkeypatch.setattr(api, "get_cart", lambda: LinesCart())
    r = env.client.post("/api/issuer/request", json=env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())).json()
    assert r["ok"] and all(c["lines_checked"] and not c.get("line_differences") for c in r["carts"])


def test_a_changed_unit_price_or_quantity_is_shown_with_both_values(env, monkeypatch):
    monkeypatch.setattr(api, "get_cart", lambda: LinesCart({"quantity": 2}))
    r = env.client.post("/api/issuer/request", json=env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())).json()
    c = r["carts"][0]
    assert c["line_differences"][0]["field"] == "quantity" and c["line_differences"][0]["signed"] == 1 and c["line_differences"][0]["store"] == 2
    assert "store cart differs" in c["note"] and "signed 1, store 2" in c["note"]


def test_a_line_the_store_added_or_dropped_is_shown(env, monkeypatch):
    class Wrong(LinesCart):
        def create_carts(self, picks):
            out = super().create_carts(picks)
            out[0]["lines"] = out[0]["lines"][1:] + [{"variant_id": "gid://x/OTHER", "quantity": 1, "unit_price_cents": 5}]
            return out
    monkeypatch.setattr(api, "get_cart", lambda: Wrong())
    r = env.client.post("/api/issuer/request", json=env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())).json()
    fields = {(d["field"], d["signed"], d["store"]) for c in r["carts"] for d in c.get("line_differences", [])}
    assert ("line", "present", "missing") in fields and ("line", "absent", "present") in fields


def test_a_store_client_that_returns_no_lines_is_said_not_to_be_checked(env):
    r = env.client.post("/api/issuer/request", json=env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())).json()
    assert all(c["lines_checked"] is False for c in r["carts"])


def test_a_relay_claim_is_attached_and_named(env, monkeypatch):
    from signoff import relay
    monkeypatch.setattr(relay, "status", lambda: {"claim_type": "live_human_presence", "result": "passed", "sandbox": True})
    env.client.post("/api/issuer/request", json=env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash()))
    sig = env.engine.state["seal"]["signature"]
    assert sig["relay"]["result"] == "passed" and sig["name"] == "Dana (live human checked, sandbox)"
