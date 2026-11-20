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


def test_an_adjustable_range_passes_only_when_the_limit_lies_inside_it():
    sheet, pool, figures, answers, _ = inputs()
    seat = next(l for l in sheet["lines"][2]["limits"] if l["id"] == "L3.seat")
    seat["bound"]["value"] = 16.5  # N adjusts from 17 to 23: it reaches 16.5 and beyond, but cannot be set to it
    n = next(c for c in line(rules.build_state(sheet, pool, figures, answers, []), "L3")["candidates"]
             if c["product"]["product_id"] == "fx-N")
    assert n["status"] == "outside" and n["checks"][1]["margin"] == -0.5
    assert n["reason"] == "seat height: 16.5 within 17 to 23 is false"


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
    assert a["status"] == "not_stated" and "quote not found" in a["reason"] and not a["picked"]


def test_a_missing_or_unsure_figure_is_not_stated_never_a_guess():
    sheet, pool, figures, answers, strikes = inputs()
    state = rules.build_state(sheet, pool, figures, answers, strikes)
    h = next(c for c in line(state, "L2")["candidates"] if c["product"]["product_id"] == "fx-H")
    assert h["status"] == "not_stated" and h["reason"] == "weight capacity never stated on the page"
    unsure = copy.deepcopy(figures)
    f = next(f for f in unsure if f["product_id"] == "fx-A" and f["figure"] == "weight_capacity")
    f.update(unsure=True, unsure_reason="two sizes, two capacities")
    a = line(rules.build_state(sheet, pool, unsure, answers, strikes), "L2")["candidates"][0]
    assert a["status"] == "not_stated" and "two sizes" in a["reason"]


def test_a_figure_in_another_unit_is_not_compared():
    sheet, pool, figures, answers, strikes = inputs()
    other = copy.deepcopy(figures)
    next(f for f in other if f["product_id"] == "fx-A" and f["figure"] == "added_height")["unit"] = "cm"
    a = line(rules.build_state(sheet, pool, other, answers, strikes), "L2")["candidates"][0]
    assert a["status"] == "not_stated"
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
