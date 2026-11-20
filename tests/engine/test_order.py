"""The limits the agent read from the therapist's written order equal the sheet the engine runs on. If the
order's text, the reading or the sheet drift apart, this fails."""
import json
import pathlib

import pytest

from signoff.engine import rules, state
from signoff.extract import order

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DERIVED = ROOT / "data" / "order" / "derived.json"


def sheet():
    return json.loads((ROOT / "sheets" / "sheet1.json").read_text())


def derived():
    if not DERIVED.exists():
        pytest.skip("the order has not been read in this checkout")
    return json.loads(DERIVED.read_text())


def test_the_reading_of_the_order_equals_the_sheet_limit_for_limit():
    made, want = derived(), {l["id"]: (line["id"], l) for line in sheet()["lines"] for l in line["limits"]}
    got = {r["limit_id"]: r for r in made["limits"]}
    assert sorted(got) == sorted(want) and len(got) == 12  # the same ids, none missing, none extra
    assert made["not_usable"] == [] and made["sheet_limits_not_in_the_order"] == []
    for limit_id, (line_id, limit) in want.items():
        r = got[limit_id]
        assert r["line_id"] == line_id and r["op"] == limit["op"] and r["unit"] == limit["unit"], limit_id
        assert r["terms"] == limit["terms"], limit_id
        if limit["bound"]["source"] == "issuer":
            assert r["value"] == limit["bound"]["value"] and r["bound"] == {"source": "issuer", "value": r["value"]}
        else:  # no number in the order: the rule is derived and the home measurement is named
            assert r["value"] is None and r["bound"] == {"source": "shopper", "fact": limit["bound"]["fact"]}
            assert r["measurement"]["source"] == "from the home"
    assert made["limits_derived"] == made["limits_equal_to_the_sheet"] == 12


def test_every_derived_limit_quotes_a_sentence_of_the_order_and_its_number_is_in_it():
    made = derived()
    text = (ROOT / made["doc"]).read_text()
    assert made["doc_sha256"] == __import__("hashlib").sha256(text.encode()).hexdigest()  # read from this very text
    for r in made["limits"]:
        assert rules.span_found(r, text) and text[r["start"]:r["end"]] == r["quote"]
        if r["value"] is not None:
            assert r["value_in_quote"] is True and str(int(r["value"])) in r["quote"]
    by_id = {r["limit_id"]: r["quote"] for r in made["limits"]}
    assert by_id["L1.tub"] == "Its overall width must fit inside the tub."
    assert by_id["L4.door"] == "Its overall width must pass the bathroom door."
    assert by_id["L6.mattress"] == "It must fit the mattress thickness."
    assert made["fulfilment"][0]["line_id"] == "L5" and made["fulfilment"][0]["matches"] is True


def test_a_sentence_repeated_under_several_items_is_found_in_its_own_item():
    text = "1. Chair. It must hold at least 300 lb.\n2. Seat. It must hold at least 300 lb.\n\nEnd."
    spans = order.item_spans(text)
    first = order.locate("It must hold at least 300 lb.", text, spans[1])
    second = order.locate("It must hold at least 300 lb.", text, spans[2])
    assert first[0] < second[0] and text[second[0]:second[1]] == "It must hold at least 300 lb."


def test_the_state_shows_the_orders_sentence_on_each_limit_and_marks_an_override(monkeypatch):
    derived()
    if not any((ROOT / "data" / "pool").glob("*.json")):
        pytest.skip("needs the real pool")
    monkeypatch.setattr(state, "_record", lambda s: None)
    state._s.update(sheet_id=None, loaded=False, sheet=None)
    try:
        s = state.reset()
        assert s["order"]["limits_in_sheet"] == s["order"]["limits_derived"] == s["order"]["limits_matching"] == 12
        assert s["order"]["reading"] == "the agent's reading of the order matches the sheet on 12 of 12 limits"
        limits = {l["id"]: l for line in s["sheet"]["lines"] for l in line["limits"]}
        assert all(l["from_order"]["matches"] and l["from_order"]["quote"] for l in limits.values())
        assert limits["L2.height"]["from_order"]["value"] == 19 and "at least 19 inches" in limits["L2.height"]["from_order"]["quote"]
        assert limits["L1.tub"]["from_order"]["value"] is None
        assert limits["L1.tub"]["from_order"]["measurement"] == {"id": "tub_inside_width", "label": "tub inside width",
                                                                "source": "from the home"}
        before = state.sheet_hash()
        assert state._s["sheet"] == sheet()  # the sheet the engine runs on carries no annotation
        s = state.apply_issuer({"type": "set_limit", "limit_id": "L2.height", "value": 19.5})
        limits = {l["id"]: l for line in s["sheet"]["lines"] for l in line["limits"]}
        assert limits["L2.height"]["from_order"]["matches"] is False and limits["L2.capacity"]["from_order"]["matches"] is True
        assert s["order"]["limits_matching"] == 11 and s["order"]["limits_matching_sheet_file"] == 12
        s = state.apply_issuer({"type": "set_limit", "limit_id": "L2.height", "value": 19.0})
        assert s["order"]["limits_matching"] == 12 and state.sheet_hash() == before  # the hash never held the annotation
    finally:
        state._s.update(sheet_id=None, loaded=False, sheet=None)
