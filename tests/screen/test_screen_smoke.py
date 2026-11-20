import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def test_screen_fixture_state_loads():
    state = json.loads((ROOT / "fixtures" / "state.json").read_text())
    assert state["lines"][1]["line_id"] == "L2"


def test_screen_fixture_copy_matches_the_fixture():
    """web/screen/fixture-state.json (drawn with ?fixture=1) must be the committed fixture run, byte for byte."""
    assert (ROOT / "web" / "screen" / "fixture-state.json").read_bytes() == (ROOT / "fixtures" / "state.json").read_bytes()


def test_screen_files_carry_the_agreed_wording():
    assert "The model reads the figure; code checks that the quote is in the store's text and does the sums." in \
        (ROOT / "web" / "screen" / "ladder.js").read_text()
    for name in ("model.js", "index.html", "ladder.js"):
        text = (ROOT / "web" / "screen" / name).read_text().lower()
        assert "proves" not in text and "proven" not in text, name
