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
    return make_state.build_state(sheet, pool, figures, answers, strikes)


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
        state = _state(sh, pool, figures, make_state.ANSWERS, strikes)
        state["version"] = trial + 1
        records.write_sync(state)
        for line in state["lines"]:
            want = sorted((c["product"]["store"], c["product"]["product_id"]) for c in line["candidates"] if c["status"] == "inside")
            got = passing.passing_box(line["line_id"])
            assert sorted((r["store"], r["product_id"]) for r in got["rows"]) == want, (trial, line["line_id"])
            assert "SELECT" in got["sql"] and "'" + line["line_id"] + "'" in got["sql"]
            checked += len(want)
    assert checked > 10
