"""The passing-box SQL must return the same candidates as the engine's `inside` set (fixtures/make_state.py is the
reference of the rules). Uses a throwaway database signoff_test_<random> on the real SingleStore; skipped if it is unreachable."""
import copy
import importlib.util
import itertools
import json
import os
import uuid
import pathlib
import random

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

spec = importlib.util.spec_from_file_location("make_state", ROOT / "fixtures" / "make_state.py")
make_state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_state)

from signoff.db import conn, passing, records, schema  # noqa: E402
from signoff.store import pool as pool_mod  # noqa: E402


@pytest.fixture(scope="module")
def db():
    """A throwaway database per run (name carries a random suffix), so the app's tables and a parallel run are never touched."""
    name = "signoff_test_" + uuid.uuid4().hex[:8]
    prev = conn.DB
    try:
        c = conn.connect(database=None)
        c.cursor().execute("CREATE DATABASE " + name)
        c.close()
    except Exception as e:  # noqa: BLE001
        pytest.skip("SingleStore unreachable: " + type(e).__name__)
    conn.DB = name
    try:
        schema.ensure()
        yield name
    finally:
        conn.DB = prev
        schema._done.discard(name)
        try:
            c = conn.connect(database=None)
            c.cursor().execute("DROP DATABASE IF EXISTS " + name)
            c.close()
        except Exception:  # noqa: BLE001
            pass


def _state(sheet, pool, figures, answers, strikes):
    """The engine's own rules (not the fixture script), so `unsure` and duplicate figures are judged as the app judges them."""
    from signoff.engine import rules
    return rules.build_state(sheet, pool, figures, answers, strikes)


def _roughen(figures, rnd):
    """Make the figures harder: a second statement with another number for some (the page states two: unclear or fails or
    passes depending on both), a unit the limit is not in for a few (not comparable), a few marked unsure (no longer absent)."""
    out = []
    for f in figures:
        f = dict(f)
        roll = rnd.random()
        if roll < 0.15:
            f["unsure"] = True
            f["unsure_reason"] = "test: two different numbers on the page"
        if 0.15 <= roll < 0.22:
            f["disagree"] = "readers disagree: %g and %g" % (f.get("low") or 0, (f.get("high") or 0) * 0.8)  # the second reader read another number
        if roll > 0.93:
            f["unit"] = "cm"
        out.append(f)
        if roll < 0.12 and f.get("kind") == "single" and isinstance(f.get("value"), (int, float)):
            other = dict(f, value=f["value"] * 1.5, low=f["value"] * 1.5, high=f["value"] * 1.5)
            out.append(other)
    return out


@pytest.mark.live  # talks to SingleStore, about 90 s: run with `uv run pytest -m live`, not in the gate
def test_sql_agrees_with_engine_on_fixtures_and_random_limits(db):
    sheet = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
    pool, figures = make_state.build_inputs()
    rnd = random.Random(7)
    checked = 0
    for trial in range(3):
        sh = copy.deepcopy(sheet)
        strikes = make_state.STRIKES if trial % 2 == 0 else []
        if trial:
            for line in sh["lines"]:
                for lim in line["limits"]:
                    b = lim["bound"]
                    if b["source"] == "issuer":
                        b["value"] = rnd.choice([x * b["step"] + b["min"] for x in range(int((b["max"] - b["min"]) / b["step"]) + 1)])
            for f in sh["shopper_facts"]:
                f["value"] = rnd.choice([f["min"] + i * f["step"] for i in range(int((f["max"] - f["min"]) / f["step"]) + 1)])
        state = _state(sh, pool, _roughen(figures, rnd) if trial else figures, make_state.ANSWERS, strikes)
        state["version"] = trial + 1
        records.write_sync(state)
        for line in state["lines"]:
            want = sorted(c["id"] for c in line["candidates"] if c["status"] == "inside")
            got = passing.passing_box(line["line_id"])
            assert sorted(r["cand_id"] for r in got["rows"]) == want, (trial, line["line_id"])
            assert "SELECT" in got["sql"] and "'" + line["line_id"] + "'" in got["sql"]
            checked += len(want)
    assert checked > 5


@pytest.mark.live
def test_sql_handles_equals_and_units_on_sheet2(db, monkeypatch):
    """T1.rough_in `==` the measured 10 in, flush `<=` 1.28 gpf (a dual flush is a spread: the full flush decides), faucet gpm,
    and a figure in another unit never counts. Reference: the rules written out here (the engine's `==` is ENGINE's)."""
    sheet = json.loads((ROOT / "sheets" / "sheet2.json").read_text())
    pool = [{"store": "s.com", "product_id": "p%d" % i, "variant_id": "v%d" % i, "title": "t%d" % i, "price_cents": 100 + i,
             "url": "u", "text": "x", "fetched_at": "t", "product_key": "k%d" % i, "line_ids": ["T1"]} for i in range(6)]
    # (rough-in kind, low, high, rough unit, flush kind, low, high)
    spec = [("single", 10, 10, "in", "single", 1.28, 1.28), ("single", 12, 12, "in", "single", 1.0, 1.0),
            ("spread", 10, 12, "in", "spread", 1.1, 1.6), ("single", 10, 10, "cm", "single", 1.0, 1.0),
            ("single", 10, 10, "in", "spread", 1.1, 1.28), ("single", 10, 10, "in", "single", 1.6, 1.6)]
    figures = []
    for p, (k1, lo1, hi1, u1, k2, lo2, hi2) in zip(pool, spec):
        for name, kind, lo, hi, unit in (("rough_in", k1, lo1, hi1, u1), ("flush_volume", k2, lo2, hi2, "gpf")):
            figures.append({"store": p["store"], "product_id": p["product_id"], "figure": name, "kind": kind,
                            "value": lo if kind == "single" else None, "low": lo, "high": hi, "unit": unit, "quote": "q",
                            "start": 0, "end": 1, "extractor": "t", "span_found_in_text": True})
    monkeypatch.setattr(pool_mod, "load", lambda: (pool, []))
    lines = [l for l in sheet["lines"] if l["id"] == "T1"]
    state = {"version": 1, "sheet": {**sheet, "lines": lines},
             "lines": [{"line_id": "T1", "struck": [], "candidates": [
                 {"id": "T1:s.com:" + p["product_id"], "product": p, "figures": [f for f in figures if f["product_id"] == p["product_id"]],
                  "status": "x", "picked": False} for p in pool]}]}
    records.write_sync(state)
    got = sorted(r["product_id"] for r in passing.passing_box("T1")["rows"])
    # p0: 10 == 10 and 1.28 <= 1.28; p1: 12 != 10; p2: spread 10..12 holds 10 but full flush 1.6 > 1.28; p3: cm is not in;
    # p4: 10 == 10 and the full flush 1.28 <= 1.28; p5: 1.6 > 1.28
    assert got == ["p0", "p4"]


def test_the_same_statement_runs_on_the_airbyte_table_and_the_source_is_checked():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from signoff.store import api
    assert "FROM {pool_table} c" in passing.PASSING_BOX_SQL and passing.AIRBYTE == "signoff.airbyte_pool"
    assert "airbyte_pool" in passing._sql(True) and "airbyte_pool" not in passing._sql(False)
    app = FastAPI()
    app.include_router(api.router)
    assert TestClient(app).get("/api/sql/passing-box?line_id=L1&source=nonsense").status_code == 422


def test_the_sheets_own_unit_words_are_one_unit_in_the_tables():
    from signoff.db import records
    state = {"sheet": {"units": {"count": ["ct", "pack", "crayons"], "dB": ["db", "decibel"]}}}
    records._learn_units(state)
    assert records._unit("ct") == "count" and records._unit("Crayons") == "count" and records._unit("count") == "count"
    assert records._unit("decibels") != "dB" and records._unit("DB") == "dB"
    assert records._unit("inches") == "in"
    records._learn_units({"sheet": {}})


@pytest.mark.live
def test_sql_tests_every_stated_value_and_every_option_on_sheet3(db):
    """A page that states two levels, an option that differs from its sibling, `several` largest, and a figure with no number in it."""
    import copy
    sheet = copy.deepcopy(json.loads((ROOT / "sheets" / "sheet3.json").read_text()))
    line = next(l for l in sheet["lines"] if l["id"] == "C1")
    lim = line["limits"][0]  # volume <= 85 dB
    def fig(cand, kind, value=None, low=None, high=None, unit="dB", **extra):
        return {"store": "s.com", "product_id": cand["product_id"], "figure": "max_volume", "kind": kind, "value": value,
                "low": low if low is not None else value, "high": high if high is not None else value, "unit": unit, "quote": "q",
                "start": 0, "end": 1, "extractor": "t", "span_found_in_text": True, **extra}
    def cand(pid, variant, price, figs):
        product = {"store": "s.com", "product_id": pid, "variant_id": variant, "title": "t", "price_cents": price, "product_key": "k" + pid + (variant or ""), "url": "u"}
        return {"id": "C1:s.com:%s%s" % (pid, ":" + variant if variant else ""), "product": product, "figures": figs, "status": "x", "picked": False}
    cases = [  # (id, variant, figures, inside when several is unset)
        ("a", None, [fig({"product_id": "a"}, "single", 80)], True),
        ("b", None, [fig({"product_id": "b"}, "single", 80), fig({"product_id": "b"}, "single", 95)], False),   # states both: unclear
        ("c", None, [fig({"product_id": "c"}, "single", 70), fig({"product_id": "c"}, "single", 85)], True),    # both pass
        ("d", "v1", [fig({"product_id": "d"}, "single", 85)], True),                                          # option one passes
        ("d", "v2", [fig({"product_id": "d"}, "single", 94)], False),                                         # its sibling does not
        ("e", None, [fig({"product_id": "e"}, "single", 60, unit="cm")], False),                              # not in dB: not comparable
        ("f", None, [fig({"product_id": "f"}, "spread", low=75, high=94)], False),                            # a spread tests both ends
        ("g", None, [], False),                                                                               # never stated
        ("h", None, [fig({"product_id": "h"}, "single", 50, number_in_quote=False)], False),                  # no number in its quote
        ("i", None, [fig({"product_id": "i"}, "single", 80, disagree="readers disagree: 80 and 95 dB")], False),  # the two readers disagree: unclear
    ]
    for several, expect in ((None, [c[0] + (":" + c[1] if c[1] else "") for c in cases if c[3]]),
                            ("smallest", None), ("largest", None)):
        lim2 = {**{k: v for k, v in lim.items() if k != "several"}, **({"several": several} if several else {})}
        sh = {**sheet, "lines": [{**line, "limits": [lim2]}]}
        state = {"version": 1, "sheet": sh, "lines": [{"line_id": "C1", "struck": [], "candidates": [cand(p, v, 100 + i, f) for i, (p, v, f, _) in enumerate(cases)]}]}
        records.write_sync(state)
        got = sorted(r["cand_id"].split("s.com:")[1] for r in passing.passing_box("C1")["rows"])
        if expect is not None:
            assert got == sorted(expect), (several, got)
        elif several == "smallest":  # only the smallest stated value is tested: b (80), c (70), f (75) now pass
            assert got == sorted(["a", "b", "c", "d:v1", "f"]), got  # i is blocked in every mode: the readers disagree
        else:  # largest: 80 passes (a), b 95 fails, c 85 passes, d:v2 94 fails, f 94 fails
            assert got == sorted(["a", "c", "d:v1"]), got


@pytest.mark.live
def test_a_count_limit_takes_a_bare_number_but_a_measure_does_not(db):
    """`unit_required: false` (a count of crayons or sheets) accepts a figure with no unit; any other limit does not."""
    import copy
    sheet = copy.deepcopy(json.loads((ROOT / "sheets" / "sheet3.json").read_text()))
    c2 = next(l for l in sheet["lines"] if l["id"] == "C2")
    assert c2["limits"][0].get("unit_required") is False
    def cand(pid, unit):
        f = {"store": "s.com", "product_id": pid, "figure": "crayon_count", "kind": "single", "value": 24, "low": 24, "high": 24, "unit": unit,
             "quote": "q", "start": 0, "end": 1, "extractor": "t", "span_found_in_text": True}
        p = {"store": "s.com", "product_id": pid, "variant_id": None, "title": "t", "price_cents": 100, "product_key": "k" + pid, "url": "u"}
        return {"id": "C2:s.com:" + pid, "product": p, "figures": [f], "status": "x", "picked": False}
    for required, expect in ((False, ["bare", "ct"]), (True, ["ct"])):
        lim = {**c2["limits"][0], "unit_required": required}
        sh = {**sheet, "lines": [{**c2, "limits": [lim]}]}
        state = {"version": 1, "sheet": sh, "lines": [{"line_id": "C2", "struck": [], "candidates": [cand("bare", None), cand("ct", "ct"), cand("cm", "cm")]}]}
        records.write_sync(state)
        assert sorted(r["product_id"] for r in passing.passing_box("C2")["rows"]) == sorted(expect), required
