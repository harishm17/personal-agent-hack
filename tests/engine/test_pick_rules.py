"""The shopper chooses the ordering among the products that pass (E30), and an order's rule may be a preference
instead of a requirement (E31). Fixture pool; the ratings here are invented for the test and never reach a sheet."""
import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from signoff.app import app
from signoff.engine import receipts, rules, state

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FX = ROOT / "fixtures"
A, B, C, D, E, F = ("L2:fixture-store-a.example:fx-A", "L2:fixture-store-b.example:fx-B", "L2:fixture-store-b.example:fx-C",
                    "L2:fixture-store-c.example:fx-D", "L2:fixture-store-c.example:fx-E", "L2:fixture-store-a.example:fx-F")
# L2: A $27.52, B $58.00, C $64.99, D $79.99 and E $89.99 pass; F is outside its limit
RATINGS = {B: {"rating": 4.6, "out_of": 5, "review_count": 40}, D: {"rating": 4.8, "out_of": 5, "review_count": 212},
           E: {"rating": 4.8, "out_of": 5, "review_count": 90}, F: {"rating": 5.0, "out_of": 5, "review_count": 900}}
WISH = {"id": "L2.capacity_wished", "name": "holds 450 lb if they have one", "op": ">=", "unit": "lb",
        "bound": {"source": "issuer", "value": 450}, "terms": [{"source": "store", "figure": "weight_capacity"}]}


def load(name):
    return json.loads((FX / name).read_text())


def built(rule, ratings=None, within=None, preferences=None):
    sheet = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
    sheet["pick_rule"] = {"id": rule, "label": "the sheet's words for " + rule, "set_by": "the test"}
    if within is not None:
        sheet["pick_rule"]["within"] = within
    if preferences:
        next(l for l in sheet["lines"] if l["id"] == "L2")["preferences"] = preferences
    return rules.build_state(sheet, load("pool.json"), load("figures.json"), load("store_answers.json"), [], ratings=ratings or {})


def line(s, line_id="L2"):
    return next(l for l in s["lines"] if l["line_id"] == line_id)


def picked(s, line_id="L2"):
    return next(c for c in line(s, line_id)["candidates"] if c["picked"])


def test_best_reviewed_is_one_sort_key_rated_first_then_review_count_then_price():
    s = built("best_reviewed", RATINGS)
    pick = picked(s)
    assert pick["id"] == D and pick["picked_because"] == "rated 4.8 from 212 reviews, the highest that passes"
    why = line(s)["why"]
    assert why["rated"] == 3 and why["rule"] == "best reviewed: 3 of 5 that pass have a quoted rating"
    assert pick["rating"] == {"rating": 4.8, "out_of": 5, "review_count": 212}
    assert "rating" not in next(c for c in line(s)["candidates"] if c["id"] == A)
    # the whole order, from the same key: equal ratings by review count, unrated ones after, by price
    order, _, _ = rules.pick_order("best_reviewed", 0.3, [c for c in line(s)["candidates"] if c["status"] == "inside"], RATINGS, {})
    assert [c["id"] for c in sorted((c for c in line(s)["candidates"] if c["status"] == "inside"), key=order)] == [D, E, B, A, C]


def test_a_rating_never_lifts_a_product_past_a_limit():
    s = built("best_reviewed", RATINGS)
    f = next(c for c in line(s)["candidates"] if c["id"] == F)
    assert f["status"] == "outside" and not f["picked"] and f["rating"]["rating"] == 5.0   # rated 5.0 and still outside
    assert line(s)["why"]["inside"] == line(built("cheapest"))["why"]["inside"] == 5


def test_best_value_is_the_cheapest_within_the_stated_distance_of_the_best_rated():
    s = built("best_value", RATINGS)
    assert picked(s)["id"] == B                                             # 4.6 is within 0.3 of 4.8, and B is cheaper
    assert picked(s)["picked_because"] == "cheapest within 0.3 stars of the best rated (4.6 against 4.8)"
    assert line(s)["why"]["rule"] == "best value (cheapest within 0.3 stars of the best rated): 3 of 5 that pass have a quoted rating"
    s = built("best_value", RATINGS, within=0.1)                            # the distance is the sheet's, not the code's
    assert picked(s)["id"] == D
    assert picked(s)["picked_because"] == "rated 4.8 from 212 reviews, the best rated that passes and the cheapest within 0.1 stars of it"
    with pytest.raises(ValueError):
        built("best_value", RATINGS, within="close")


def test_most_popular_is_the_most_reviews_counted_then_the_rating_then_the_price():
    counts = dict(RATINGS, A={"rating": 4.4, "out_of": None, "review_count": 212})   # a count quoted with no scale still counts
    counts[A] = counts.pop("A")
    s = built("most_popular", counts)
    inside = [c for c in line(s)["candidates"] if c["status"] == "inside"]
    order, _, _ = rules.pick_order("most_popular", 0.3, inside, counts, {})
    assert [c["id"] for c in sorted(inside, key=order)] == [D, A, E, B, C]   # 212 rated 4.8, 212 unrated, 90, 40, no count
    assert picked(s)["id"] == D and picked(s)["picked_because"] == "212 reviews (rated 4.8), the most that passes"
    assert line(s)["why"]["rated"] == 4 and line(s)["why"]["rule"] == "most reviewed: 4 of 5 that pass have a quoted review count"
    a = next(c for c in inside if c["id"] == A)
    assert a["review_count"] == 212 and "rating" not in a                    # its rating has no scale, so only the count is shown
    assert not next(c for c in line(s)["candidates"] if c["id"] == F)["picked"]   # 900 reviews and outside the limit
    s = built("most_popular", {})
    assert picked(s)["id"] == A and line(s)["why"]["rated"] == 0
    assert picked(s)["picked_because"] == "cheapest that passes; none of them has a quoted review count"
    assert line(s)["why"]["rule"] == "most reviewed: none of the 5 that pass has a quoted review count, so the cheapest is shown"
    s = built("most_popular", {B: {"rating": None, "out_of": None, "review_count": 1}})
    assert picked(s)["id"] == B and picked(s)["picked_because"] == "1 review, the most that passes"


def test_with_no_quoted_rating_every_product_is_unrated_and_the_line_says_so():
    for rule in ("best_reviewed", "best_value"):
        s = built(rule, {})
        assert picked(s)["id"] == A and line(s)["why"]["rated"] == 0
        assert "none of the 5 that pass has a quoted rating" in line(s)["why"]["rule"]
        assert picked(s)["picked_because"] == "cheapest that passes; none of them has a quoted rating"
        assert all("rating" not in c for l in s["lines"] for c in l["candidates"])


def test_a_rating_is_used_only_as_quoted_with_its_scale():
    no_scale = {A: {"rating": 4.9, "out_of": None, "review_count": 50}, B: {"rating": 4.6, "out_of": 5, "review_count": 40}}
    s = built("best_reviewed", no_scale)
    assert picked(s)["id"] == B and line(s)["why"]["rated"] == 1            # 4.9 of an unstated scale is not compared
    of_ten = {A: {"rating": 9.0, "out_of": 10, "review_count": 12}, B: {"rating": 4.6, "out_of": 5, "review_count": 40}}
    s = built("best_reviewed", of_ten)
    assert picked(s)["id"] == B                                             # 9.0 of 10 is 4.5 of 5
    assert rules.rating_words(of_ten[A]) == "rated 9 out of 10 from 12 reviews"
    assert rules.stars({"rating": 6, "out_of": 5}) is None and rules.stars({"rating": True, "out_of": 5}) is None


def test_the_cheapest_rules_do_not_look_at_ratings_and_an_unknown_rule_is_an_error():
    assert picked(built("cheapest", RATINGS))["id"] == A
    assert picked(built("cheapest", RATINGS))["picked_because"] == "cheapest that passes"
    s = built("cheapest_with_delivery_time", RATINGS)
    assert picked(s)["id"] == A and picked(s)["picked_because"] == "cheapest that passes and states a delivery time"
    assert "rated" not in line(s)["why"] and line(s)["why"]["rule"] == "the sheet's words for cheapest_with_delivery_time"
    with pytest.raises(ValueError):
        built("nicest")
    with pytest.raises(ValueError):
        rules.validate_sheet({"lines": [], "pick_rule": {"id": "nicest"}})
    assert {r["id"] for r in rules.pick_rules()} == set(rules.PICK_RULES)


def test_a_preference_orders_those_that_pass_and_changes_no_status_and_no_count():
    plain, wished = built("cheapest"), built("cheapest", preferences=[WISH])
    assert picked(plain)["id"] == A and picked(wished)["id"] == C           # C and D hold 450; C is the cheaper
    assert picked(wished)["picked_because"] == "cheapest that passes, among those that meet the preference"
    assert line(wished)["why"]["preferences"] == "2 of 5 that pass meet the preference"
    assert wished["counts"] == plain["counts"]
    assert [(c["id"], c["status"], c["reason"]) for c in line(wished)["candidates"]] == \
        [(c["id"], c["status"], c["reason"]) for c in line(plain)["candidates"]]
    by = {c["product"]["product_id"]: c["preferences"][0] for c in line(wished)["candidates"]}
    assert by["fx-A"] == {"id": "L2.capacity_wished", "label": "holds 450 lb if they have one", "status": "not_met",
                          "value": 300.0, "expr": "300 >= 450", "quote": by["fx-A"]["quote"]} and by["fx-A"]["quote"]
    assert by["fx-D"]["status"] == "met" and by["fx-D"]["expr"] == "450 >= 450"
    assert by["fx-H"]["status"] == "not_stated" and by["fx-H"]["value"] is None   # the page never states a capacity
    assert all("preferences" not in c for c in line(wished, "L1")["candidates"])  # only the line that carries one
    # the preference comes first, then the pick rule's own key
    s = built("cheapest_with_delivery_time", preferences=[WISH])
    assert picked(s)["id"] == D                                             # C states no delivery time
    s = built("best_reviewed", RATINGS, preferences=[WISH])
    assert picked(s)["id"] == D and line(s)["why"]["rated"] == 3
    # a preference nothing meets changes nothing
    nobody = dict(WISH, bound={"source": "issuer", "value": 900})
    s = built("cheapest", preferences=[nobody])
    assert picked(s)["id"] == A and line(s)["why"]["preferences"] == "0 of 5 that pass meet the preference"
    assert picked(s)["picked_because"] == "cheapest that passes"
    with pytest.raises(ValueError):
        rules.validate_sheet(dict(json.loads((ROOT / "sheets" / "sheet1.json").read_text()),
                                  lines=[{"id": "X", "limits": [], "preferences": [dict(WISH, op="about")]}]))


# --- through the state: the route, the hash, the receipts ---

@pytest.fixture
def live(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "DATA", tmp_path)
    monkeypatch.setattr(state, "_load_pool", lambda: (load("pool.json"), load("store_answers.json")))
    monkeypatch.setattr(state, "_record", lambda s: None)
    monkeypatch.setattr(state, "_ratings_fn", lambda: lambda line_id: {k: v for k, v in RATINGS.items() if k.startswith(line_id + ":")})
    state.reset()
    yield
    state._s["loaded"] = False


def test_the_shopper_sets_the_ordering_and_the_approver_signs_it(live):
    s = state.get_state()
    v, before = s["version"], state.sheet_hash()
    assert [r["id"] for r in s["pick_rules"]] == ["cheapest", "best_reviewed", "best_value", "most_popular",
                                                  "cheapest_with_delivery_time"]
    assert picked(s)["id"] == A and "rating" not in picked(s)
    assert next(c for c in line(s)["candidates"] if c["id"] == D)["rating"]["review_count"] == 212   # shown under every rule
    client = TestClient(app)
    r = client.post("/api/shopper/pick_rule", json={"id": "best_reviewed"}).json()
    s = state.get_state()
    assert r["ok"] and r["version"] == s["version"] > v and r["pick_rule"]["id"] == "best_reviewed"
    assert r["pick_rule"]["set_by"] == s["sheet"]["shopper"]["name"] and r["total_cents"] == s["total_cents"]
    assert picked(s)["id"] == D and line(s)["picked_by"] == "rule"
    assert line(s)["why"]["rule"] == "best reviewed: 3 of 5 that pass have a quoted rating"
    reviewed = state.sheet_hash()
    assert reviewed != before and '"pick_rule":{"id":"best_reviewed"' in state.canonical_sheet()
    assert '"rating":{"out_of":5,"rating":4.8,"review_count":212}' in state.canonical_sheet()
    state.set_pick_rule("most_popular")
    assert picked(state.get_state())["id"] == D and '"review_count":212' in state.canonical_sheet()
    assert '"pick_rule":{"id":"most_popular"' in state.canonical_sheet() and state.sheet_hash() not in (before, reviewed)
    # best value: the distance is under the hash
    state.set_pick_rule("best_value")
    assert picked(state.get_state())["id"] == B and '"within":0.3' in state.canonical_sheet()
    value = state.sheet_hash()
    state._s["sheet"]["pick_rule"]["within"] = 0.1
    state._recompute(why="test")
    assert state.sheet_hash() != value and '"within":0.1' in state.canonical_sheet()
    assert "0.1 stars" in next(x["label"] for x in state.get_state()["pick_rules"] if x["id"] == "best_value")
    # her own choice of one product still stands over any ordering, and says so
    s = state.set_shopper_choice("L2", E)
    assert picked(s)["id"] == E and picked(s)["picked_because"] == "chosen by %s" % s["sheet"]["shopper"]["name"]
    assert sum(1 for c in line(s)["candidates"] if "picked_because" in c) == 1
    state.set_shopper_choice("L2", None)
    # an unknown id is an error; the sheet's own rule comes back in the sheet's own words
    assert client.post("/api/shopper/pick_rule", json={"id": "nicest"}).status_code == 400
    back = state.set_pick_rule("cheapest_with_delivery_time")
    assert back["sheet"]["pick_rule"] == json.loads((ROOT / "sheets" / "sheet1.json").read_text())["pick_rule"]
    assert state.sheet_hash() == before
    assert [x["type"] for x in receipts.chain()["receipts"]].count("shopper_pick_rule") == 4
    # refused once signed; a reset returns to the sheet's rule
    state.set_pick_rule("best_reviewed")
    state.mark_signed({"name": "Dana", "at": "2026-11-20T14:00:00-08:00", "sheet_hash": state.sheet_hash()}, [])
    assert client.post("/api/shopper/pick_rule", json={"id": "cheapest"}).status_code == 409
    assert state.reset()["sheet"]["pick_rule"]["id"] == "cheapest_with_delivery_time"


def test_no_reviews_module_or_a_failing_one_means_unrated_and_the_state_says_so(live, monkeypatch):
    monkeypatch.setattr(state, "_ratings_fn", lambda: None)
    s = state.set_pick_rule("best_reviewed")
    assert picked(s)["id"] == A and line(s)["why"]["rated"] == 0 and not [d for d in s["degraded"] if d["what"] == "ratings"]

    def broken(line_id):
        raise OSError("no cache")
    monkeypatch.setattr(state, "_ratings_fn", lambda: broken)
    s = state.set_pick_rule("best_value")
    assert picked(s)["id"] == A and line(s)["why"]["rated"] == 0
    assert [d["what"] for d in s["degraded"]] == ["ratings"]


def test_the_reviews_module_sees_this_versions_candidates_while_it_answers(live, monkeypatch):
    seen = []

    def ratings(line_id):
        now = state.get_state()   # what signoff.reviews does: it reads the candidates from the engine
        seen.append({c["id"]: c["status"] for l in now["lines"] if l["line_id"] == line_id for c in l["candidates"]})
        return {}
    monkeypatch.setattr(state, "_ratings_fn", lambda: ratings)
    state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 475})   # only C holds 475
    l2 = [x for x in seen if A in x][-1]
    assert l2[A] == "outside" and l2[C] == "inside"


def test_a_preference_is_signed_with_its_bound(live):
    before = state.sheet_hash()
    next(l for l in state._s["sheet"]["lines"] if l["id"] == "L2")["preferences"] = [WISH]
    s = state._recompute(why="test")
    assert picked(s)["id"] == D                                             # sheet 1 wants a delivery time; C states none
    sheet = json.loads(state.canonical_sheet())
    l2 = next(l for l in sheet["lines"] if l["line_id"] == "L2")
    assert l2["preferences"] == [{"id": "L2.capacity_wished", "name": "holds 450 lb if they have one", "op": ">=",
                                  "unit": "lb", "set_by": "issuer", "bound": 450,
                                  "terms": ["weight_capacity"]}]
    assert l2["pick"]["preferences"] == [{"id": "L2.capacity_wished", "status": "met", "expr": "450 >= 450"}]
    assert "preferences" not in next(l for l in sheet["lines"] if l["line_id"] == "L1") and state.sheet_hash() != before
    # the phone's adjustable limits and the limit ids know nothing of a preference
    with pytest.raises(state.EngineError):
        state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity_wished", "value": 300})
    assert s["counts"]["inside_limits"] == state.reset()["counts"]["inside_limits"]
