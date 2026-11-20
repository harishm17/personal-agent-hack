import json
import pathlib

from signoff.extract import asked, reader

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SHEET = json.loads((ROOT / "sheets" / "sheet1.json").read_text())


def row(reply, figure="overall_width"):
    return {"store": "s.example", "product_id": "p1", "figure": figure, "role": "not_stated", "line_id": "L1",
            "question": "What does Chair state for its overall width, in inches?", "reply": reply,
            "asked_at": "2026-11-20T12:05:00-08:00"}


def test_a_reply_that_states_the_figure_is_read_with_the_same_span_check_against_the_reply(monkeypatch):
    seen = {}

    def model(name, system, user, **kw):
        seen.update(system=system, user=user, purpose=kw.get("purpose"))
        return json.dumps({"figures": [{"figure": "overall_width", "stated": True, "kind": "single", "value": 19.5,
                                        "unit": "inches", "quote": "overall width of 19.5 inches"}]}), {}, "test-reader"
    monkeypatch.setattr(reader, "ask", model)
    reply = "The Chair has an overall width of 19.5 inches, measured outside the legs."
    out = asked.read_reply(row(reply), SHEET, "test-reader")
    assert out["answered"] is True and (out["value"], out["unit"]) == (19.5, "in")
    assert reply[out["start"]:out["end"]] == out["quote"] == "overall width of 19.5 inches"
    # the question and the reading prompt hold no limit, no measurement of the home and nobody's name
    assert seen["system"] == reader.SYSTEM and "21.5" not in seen["user"] and "300" not in seen["user"]
    assert "Elena" not in seen["user"] and "Dana" not in seen["user"] and "overall_width" in seen["user"]


def test_a_number_that_is_not_in_the_reply_and_a_reply_that_says_nothing_are_not_answers(monkeypatch):
    monkeypatch.setattr(reader, "ask", lambda *a, **k: (json.dumps({"figures": [
        {"figure": "overall_width", "stated": True, "kind": "single", "value": 19.5, "unit": "in",
         "quote": "overall width of 19.5 inches"}]}), {}, "test-reader"))
    out = asked.read_reply(row("The store's information does not specify the Chair's overall width."), SHEET, "test-reader")
    assert out["answered"] is False and out["start"] is None  # the quote is not in the reply: thrown away
    monkeypatch.setattr(reader, "ask", lambda *a, **k: ('{"figures": [{"figure": "overall_width", "stated": false}]}', {}, "t"))
    assert asked.read_reply(row("The store's information does not specify it."), SHEET, "t")["answered"] is False


def test_a_returns_and_delivery_reply_is_kept_as_it_is_and_no_model_reads_it(monkeypatch):
    def no_model(*a, **k):
        raise AssertionError("not a figure: nothing to read")
    monkeypatch.setattr(reader, "ask", no_model)
    out = asked.read_reply(row("Standard delivery generally takes 1–5 business days.", "returns_and_delivery"), SHEET, "t")
    assert out["answered"] is None and out["reply"].startswith("Standard delivery")
