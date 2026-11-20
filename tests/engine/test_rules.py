import copy
import json
import pathlib

from signoff.engine import rules

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FX = ROOT / "fixtures"


def load(name):
    return json.loads((FX / name).read_text())


def inputs():
    sheet = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
    return sheet, load("pool.json"), load("figures.json"), load("store_answers.json"), load("strikes.json")


def test_state_equals_the_fixture_state():
    want = load("state.json")
    got = rules.build_state(*inputs())
    want.pop("version"), got.pop("version")
    assert json.loads(json.dumps(got)) == want


def line(state, line_id):
    return next(l for l in state["lines"] if l["line_id"] == line_id)


def test_raising_the_height_limit_moves_the_pick_to_another_store():
    sheet, pool, figures, answers, strikes = inputs()
    before = line(rules.build_state(sheet, pool, figures, answers, strikes), "L2")
    assert before["pick"] == "L2:fixture-store-a.example:fx-A"  # 15 + 5 (the low end of "5 to 5.5") = 20 >= 19
    height = next(l for l in sheet["lines"][1]["limits"] if l["id"] == "L2.height")
    height["bound"]["value"] = 20.5
    after = line(rules.build_state(sheet, pool, figures, answers, strikes), "L2")
    assert after["status"] == "open" and after["pick"] is None
    height["bound"]["value"] = 19.0
    capacity = next(l for l in sheet["lines"][1]["limits"] if l["id"] == "L2.capacity")
    capacity["bound"]["value"] = 425
    moved = line(rules.build_state(sheet, pool, figures, answers, strikes), "L2")
    assert moved["pick"] == "L2:fixture-store-c.example:fx-D"  # store b states no delivery time, so C is passed over
    assert moved["why"]["inside"] == 2 and moved["why"]["with_delivery_time"] == 1


def test_a_spread_uses_the_end_that_could_fail():
    fig = {"kind": "spread", "low": 5.0, "high": 5.5}
    assert rules.deciding(fig, ">=") == 5.0 and rules.deciding(fig, "<=") == 5.5


def test_at_least_passes_when_a_setting_of_an_adjustable_range_meets_it():
    """Rule 3: "must reach at least" is met by a seat that can be set to it or higher; the bound need not lie in the range."""
    sheet, pool, figures, answers, _ = inputs()
    seat = next(l for l in sheet["lines"][2]["limits"] if l["id"] == "L3.seat")
    seat["bound"]["value"] = 16.5  # N adjusts from 17 to 23: every setting is at least 16.5
    n = next(c for c in line(rules.build_state(sheet, pool, figures, answers, []), "L3")["candidates"]
             if c["product"]["product_id"] == "fx-N")
    assert n["status"] == "inside" and n["checks"][1]["expr"] == "23 >= 16.5"
    seat["bound"]["value"] = 23.0  # it can be set to 23
    n = next(c for c in line(rules.build_state(sheet, pool, figures, answers, []), "L3")["candidates"]
             if c["product"]["product_id"] == "fx-N")
    assert n["status"] == "inside" and n["checks"][1]["margin"] == 0
    seat["bound"]["value"] = 23.5  # no setting reaches it
    n = next(c for c in line(rules.build_state(sheet, pool, figures, answers, []), "L3")["candidates"]
             if c["product"]["product_id"] == "fx-N")
    assert n["status"] == "outside" and n["reason"] == "seat height: 23 >= 23.5 is false"


def test_every_stated_value_is_tested_and_values_that_differ_make_the_candidate_unclear():
    sheet, pool, figures, answers, strikes = inputs()
    height = next(l for l in sheet["lines"][1]["limits"] if l["id"] == "L2.height")
    a = lambda: line(rules.build_state(sheet, pool, figures, answers, strikes), "L2")["candidates"][0]  # noqa: E731
    assert a()["status"] == "inside"            # "adds 5 to 5.5": 20 and 20.5 both reach 19
    height["bound"]["value"] = 20.25            # 20 fails, 20.5 passes: the page does not settle it
    got = a()
    assert got["status"] == "unclear" and got["reason"] == "finished seat height: page states both 5 and 5.5 in"
    assert got["checks"][1]["state"] == "unclear" and got["checks"][1]["expr"] == "20 or 20.5 >= 20.25"
    assert [v["pass"] for v in got["checks"][1]["values"]] == [False, True] and not got["picked"]
    height["bound"]["value"] = 21.0             # both fail
    assert a()["status"] == "outside" and a()["reason"] == "finished seat height: 15 + 5.5 = 20.5 >= 21 is false"
    # the order may say which of several stated values counts ("the full flush counts")
    height["bound"]["value"] = 20.25
    height["several"] = "largest"
    assert a()["status"] == "inside" and a()["checks"][1]["expr"] == "15 + 5.5 = 20.5 >= 20.25"
    height["several"] = "smallest"
    assert a()["status"] == "outside"


def test_a_statement_that_cannot_be_compared_is_unclear_not_absent_and_a_real_failure_comes_first():
    sheet, pool, figures, answers, strikes = inputs()
    no_unit = copy.deepcopy(figures)
    next(f for f in no_unit if f["product_id"] == "fx-A" and f["figure"] == "added_height")["unit"] = None
    a = line(rules.build_state(sheet, pool, no_unit, answers, strikes), "L2")["candidates"][0]
    assert a["status"] == "unclear" and a["reason"] == "finished seat height: no unit stated"
    assert a["checks"][1]["terms"][1]["quote"]  # the statement is still shown
    # two numbers in one quote that the text does not settle: both are tested
    rivals = copy.deepcopy(figures)
    f = next(f for f in rivals if f["product_id"] == "fx-B" and f["figure"] == "added_height")
    f["possible"] = [3.0]                        # 4.5 reaches 19 with the rim's 15, 3 does not
    b = line(rules.build_state(sheet, pool, rivals, answers, strikes), "L2")["candidates"][1]
    assert b["status"] == "unclear" and "page states both 3 and 4.5 in" in b["reason"]
    # H states no capacity; if what it does state fails, it is outside, not "not stated"
    sheet["lines"][1]["limits"][1]["bound"]["value"] = 19.5   # H adds 4: 19 < 19.5
    h = next(c for c in line(rules.build_state(sheet, pool, figures, answers, strikes), "L2")["candidates"]
             if c["product"]["product_id"] == "fx-H")
    assert h["status"] == "outside" and h["reason"] == "finished seat height: 15 + 4 = 19 >= 19.5 is false"


def test_a_figure_whose_quote_is_not_in_the_text_does_not_count():
    sheet, pool, figures, answers, strikes = inputs()
    text = {(p["store"], p["product_id"]): p["text"] for p in pool}
    for f in figures:
        assert rules.span_found(f, text[(f["store"], f["product_id"])])
    bad = copy.deepcopy(figures)
    target = next(f for f in bad if f["product_id"] == "fx-A" and f["figure"] == "added_height")
    target["quote"] = "Adds 6 inches of height to the toilet seat."
    target["span_found_in_text"] = rules.span_found(target, text[(target["store"], "fx-A")])
    assert target["span_found_in_text"] is False
    a = line(rules.build_state(sheet, pool, bad, answers, strikes), "L2")["candidates"][0]
    assert a["status"] == "not_stated" and a["reason"] == "added height never stated on the page" and not a["picked"]


def test_a_figure_with_no_statement_is_not_stated_and_an_unsure_one_is_still_tested():
    sheet, pool, figures, answers, strikes = inputs()
    state = rules.build_state(sheet, pool, figures, answers, strikes)
    h = next(c for c in line(state, "L2")["candidates"] if c["product"]["product_id"] == "fx-H")
    assert h["status"] == "not_stated" and h["reason"] == "weight capacity never stated on the page"
    unsure = copy.deepcopy(figures)
    f = next(f for f in unsure if f["product_id"] == "fx-A" and f["figure"] == "weight_capacity")
    f.update(unsure=True, unsure_reason="two sizes, two capacities")  # the reader's doubt is a note, not an absence
    a = line(rules.build_state(sheet, pool, unsure, answers, strikes), "L2")["candidates"][0]
    assert a["status"] == "inside" and a["checks"][0]["expr"] == "300 >= 300"


def test_a_figure_in_another_unit_is_not_compared():
    sheet, pool, figures, answers, strikes = inputs()
    other = copy.deepcopy(figures)
    next(f for f in other if f["product_id"] == "fx-A" and f["figure"] == "added_height")["unit"] = "cm"
    a = line(rules.build_state(sheet, pool, other, answers, strikes), "L2")["candidates"][0]
    assert a["status"] == "unclear" and a["reason"] == "finished seat height: stated in cm, not in"
    assert rules.convert(12.7, "cm", "in") == 5.0 and rules.convert(300, "lbs.", "lb") == 300


def test_a_strike_is_by_product_key_and_holds_at_every_store():
    sheet, pool, figures, answers, _ = inputs()
    pool = copy.deepcopy(pool)
    twin = copy.deepcopy(next(p for p in pool if p["product_id"] == "fx-D"))
    twin.update(store="fixture-store-a.example", product_id="fx-D2", variant_id="fx-D2-v1", price_cents=100)
    pool.append(twin)
    strikes = [{"line_id": "L2", "product_key": "fixture d", "by": "issuer", "reason": "test", "at": "now"}]
    l2 = line(rules.build_state(sheet, pool, figures, answers, strikes), "L2")
    struck = [c for c in l2["candidates"] if c["status"] == "struck"]
    assert {c["product"]["store"] for c in struck} == {"fixture-store-a.example", "fixture-store-c.example"}
    assert l2["status"] == "next_candidate" and not any(c["picked"] for c in struck)


def test_a_pick_up_line_skips_the_delivery_condition():
    state = rules.build_state(*inputs())
    l5 = line(state, "L5")  # its only candidate is at the store that states no delivery time
    assert l5["status"] == "pick_up" and l5["pick"] == "L5:fixture-store-b.example:fx-Q"
    assert state["total_cents"] == sum(c["product"]["price_cents"] for l in state["lines"] for c in l["candidates"]
                                       if c["picked"] and l["status"] != "pick_up")


def test_the_sentence_around_a_span_holds_the_quote_at_the_stated_place():
    text = "Shower Chair.\nA wide seat supports up to 300 lbs, giving you room. Seat height 16\" to 21\"."
    start = text.index("300 lbs")
    sentence, a, b = rules.sentence_around(text, start, start + 7)
    assert sentence == "A wide seat supports up to 300 lbs, giving you room." and sentence[a:b] == "300 lbs"
    long = "word " * 200 + "holds 300 lbs " + "word " * 200
    start = long.index("300 lbs")
    sentence, a, b = rules.sentence_around(long, start, start + 7)
    assert len(sentence) < 300 and sentence[a:b] == "300 lbs" and sentence.startswith("… ") and sentence.endswith(" …")


def sheet_with(op, bound, kind="single", low=10.0, high=10.0, value=10.0, rule="cheapest_with_delivery_time"):
    sheet = {"issuer": {"name": "Marco"}, "shopper": {"name": "Priya"}, "need_by": "2026-12-04",
             "pick_rule": {"id": rule, "label": rule},
             "shopper_facts": [{"id": "measured", "short": "drain from wall", "label": "x", "value": bound, "unit": "in"}],
             "lines": [{"id": "T1", "need": "toilet", "room": "bathroom", "fulfilment": "cart", "limits": [
                 {"id": "T1.rough_in", "name": "rough-in", "terms": [{"source": "store", "figure": "rough_in"}], "op": op,
                  "bound": {"source": "shopper", "fact": "measured"}, "unit": "in"}]}]}
    pool = [{"store": "s", "product_id": "p", "variant_id": "v", "title": "t", "price_cents": 100, "url": "u",
             "fetched_at": "now", "product_key": "k", "line_ids": ["T1"]}]
    figures = [{"store": "s", "product_id": "p", "figure": "rough_in", "kind": kind, "value": value if kind == "single" else None,
                "low": low, "high": high, "unit": "in", "quote": "q", "start": 0, "end": 1, "span_found_in_text": True}]
    return sheet, pool, figures


def only_check(sheet, pool, figures, answers=()):
    state = rules.build_state(sheet, pool, figures, list(answers), [])
    return state["lines"][0], state["lines"][0]["candidates"][0]["checks"][0]


def test_equality_is_a_real_comparison_with_a_margin_of_zero_when_it_matches():
    line, check = only_check(*sheet_with("==", 10.0))
    assert (check["expr"], check["pass"], check["margin"], check["state"]) == ("10 == 10", True, 0.0, "pass")
    line, check = only_check(*sheet_with("==", 10.0, value=12.0))
    assert (check["expr"], check["pass"], check["margin"]) == ("12 == 10", False, -2.0)
    assert line["candidates"][0]["status"] == "outside" and line["candidates"][0]["reason"] == "rough-in: 12 == 10 is false"
    # a page that states both 10 and 12 does not settle an equality: unclear
    _, check = only_check(*sheet_with("==", 10.0, kind="spread", low=10.0, high=12.0))
    assert check["state"] == "unclear" and check["unclear_why"] == "page states both 10 and 12 in"
    # an adjustable range that takes in the value is set to it
    _, check = only_check(*sheet_with("==", 10.0, kind="adjustable", low=10.0, high=12.0))
    assert check["expr"] == "10 == 10" and check["pass"] is True


def test_an_unknown_comparison_or_pick_rule_is_an_error_not_a_silent_other_one():
    import pytest
    sheet, pool, figures = sheet_with("=", 10.0)
    with pytest.raises(ValueError, match="comparison"):
        rules.build_state(sheet, pool, figures, [], [])
    with pytest.raises(ValueError, match="comparison"):
        rules.validate_sheet(sheet)
    sheet, pool, figures = sheet_with("==", 10.0, rule="best value")
    with pytest.raises(ValueError, match="pick rule"):
        rules.validate_sheet(sheet)
    rules.validate_sheet(json.loads((ROOT / "sheets" / "sheet1.json").read_text()))


def test_the_pick_rule_cheapest_does_not_need_a_delivery_time_and_sheet_ones_rule_still_does():
    line, _ = only_check(*sheet_with("==", 10.0, rule="cheapest"))
    assert line["status"] == "ready" and line["pick"] and line["tightest"]["text"] == "matches exactly"
    assert line["why"]["with_delivery_time"] == 0 and line["candidates"][0]["arrival"]["status"] == "not stated"
    line, _ = only_check(*sheet_with("==", 10.0))  # the rule that needs a stated time: the same product is not picked
    assert line["status"] == "open" and line["reason"] == "nothing inside the limits states a delivery time"


def test_gallons_per_flush_and_per_minute_are_units_and_litres_convert():
    assert rules.unit_name("GPF") == "gpf" and rules.unit_name("gallons per minute") == "gpm"
    assert rules.convert(4.8, "Lpf", "gpf") == 1.27 and rules.convert(1.28, "gpf", "gpf") == 1.28
    assert rules.convert(1.2, "gpm", "gpf") is None  # a flow is not a flush volume


def test_a_lines_quantity_multiplies_its_pick_in_the_total_and_a_bad_one_is_an_error():
    import pytest
    sheet, pool, figures, answers, strikes = inputs()
    one = rules.build_state(sheet, pool, figures, answers, strikes)["total_cents"]
    sheet["lines"][1]["quantity"] = 24  # L2's pick, fx-A at 2752, twenty-four times
    assert rules.build_state(sheet, pool, figures, answers, strikes)["total_cents"] == one + 23 * 2752
    sheet["lines"][1]["quantity"] = 0
    with pytest.raises(ValueError, match="quantity"):
        rules.validate_sheet(sheet)


def test_a_count_needs_no_unit_when_the_sheet_says_so_and_a_measure_still_does():
    sheet, pool, figures = sheet_with(">=", 10.0)
    figures[0]["unit"] = None
    line, check = only_check(sheet, pool, figures)
    assert check["state"] == "unclear" and check["unclear_why"] == "no unit stated"
    sheet["lines"][0]["limits"][0]["unit_required"] = False  # the limit counts things: a bare number is the count
    line, check = only_check(sheet, pool, figures)
    assert check["state"] == "pass" and check["expr"] == "10 >= 10"
