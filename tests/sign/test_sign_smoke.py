import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def test_sign_fixture_state_loads():
    state = json.loads((ROOT / "fixtures" / "state.json").read_text())
    assert state["lines"][1]["line_id"] == "L2"
