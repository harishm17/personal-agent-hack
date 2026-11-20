"""Sheet 2, the plumber's fixture list, runs on the same engine from its own file, pool, order and readings,
and sheet 1 is untouched beside it. Uses the real pool and the cached readings."""
import json
import pathlib

import pytest

from signoff.engine import state

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def both(monkeypatch):
    if not (ROOT / "sheets" / "sheet2.json").exists() or not any((ROOT / "data" / "sheet2" / "pool").glob("*.json")) \
            or not any((ROOT / "data" / "figures" / "sheet2").glob("*.json")):
        pytest.skip("sheet 2's file, pool or readings are not in this checkout")
    monkeypatch.setattr(state, "_record", lambda s: None)
    monkeypatch.delenv("SIGNOFF_SHEET", raising=False)
    monkeypatch.delenv("SIGNOFF_POOL_DIR", raising=False)
    state._s.update(sheet_id=None, loaded=False, sheet=None)
    yield
    state._s.update(sheet_id=None, loaded=False, sheet=None)


def line(s, line_id):
    return next(l for l in s["lines"] if l["line_id"] == line_id)


def test_sheet_two_runs_from_its_own_files_and_sheet_one_is_untouched(both):
    one = state.reset()
    before = (one["sheet_hash"], one["total_cents"], [l["pick"] for l in one["lines"]])
    two = state.use_sheet("sheet2")
    assert two["sheet"]["title"] == "Bathroom remodel" and [l["line_id"] for l in two["lines"]] == ["T1", "T2", "T3", "T4"]
    assert two["counts"]["products_found"] > 100 and two["mode"] == "live" and two["degraded"] == []
    assert "planted" not in two
    # pages are products; candidates are the options on sale. The scan reads pages.
    assert two["counts"]["products_found"] <= two["counts"]["candidates"]
    assert two["instruction_scan"]["pages_in_pool"] == two["counts"]["products_found"]
    back = state.use_sheet("sheet1")
    assert (back["sheet_hash"], back["total_cents"], [l["pick"] for l in back["lines"]]) == before


def test_the_toilet_is_decided_by_an_equality_against_the_house_and_by_the_full_flush(both):
    s = state.use_sheet("sheet2")
    t1 = line(s, "T1")
    pick = next(c for c in t1["candidates"] if c["picked"])
    rough, flush = pick["checks"]
    assert rough["op"] == "==" and rough["expr"] == "10 == 10" and rough["margin"] == 0 and rough["bound"]["owner"] == "shopper"
    assert flush["op"] == "<=" and flush["pass"] and t1["tightest"]["text"] == "matches exactly"
    assert any(c["reason"] == "rough-in: 12 == 10 is false" for c in t1["candidates"])
    # a dual-flush page states two volumes. Both are tested (rule 1): if the sheet's limit says the largest
    # counts, the full flush decides; if it does not say, a page whose two volumes differ in outcome is unclear.
    flush_limit = next(l for l in s["sheet"]["lines"][0]["limits"] if l["id"] == "T1.flush")
    dual = [k for c in t1["candidates"] for k in c["checks"] if k["limit_id"] == "T1.flush"
            and any(t.get("kind") == "spread" and t["low"] <= 1.28 < t["high"] for t in k["terms"])]
    assert dual
    if flush_limit.get("several") == "largest":
        assert all(k["state"] == "fail" for k in dual)
    else:
        assert all(k["state"] == "unclear" and k["unclear_why"].startswith("page states both") for k in dual)
    # the house's measurement decides: at 12 in the picks are 12 in toilets
    moved = state.set_shopper_fact("rough_in_measured", 12.0)
    pick12 = next(c for c in line(moved, "T1")["candidates"] if c["picked"])
    assert pick12["checks"][0]["expr"] == "12 == 12" and pick12["id"] != pick["id"]


def test_the_cheapest_rule_does_not_need_a_delivery_time_and_the_order_matches(both):
    s = state.use_sheet("sheet2")
    assert s["sheet"]["pick_rule"]["id"] == "cheapest"
    for l in s["lines"]:
        inside = sorted((c for c in l["candidates"] if c["status"] == "inside"), key=lambda c: (c["product"]["price_cents"], c["id"]))
        assert l["pick"] == (inside[0]["id"] if inside else None)  # cheapest inside, whatever the store says about delivery
    assert s["order"]["limits_in_sheet"] == s["order"]["limits_derived"] == s["order"]["limits_matching"] == 5
    limits = {l["id"]: l for sl in s["sheet"]["lines"] for l in sl["limits"]}
    assert limits["T1.rough_in"]["from_order"]["op"] == "==" and limits["T1.rough_in"]["from_order"]["value"] is None
    assert limits["T1.flush"]["from_order"]["value"] == 1.28 and "1.28 gallons per flush" in limits["T1.flush"]["from_order"]["quote"]
    moved = state.apply_issuer({"type": "set_limit", "limit_id": "T3.flow", "value": 2.5})
    assert line(moved, "T3")["why"]["inside"] > line(s, "T3")["why"]["inside"] and moved["order"]["limits_matching"] == 4
