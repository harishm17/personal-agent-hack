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
    """Mark some figures unsure, and add a clean duplicate behind an unsure one for a few: the SQL must follow the engine."""
    out = []
    for f in figures:
        f = dict(f)
        roll = rnd.random()
        if roll < 0.25:
            f["unsure"] = True
            f["unsure_reason"] = "test: two different numbers on the page"
        out.append(f)
        if roll < 0.08:  # an unsure figure first, then a sound one of the same name: the engine uses the sound one
            out[-1]["unsure"] = True
            out.append({**f, "unsure": False})
    return out


@pytest.mark.live  # talks to SingleStore, about 90 s: run with `uv run pytest -m live`, not in the gate
def test_sql_agrees_with_engine_on_fixtures_and_random_limits(db, monkeypatch):
    sheet = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
    pool, figures = make_state.build_inputs()
    monkeypatch.setattr(pool_mod, "load", lambda: (pool, make_state.ANSWERS))
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
            want = sorted((c["product"]["store"], c["product"]["product_id"]) for c in line["candidates"] if c["status"] == "inside")
            got = passing.passing_box(line["line_id"])
            assert sorted((r["store"], r["product_id"]) for r in got["rows"]) == want, (trial, line["line_id"])
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
