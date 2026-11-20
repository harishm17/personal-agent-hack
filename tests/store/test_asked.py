import json
import pathlib
import re

from signoff.store import asked, replay, ucp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SHEET = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
STATE = json.loads((ROOT / "fixtures" / "state.json").read_text())
PEOPLE = re.compile(r"dana|elena|therapist|daughter|father|surgery|doctor|patient|limit|at least|at most|reason", re.I)


def test_template_has_no_digit_person_or_limit_word():
    for fig in asked.FIGURE_WORDS:
        for unit in ("lb", "in"):
            q = asked.figure_question("Product", fig, unit)
            assert not re.search(r"\d", q) and not PEOPLE.search(q), q
    assert not re.search(r"\d", asked.returns_question("Product")) and not PEOPLE.search(asked.returns_question("Product"))


def test_every_planned_question_is_free_of_sheet_values():
    vals = asked.sheet_values(SHEET)
    assert {300.0, 19.0, 16.0, 15.0, 21.5, 28.0, 12.0} <= vals  # limit values and shopper facts, as on the sheet
    planned = asked.plan(STATE, SHEET)
    assert any("question" in t for t in planned)
    for t in planned:
        if "question" in t:
            assert asked.leaks(t["question"], SHEET) == [], t["question"]
            assert not PEOPLE.search(t["question"].replace(t["title"], "")), t["question"]


def test_leak_check_fails_when_a_limit_or_a_measurement_is_in_the_question():
    assert asked.leaks("Does it hold 300 pounds?", SHEET) == [300.0]
    assert asked.leaks("Does it fit a 21.5 inch tub?", SHEET) == [21.5]
    assert asked.leaks("Seat at 19 in", SHEET) == [19.0]
    assert asked.leaks("What does Carex 5-1/2 state", SHEET) == []


def test_a_title_with_a_sheet_value_is_skipped_not_asked():
    state = json.loads(json.dumps(STATE))
    for line in state["lines"]:
        for c in line["candidates"]:
            c["product"]["title"] = c["product"]["title"] + " 300 lb"
    planned = asked.plan(state, SHEET)
    assert planned and all("skipped" in t for t in planned)


def test_cached_question_is_not_asked_twice_and_replay_never_asks(monkeypatch, tmp_path):
    monkeypatch.setattr(asked, "CACHE", tmp_path)
    calls = []
    monkeypatch.setattr(ucp, "ask_business", lambda s, q: calls.append(q) or {"answer": {"plain": "It states 20 inches."}})
    t = {"store": "a.com", "product_id": "p1", "title": "Thing", "line_id": "L1", "role": "pick", "figure": "overall_width",
         "question": asked.figure_question("Thing", "overall_width", "in")}
    r1, r2 = asked.ask_one(t), asked.ask_one(t)
    assert len(calls) == 1 and r1 == r2 and r1["reply"] == "It states 20 inches."
    monkeypatch.setenv("SIGNOFF_MODE", "replay")
    t2 = dict(t, product_id="p2", question="another")
    assert asked.ask_one(t2) is None and len(calls) == 1
