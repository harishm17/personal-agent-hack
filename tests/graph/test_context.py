"""The event's facts are read like a store's page: kept only when the quote is where the file says it is."""
import copy
import json
import pathlib

from signoff.graph import context, explore

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SHEET = {"id": "s", "need_by": "2026-12-02", "issuer": {"id": "dana", "name": "Dana", "role": "therapist"},
         "shopper": {"id": "elena", "name": "Elena"}, "shopper_facts": [{"id": "tub", "value": 21.5}],
         "lines": [{"id": "L1", "need": "chair", "limits": [{"id": "L1.capacity", "bound": {"value": 300}}]}]}
CONTEXT = {"event": {"id": "e", "label": "An event", "starts": "2026-11-24", "ends": "2026-12-02"}, "people": [],
           "classes": {"health": "never leaves"},
           "messages": [{"id": "m1", "from": "dana", "at": "2026-11-12T10:00:00-08:00", "text": "He weighs 280 lb. The tub is 21.5 inches wide."}],
           "facts": [{"id": "weight", "label": "Weighs 280 lb", "value": 280, "class": "health", "owner": "dana", "source": "m1",
                      "quote": "He weighs 280 lb", "start": 0, "end": 16, "feeds": [{"to": "/lines/0/limits/0", "verb": "is why"}]},
                     {"id": "tub", "label": "Tub 21.5 in", "value": 21.5, "class": "health", "owner": "elena", "source": "m1",
                      "quote": "The tub is 21.5 inches wide", "start": 18, "end": 45,
                      "feeds": [{"to": "/shopper_facts/0/value", "verb": "became the measurement", "equals": True}]},
                     {"id": "idle", "label": "Not used", "value": None, "class": "health", "owner": "dana", "source": "m1",
                      "quote": "He weighs", "start": 0, "end": 9, "feeds": []}]}


def test_a_fact_is_kept_only_if_its_quote_is_in_its_message_at_the_stated_place():
    c = copy.deepcopy(CONTEXT)
    c["facts"][0]["start"] = 3                      # the offsets no longer hold the quote
    c["facts"].append(dict(c["facts"][2], id="lost", source="m9"))
    got = context.read(c, SHEET, "sheets/s_context.json")
    assert [f["id"] for f in got["facts"]] == ["tub", "idle"]
    assert {d["id"]: d["why"] for d in got["dropped"]} == {"weight": "the quote is not in the message at the stated place", "lost": "no such message"}


def test_an_equals_feed_is_checked_against_the_sheet_and_a_disagreement_is_kept_visible():
    got = context.read(CONTEXT, SHEET)
    tub = next(f for f in got["facts"] if f["id"] == "tub")
    assert tub["feeds"][0]["matches"] is True and tub["feeds"][0]["sheet_value"] == 21.5
    weight = next(f for f in got["facts"] if f["id"] == "weight")
    assert weight["feeds"][0]["matches"] is None and weight["feeds"][0]["found"] is True
    other = copy.deepcopy(SHEET)
    other["shopper_facts"][0]["value"] = 22.0
    tub = next(f for f in context.read(CONTEXT, other)["facts"] if f["id"] == "tub")
    assert tub["feeds"][0]["matches"] is False and tub["feeds"][0]["sheet_value"] == 22.0


def test_a_sheet_without_a_context_file_has_no_event(tmp_path):
    held, name = context.load("nothing", tmp_path)
    assert held is None and name == "sheets/nothing_context.json" and context.read(held, SHEET) is None


def test_pointers_resolve_to_the_nodes_they_stand_for():
    assert explore._target("/lines/0/limits/0/bound/value", SHEET) == ["limit:L1.capacity"]
    assert explore._target("/shopper_facts", SHEET) == ["fact:tub"]
    assert explore._target("/shopper", SHEET) == ["person:shopper"]
    assert explore._target("/need_by", SHEET) is None
    assert explore._target("/lines/7/limits/0", SHEET) == []


def test_the_committed_context_file_holds_every_fact_it_claims():
    for path in sorted((ROOT / "sheets").glob("*_context.json")):
        sheet = json.loads((ROOT / "sheets" / (path.name.replace("_context", ""))).read_text())
        got = context.read(json.loads(path.read_text()), sheet, "sheets/" + path.name)
        assert got["dropped"] == [], (path.name, got["dropped"])
        assert all(feed["matches"] is not False for f in got["facts"] for feed in f["feeds"]), path.name
