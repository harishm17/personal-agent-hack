import json
import pathlib
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from signoff.engine import api, state

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def fixture_inputs(monkeypatch, tmp_path):
    """The fixture pool, whatever is in data/ on this machine."""
    monkeypatch.setattr(state, "DATA", tmp_path)
    monkeypatch.setattr(state, "_load_pool", lambda: (json.loads((ROOT / "fixtures" / "pool.json").read_text()),
                                                      json.loads((ROOT / "fixtures" / "store_answers.json").read_text())))
    monkeypatch.setattr(state, "_record", lambda s: None)
    state.reset()
    yield
    state._s["loaded"] = False


def line(s, line_id):
    return next(l for l in s["lines"] if l["line_id"] == line_id)


def includes(got, want, path="state"):
    """Every key and value of the fixture is in the live state; the live state may add keys."""
    if isinstance(want, dict):
        for k, v in want.items():
            assert k in got, "%s.%s missing" % (path, k)
            includes(got[k], v, "%s.%s" % (path, k))
    elif isinstance(want, list):
        assert len(got) == len(want), path
        for i, (g, w) in enumerate(zip(got, want)):
            includes(g, w, "%s[%d]" % (path, i))
    else:
        assert got == want, path


def test_live_state_has_the_shape_and_values_of_the_fixture():
    want = json.loads((ROOT / "fixtures" / "state.json").read_text())
    want.pop("version")
    includes(json.loads(state.state_json()), want)
    assert state.get_state()["mode"] == "fixture"


def test_a_limit_change_through_apply_issuer_moves_the_l2_pick():
    assert line(state.get_state(), "L2")["pick"] == "L2:fixture-store-a.example:fx-A"
    v, h = state.get_state()["version"], state.sheet_hash()
    after = state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 425})
    assert line(after, "L2")["pick"] == "L2:fixture-store-c.example:fx-D"
    assert after["version"] > v and state.sheet_hash() != h
    back = state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 300})
    assert line(back, "L2")["pick"] == "L2:fixture-store-a.example:fx-A" and state.sheet_hash() == h


def test_limits_are_refused_outside_their_range_or_when_they_are_not_the_issuers():
    for action in ({"type": "set_limit", "limit_id": "L2.capacity", "value": 5000},
                   {"type": "set_limit", "limit_id": "L2.capacity", "value": "300"},
                   {"type": "set_limit", "limit_id": "L1.tub", "value": 30},
                   {"type": "set_limit", "limit_id": "L9.none", "value": 300},
                   {"type": "strike", "line_id": "L2", "product_key": "not in the pool", "reason": "x"},
                   {"type": "create_cart"}):
        with pytest.raises(state.EngineError):
            state.apply_issuer(action)


def test_strike_and_unstrike():
    s = state.apply_issuer({"type": "strike", "line_id": "L2", "product_key": "fixture a", "reason": "seat too soft"})
    l2 = line(s, "L2")
    assert l2["status"] == "next_candidate" and l2["pick"] == "L2:fixture-store-c.example:fx-D"
    assert l2["struck"][0]["reason"] == "seat too soft" and l2["candidates"][0]["status"] == "struck"
    s = state.apply_issuer({"type": "unstrike", "line_id": "L2", "product_key": "fixture a"})
    assert line(s, "L2")["status"] == "ready" and line(s, "L2")["pick"] == "L2:fixture-store-a.example:fx-A"


def test_shopper_fact_changes_the_sum_and_is_hers_to_change():
    s = state.set_shopper_fact("toilet_rim_height", 14.0)  # 14 + 5 = 19 >= 19: nothing to spare
    assert line(s, "L2")["tightest"]["text"] == "nothing to spare"
    s = state.set_shopper_fact("toilet_rim_height", 13.5)  # 13.5 + 5 = 18.5: A is out, D (5 in) is out too
    assert line(s, "L2")["pick"] is None
    with pytest.raises(state.EngineError):
        state.set_shopper_fact("toilet_rim_height", 40)
    with pytest.raises(state.EngineError):
        state.set_shopper_fact("L2.capacity", 200)


def test_signing_seals_the_hash_and_freezes_the_sheet():
    h = state.sheet_hash()
    assert state.apply_issuer({"type": "sign_sheet", "sheet_hash": h})["seal"]["signed"] is False
    with pytest.raises(state.EngineError):
        state.apply_issuer({"type": "sign_sheet", "sheet_hash": "0" * 64})
    carts = [{"store": "fixture-store-a.example", "cart_id": "c1", "cart_url": "https://fixture-store-a.example/cart/c1",
              "total_cents": 1, "created_at": "2026-11-20T14:00:00-08:00", "mode": "fixture"}]
    with pytest.raises(state.EngineError):
        state.mark_signed({"key_id": "k1", "name": "Dana"}, carts)  # no signed hash: nothing to seal
    s = state.mark_signed({"key_id": "k1", "name": "Dana", "at": "2026-11-20T14:00:00-08:00", "sheet_hash": h}, carts)
    assert s["seal"]["signed"] and s["seal"]["sheet_hash"] == h and s["seal"]["current"] is True
    assert s["seal"]["text"] == "Signed by Dana at 14:00. 1 cart created."
    picked = [c for l in s["lines"] for c in l["candidates"] if c["picked"] and c["action"]]
    assert picked and all(c["action"]["cart_url"].endswith("/cart/c1") for c in picked)
    with pytest.raises(state.EngineError) as refused:
        state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 425})
    assert refused.value.status == 409
    s = state.reset()
    assert s["seal"] == {"signed": False, "text": "Not signed. No cart exists at any store.", "sheet_hash": None,
                         "signature": None, "carts": [], "covers": state.COVERS}


def test_reset_puts_the_sheet_back_as_on_disk():
    state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 425})
    state.set_shopper_fact("toilet_rim_height", 16.0)
    state.set_issuer_key({"enrolled": True, "key_id": "k1"})
    assert state.get_state()["issuer_key"]["enrolled"] is True
    s = state.reset()
    assert s["issuer_key"]["enrolled"] is False
    assert s["sheet"] == json.loads((ROOT / "sheets" / "sheet1.json").read_text())


def test_reload_keeps_the_issuers_changes():
    state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 425})
    s = state.reload_data()
    assert line(s, "L2")["pick"] == "L2:fixture-store-c.example:fx-D"


def test_recompute_is_fast_enough_for_a_slider():
    start = time.perf_counter()
    for i in range(20):
        state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 300 + 25 * (i % 5)})
    assert (time.perf_counter() - start) / 20 < 0.05


def test_routes():
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    s = client.get("/api/state").json()
    assert len(s["lines"]) == 6 and s["seal"]["signed"] is False
    assert client.post("/api/shopper/fact", json={"fact_id": "toilet_rim_height", "value": 14.0}).json()["ok"]
    assert client.get("/api/state").json()["version"] == s["version"] + 1
    assert client.post("/api/shopper/fact", json={"fact_id": "nope", "value": 1}).status_code == 404
    assert client.post("/api/shopper/fact", json={"fact_id": "toilet_rim_height", "value": 99}).status_code == 400
    c = client.get("/api/sheet/canonical").json()
    assert c["sheet_hash"] == state.sheet_hash() and json.loads(c["canonical"])["sheet_id"] == "sheet1"
    # no engine route can change a limit, strike a product or sign
    paths = {r.path for r in api.router.routes}
    assert paths == {"/api/state", "/api/events", "/api/shopper/fact", "/api/sheet/canonical", "/api/shopper/say",
                     "/api/drill/session", "/api/drill/say", "/api/drill/state", "/api/receipts", "/api/receipts/verify",
                     "/api/sheets", "/api/admin/use-sheet", "/api/reads/ledger", "/api/shopper/choose",
                     "/api/shopper/pick_rule"}


def test_the_reader_can_be_switched_to_another_readers_run(tmp_path):
    with pytest.raises(state.EngineError):
        state.set_reader("sie:no-such-model")
    assert state.set_reader(None)["mode"] == "fixture"


def test_reset_is_complete_and_text_checks_follow_the_sheet_they_were_run_on():
    original = state.sheet_hash()
    state.set_senso([{"id": "c1", "verdict": "verified", "candidate_id": "L2:fixture-store-a.example:fx-A"}])
    s = state.get_state()
    assert s["senso_current"] is True and line(s, "L2")["candidates"][0]["senso"]["claims"][0]["id"] == "c1"
    s = state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 425})
    assert s["senso"][0]["id"] == "c1" and s["senso_current"] is False  # shown, marked as run on an earlier sheet
    state.apply_issuer({"type": "strike", "line_id": "L2", "product_key": "fixture d", "reason": "x"})
    state.set_shopper_fact("mattress_thickness", 9.0)
    state.set_issuer_key({"enrolled": True, "key_id": "k"})
    state.mark_signed({"name": "Dana", "at": "2026-11-20T14:00:00-08:00", "sheet_hash": state.sheet_hash()}, [])
    started = time.perf_counter()
    s = state.reset()
    assert time.perf_counter() - started < 0.2
    assert state.sheet_hash() == original and s["senso_current"] is True and s["seal"]["signed"] is False
    assert s["issuer_key"]["enrolled"] is False and [k["product_key"] for k in line(s, "L2")["struck"]] == []
    assert s["sheet"] == json.loads((ROOT / "sheets" / "sheet1.json").read_text())
    assert state.set_shopper_fact("mattress_thickness", 12.0)["version"] > s["version"]  # open for changes again


def test_a_change_between_verification_and_sealing_is_never_sealed_as_if_signed():
    """The seal race: the phone signed hash H, the stores are being called, and a measurement changes."""
    signed = state.sheet_hash()  # what SIGN verified against
    state.set_shopper_fact("toilet_rim_height", 14.0)  # arrives while the carts are being created
    assert state.sheet_hash() != signed
    with pytest.raises(state.EngineError) as refused:
        state.mark_signed({"name": "Dana", "sheet_hash": signed}, [{"store": "fixture-store-a.example", "cart_id": "c1"}])
    assert refused.value.status == 409 and "changed after it was signed" in str(refused.value)
    s = state.get_state()
    assert s["seal"]["signed"] is False and s["seal"]["carts"] == [] and s["seal"]["sheet_hash"] is None


def test_signed_picks_are_those_of_exactly_the_signed_hash_and_hold_the_sheet_until_it_is_sealed():
    signed = state.sheet_hash()
    with pytest.raises(state.EngineError):
        state.signed_picks("0" * 64)
    picks = state.signed_picks(signed)
    want = {l["pick"] for l in state.get_state()["lines"] if l["status"] in ("ready", "next_candidate")}
    assert {p["candidate_id"] for p in picks} == want and all(p["quantity"] == 1 for p in picks)
    assert set(picks[0]) >= {"store", "variant_id", "quantity", "line_id", "price_cents"}
    assert state.get_state()["version"] and state._recompute(record=False)["signing"]["in_progress"] is True
    for change in (lambda: state.set_shopper_fact("toilet_rim_height", 14.0),
                   lambda: state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 425})):
        with pytest.raises(state.EngineError) as held:
            change()
        assert held.value.status == 409 and "being signed" in str(held.value)
    s = state.mark_signed({"name": "Dana", "sheet_hash": signed, "at": "2026-11-20T14:00:00-08:00"}, [])
    assert s["seal"]["signed"] and s["seal"]["sheet_hash"] == signed == state.sheet_hash() and "signing" not in s
    state.reset()
    state.signed_picks(state.sheet_hash())
    state.release_signing()  # the stores refused: the hold ends and the sheet can change again
    assert state.set_shopper_fact("toilet_rim_height", 14.0)["seal"]["signed"] is False


def test_the_hash_covers_the_pick_rule_and_each_picks_delivery_quote():
    canonical = json.loads(state.canonical_sheet())
    assert canonical["pick_rule"] == {"id": "cheapest_with_delivery_time", "label": "cheapest that states a delivery time",
                                      "set_by": "shopper"}
    l2 = next(l for l in canonical["lines"] if l["line_id"] == "L2")
    assert l2["pick"]["delivery"]["quote"] == "standard shipping takes 3 to 5 days" and l2["pick"]["delivery"]["status"] == "stated"
    assert state.get_state()["seal"]["covers"] == state.COVERS and "delivery quotes" in state.COVERS \
        and "pick rule" in state.COVERS and "variant and quantity" in state.COVERS
    assert l2["pick"]["quantity"] == 1 and "currency" in l2["pick"] and "variant_title" in l2["pick"]
    before = state.sheet_hash()
    state._s["answers"][0]["delivery"]["quote"] = "standard shipping takes 2 to 9 days"  # the store's words change
    assert state._recompute(record=False)["sheet_hash"] != before
    state._s["sheet"]["pick_rule"]["label"] = "dearest first"
    assert state._recompute(record=False)["sheet_hash"] != before


def test_a_cart_that_is_pending_or_failed_is_not_counted_as_created_and_a_second_call_keeps_the_signing_time():
    h = state.sheet_hash()
    signature = {"name": "Dana", "sheet_hash": h, "at": "2026-11-20T14:00:00-08:00"}
    carts = [{"store": "fixture-store-a.example", "cart_id": "c1", "cart_url": "https://a/cart/c1", "mode": "real"},
             {"store": "fixture-store-c.example", "cart_id": None, "cart_url": None, "mode": "pending"}]
    s = state.mark_signed(signature, carts)
    assert s["seal"]["text"] == "Signed by Dana at 14:00. 1 cart created. 1 store has not answered yet."
    acted = {c["product"]["store"] for l in s["lines"] for c in l["candidates"] if c["action"]}
    assert acted == {"fixture-store-a.example"}  # only a cart with a link counts as created
    carts[1] = {"store": "fixture-store-c.example", "cart_id": "c2", "cart_url": "https://c/cart/c2", "mode": "real"}
    s = state.mark_signed(dict(signature, at="2026-11-20T14:00:09-08:00"), carts)  # the store answered
    assert s["seal"]["signed_at"] == "2026-11-20T14:00:00-08:00" and s["seal"]["text"] == "Signed by Dana at 14:00. 2 carts created."
    from signoff.engine import receipts
    assert [r["type"] for r in receipts.chain()["receipts"]][-3:] == ["signed", "carts_created", "carts_updated"]


def test_a_fallback_in_use_is_named_in_the_state_never_silent(monkeypatch):
    from signoff.engine import health
    assert state.get_state()["degraded"] == []
    health.note("pool loader", "signoff.store.pool.load() failed (ValueError); the pool was read straight from the files")
    try:
        s = state.set_shopper_fact("toilet_rim_height", 15.5)
        assert s["degraded"] == [{"what": "pool loader", "note": "signoff.store.pool.load() failed (ValueError); "
                                  "the pool was read straight from the files"}]
    finally:
        health.clear("pool loader")
    assert state.set_shopper_fact("toilet_rim_height", 15.0)["degraded"] == []


def test_what_memory_recalls_is_applied_at_the_start_of_a_run_and_nowhere_else(monkeypatch):
    import sys
    import types
    asked = []

    def recall(sheet):
        asked.append(sheet["id"])
        return {"facts": [{"fact_id": "toilet_rim_height", "value": 14.0, "measured_by": "Elena", "measured_at": "2026-11-18T09:00:00-08:00"},
                          {"fact_id": "toilet_rim_height", "value": 99.0}, {"fact_id": "not_a_fact", "value": 1}],
                "strikes": [{"line_id": "L2", "product_key": "fixture a", "reason": "seat too soft (remembered)"},
                            {"line_id": "L2", "product_key": "not in the pool", "reason": "x"}]}
    fake = types.ModuleType("signoff.memory")
    fake.recall = recall
    monkeypatch.setitem(sys.modules, "signoff.memory", fake)
    import signoff
    monkeypatch.setattr(signoff, "memory", fake, raising=False)
    s = state.reset()
    fact = next(f for f in s["sheet"]["shopper_facts"] if f["id"] == "toilet_rim_height")
    assert (fact["value"], fact["remembered"], fact["measured_by"]) == (14.0, True, "Elena")
    l2 = line(s, "L2")
    assert l2["struck"][0]["from_memory"] is True and l2["struck"][0]["reason"] == "seat too soft (remembered)"
    assert next(c for c in l2["candidates"] if c["product"]["product_key"] == "fixture a")["status"] == "struck"
    assert len(s["memory"]["facts"]) == 1 and len(s["memory"]["strikes"]) == 1 and len(s["memory"]["ignored"]) == 3
    assert "fixture a" in state.canonical_sheet()  # a remembered strike is under the hash like any other
    # it is undone only the way any strike is: by the issuer's request
    s = state.apply_issuer({"type": "unstrike", "line_id": "L2", "product_key": "fixture a"})
    assert line(s, "L2")["struck"] == [] and asked == ["sheet1"]  # memory is asked once, at the start, not on a change

    def broken(sheet):
        raise RuntimeError("memory store is down")
    fake.recall = broken
    s = state.reset()
    assert "memory" not in s and [d["what"] for d in s["degraded"]] == ["memory"]
    assert next(f for f in s["sheet"]["shopper_facts"] if f["id"] == "toilet_rim_height")["value"] == 15.0


def test_the_shopper_may_choose_any_candidate_that_passes_and_nothing_that_does_not():
    s = state.get_state()
    l2 = line(s, "L2")
    rule_pick, before = l2["pick"], state.sheet_hash()
    assert l2["picked_by"] == "rule" and rule_pick.endswith("fx-A")
    by = {c["product"]["product_id"]: c for c in l2["candidates"]}
    assert by["fx-D"]["status"] == "inside" and by["fx-F"]["status"] == "outside" and by["fx-H"]["status"] == "not_stated"
    for refused in ("fx-F", "fx-H"):                                   # outside, not stated: she cannot choose past a limit
        with pytest.raises(state.EngineError) as error:
            state.set_shopper_choice("L2", by[refused]["id"])
        assert error.value.status == 409 and "cannot be chosen" in str(error.value)
    with pytest.raises(state.EngineError):
        state.set_shopper_choice("L3", next(c["id"] for c in line(s, "L3")["candidates"] if c["status"] == "struck"))
    s = state.set_shopper_choice("L2", by["fx-D"]["id"])               # D is dearer, and inside: her choice
    l2 = line(s, "L2")
    assert l2["pick"] == by["fx-D"]["id"] and l2["picked_by"] == "shopper" and l2["why"]["pick_price_cents"] == 7999
    assert [c["product"]["product_id"] for c in l2["candidates"] if c["picked"]] == ["fx-D"]
    assert state.sheet_hash() != before and '"picked_by":"shopper"' in state.canonical_sheet()  # the approver signs it knowingly
    assert s["total_cents"] == sum(c["product"]["price_cents"] for l in s["lines"] for c in l["candidates"]
                                   if c["picked"] and l["status"] in ("ready", "next_candidate"))
    # a limit change that puts her choice outside drops it back to the rule, and says so
    s = state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 475})   # D holds 450
    l2 = line(s, "L2")
    assert l2["picked_by"] in ("rule", None) and l2["pick"] != by["fx-D"]["id"]
    assert "no longer inside the limits" in l2["choice_dropped"]["why"] and by["fx-D"]["id"] not in state._s["choices"].values()
    state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 300})
    s = state.set_shopper_choice("L2", by["fx-D"]["id"])
    s = state.set_shopper_choice("L2", None)                           # back to the rule
    assert line(s, "L2")["pick"] == rule_pick and line(s, "L2")["picked_by"] == "rule" and state.sheet_hash() == before
    from signoff.engine import receipts
    assert [r["type"] for r in receipts.chain()["receipts"]].count("shopper_choice") == 3


def test_the_name_the_approver_reads_is_under_the_hash():
    """H1: the same ids with another product name must not sign to the same fingerprint."""
    s = state.get_state()
    before = state.sheet_hash()
    pick = next(c for c in line(s, "L2")["candidates"] if c["picked"])
    sheet = json.loads(state.canonical_sheet())
    assert next(l for l in sheet["lines"] if l["line_id"] == "L2")["pick"]["title"] == pick["product"]["title"]
    row = next(p for p in state._s["pool"] if p["product_id"] == pick["product"]["product_id"] and "L2" in p["line_ids"])
    row["title"] = "Another name on the same ids"
    state._recompute(why="test")
    assert state.sheet_hash() != before and "Another name on the same ids" in state.canonical_sheet()
    assert "product name" in state.COVERS
    # the words of each limit and the reason for a strike are shown at signing too, so they are signed too
    assert next(l for l in sheet["lines"] if l["line_id"] == "L2")["limits"][0]["name"]
    limit = state._s["sheet"]["lines"][1]["limits"][0]
    now, limit["label"] = state.sheet_hash(), "at most"                 # the word shown beside the number
    state._recompute(why="test")
    assert state.sheet_hash() != now and json.loads(state.canonical_sheet())["lines"][1]["limits"][0]["label"] == "at most"
    now, state._s["sheet"]["pick_rule"]["set_by"] = state.sheet_hash(), "somebody else"   # who chose the ordering
    state._recompute(why="test")
    assert state.sheet_hash() != now
    struck = next(l for l in s["lines"] if l["struck"])
    signed = next(l for l in json.loads(state.canonical_sheet())["lines"] if l["line_id"] == struck["line_id"])
    assert signed["strike_reasons"] == {x["product_key"]: x["reason"] for x in struck["struck"]}


def test_one_value_has_one_fingerprint_however_it_arrived():
    """H5: a limit or a measurement set to another value and back gives the first hash again."""
    first, text = state.sheet_hash(), state.canonical_sheet()
    state.apply_issuer({"type": "set_limit", "limit_id": "L5.length", "value": 20})     # 16.0 in the sheet file
    assert state.sheet_hash() != first
    state.apply_issuer({"type": "set_limit", "limit_id": "L5.length", "value": 16})     # back, typed as a whole number
    assert state.sheet_hash() == first and state.canonical_sheet() == text
    state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 325.0})
    state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 300.0})  # 300 in the file, back as a decimal
    assert state.sheet_hash() == first
    was = next(f for f in state.get_state()["sheet"]["shopper_facts"] if f["id"] == "toilet_rim_height")["value"]
    state.set_shopper_fact("toilet_rim_height", was + 0.5)
    assert state.sheet_hash() != first
    state.set_shopper_fact("toilet_rim_height", int(was) if float(was).is_integer() else was)
    assert state.sheet_hash() == first and state.canonical_sheet() == text
    assert state._one_form({"a": [16.0, 16.5, True, "16.0"]}) == {"a": [16, 16.5, True, "16.0"]}
    assert '16.0' not in json.dumps(json.loads(text)["lines"][4]["limits"])
