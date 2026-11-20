"""The engine runs another sheet with no code about what the sheet is for. The sheet here is ENGINE's draft
(tests/engine/sheet2_draft.json); the pool is the STORE stream's real cookware pool; the figures were read
once by the reference reader and are cached under data/figures/sheet2/."""
import json
import pathlib
import shutil

import pytest

from signoff.engine import state

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def two_sheets(monkeypatch, tmp_path):
    if not any((ROOT / "data" / "sheet2" / "pool").glob("*.json")):
        pytest.skip("no pool for the second sheet in this checkout")
    shutil.copy(ROOT / "sheets" / "sheet1.json", tmp_path / "sheet1.json")
    shutil.copy(ROOT / "tests" / "engine" / "sheet2_draft.json", tmp_path / "sheet2.json")
    monkeypatch.setattr(state, "SHEETS", tmp_path)
    monkeypatch.setattr(state, "_record", lambda s: None)
    yield
    state._s.update(sheet_id=None, loaded=False, sheet=None)


def test_a_second_sheet_runs_from_its_file_alone(two_sheets):
    s = state.use_sheet("sheet2")
    assert s["sheet"]["title"] == "Shared kitchen" and len(s["lines"]) == 3 and s["counts"]["products_found"] > 100
    pots = next(l for l in s["lines"] if l["line_id"] == "stock_pot")
    inside = [c for c in pots["candidates"] if c["status"] == "inside"]
    assert inside and all(c["checks"][0]["bound"]["unit"] == "qt" for c in inside)
    for c in inside:  # every counted figure is a span of the store's own text, in the sheet's unit
        term = c["checks"][0]["terms"][0]
        assert term["unit"] == "qt" and term["quote"] and term["sentence"][slice(*term["quote_in_sentence"])] == term["quote"]
    before = pots["why"]["inside"]
    moved = state.apply_issuer({"type": "set_limit", "limit_id": "stock_pot.capacity", "value": 8})
    assert next(l for l in moved["lines"] if l["line_id"] == "stock_pot")["why"]["inside"] < before
    with pytest.raises(state.EngineError):
        state.use_sheet("sheet9")
    back = state.use_sheet("sheet1")
    assert back["sheet"]["id"] == "sheet1" and len(back["lines"]) == 6
    assert back["sheet"] == json.loads((ROOT / "sheets" / "sheet1.json").read_text())
