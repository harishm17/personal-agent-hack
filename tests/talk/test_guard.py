"""The guard: the sheet's sealed values by normalised match, model spans decided by code, the rule read from the sheet."""
import pytest

from signoff.talk import guard

TITLE = {"product_id": "p1", "title": "Carex 16-Inch Textured Grab Bar, 300 lb"}


def kinds(spans):
    return sorted({s["kind"] for s in spans})


@pytest.mark.parametrize("text, kind", [
    ("It has to hold 300 lb.", "limit"),
    ("It has to hold 300 pounds.", "limit"),
    ("It must carry three hundred pounds.", "limit"),
    ("Capacity needed: 300.", "limit"),
    ("The bar should be 16 inches or longer.", "limit"),
    ("Our tub is 21.5 inches inside.", "home_measurement"),
    ("Our tub is 21 1/2 in wide.", "home_measurement"),
    ("The tub is twenty-one and a half inches.", "home_measurement"),
    ("The door opening is 28\".", "home_measurement"),
    ("Dana wrote the order.", "person"),
    ("I am asking for Elena.", "person"),
    ("The occupational therapist asked for it.", "person"),
])
def test_each_sheet_value_is_found_however_it_is_written(sheet, text, kind):
    spans = guard.sheet_spans(text, sheet)
    assert kind in kinds(spans), spans
    assert all(text[s["start"]:s["end"]] == s["text"] for s in spans)


@pytest.mark.parametrize("text", [
    "Can an opened grab bar be returned, and will it arrive by December 2, 2026?",
    "Will it arrive by 2026-12-02 in California?",
    "How long is delivery? I can wait 3000 hours or 1300 minutes, not 28.75.",
])
def test_a_clean_message_has_no_sealed_span(sheet, text, finder):
    assert guard.check(text, sheet, None, finder) == []


def test_the_stores_own_title_is_not_ours_to_seal(sheet, finder):
    text = "Can an opened Carex 16-Inch Textured Grab Bar, 300 lb be returned?"
    assert guard.check(text, sheet, TITLE, finder) == []
    assert kinds(guard.check(text + " We need 300 lb.", sheet, TITLE, finder)) == ["limit"]


@pytest.mark.parametrize("text, kind", [
    ("She just had a hip replacement.", "health"),
    ("She weighs 280 pounds.", "health"),
    ("It is for my mother.", "person"),
    ("We can spend $120.", "money"),
    ("Ship it to 14 Oak Street.", "address"),
])
def test_model_spans_are_kept_by_code_for_sealed_kinds(sheet, finder, text, kind):
    assert kinds(guard.check(text, sheet, None, finder)) == [kind]


def test_code_drops_a_model_span_with_wrong_offsets_or_low_score(sheet):
    text = "She just had a hip replacement."
    wrong = lambda t, labels: [{"text": "hip replacement", "label": "medical procedure", "score": 0.9, "start": 0, "end": 5}]  # noqa: E731
    low = lambda t, labels: [{"text": "hip replacement", "label": "medical procedure", "score": 0.2, "start": 15, "end": 30}]  # noqa: E731
    assert guard.model_spans(text, sheet, wrong) == []
    pronoun = lambda t, labels: [{"text": "I", "label": "person name", "score": 0.62, "start": 0, "end": 1}]  # noqa: E731
    assert guard.model_spans("I need it soon.", sheet, pronoun) == []  # seen live, 20 Nov 14:00: a span that states nothing
    assert guard.model_spans(text, sheet, low) == []


def test_the_default_rule_and_a_sheets_own_rule(sheet, finder):
    assert guard.rule(sheet)["may"] == ["product", "need_by", "delivery_region"]
    assert guard.rule(sheet)["source"] == "default"
    text = "We can spend $120 and need it by December 2, 2026."
    assert kinds(guard.check(text, sheet, None, finder)) == ["money"]
    open_money = {**sheet, "sharing": {"store": ["product", "money"]}}
    assert kinds(guard.check(text, open_money, None, finder)) == ["need_by"]
    assert guard.rule(open_money)["source"] == "sheet"
    assert guard.check(text, {**sheet, "sharing": {"model": ["product"]}}, None, finder) != []  # no store rule: nothing may go


def test_cut_leaves_a_gap_where_each_span_was(sheet, finder):
    text = "For my mother Maria, who weighs 280 pounds; it must hold 300 lb. Can it be returned?"
    spans = guard.check(text, sheet, None, finder)
    out = guard.cut(text, spans)
    assert "280" not in out and "300" not in out and "Maria" not in out and "mother" not in out.lower()
    assert out.endswith("Can it be returned?") and guard.GAP in out
