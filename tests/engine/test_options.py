"""An option's own name is a statement about it; a statement about another size is not (E26)."""
import json
import pathlib

import pytest

from signoff.engine import options, rules, state
from signoff.extract import spans

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PAGE = ("Textured Grab Bars.\nSupporting up to 440 pounds. Sizes: 12” Grab bar- 15.11” end to end 16” Grab bar- 19.11” end to end "
        "24” Grab bar- 27.11” end to end")
SHEET = {"id": "t", "issuer": {"name": "Dana"}, "shopper": {"name": "Elena"}, "need_by": "2026-12-02", "shopper_facts": [],
         "pick_rule": {"id": "cheapest", "label": "cheapest"},
         "lines": [{"id": "L5", "need": "grab bar", "room": "bathroom", "fulfilment": "cart", "limits": [
             {"id": "L5.capacity", "name": "weight capacity", "terms": [{"source": "store", "figure": "weight_capacity"}],
              "op": ">=", "bound": {"source": "issuer", "value": 300}, "unit": "lb"},
             {"id": "L5.length", "name": "bar length", "terms": [{"source": "store", "figure": "length"}],
              "op": ">=", "bound": {"source": "issuer", "value": 16.0}, "unit": "in"}]}]}


def rows():
    row = {"store": "v.example", "product_id": "p", "variant_id": "v0", "title": "Textured Grab Bars", "price_cents": 2799,
           "url": "u", "fetched_at": "now", "product_key": "textured grab bars", "line_ids": ["L5"], "text": PAGE,
           "variant_title": "16 Inch",
           "options": [{"variant_id": "v16", "title": "16 Inch", "price_cents": 2799, "available": True},
                       {"variant_id": "v18", "title": "18 Inch", "price_cents": 1999, "available": True},
                       {"variant_id": "v12", "title": '12" / Polished', "price_cents": 1799, "available": True}]}
    return options.expand([row])


def figures(pool):
    out = []
    for row in pool:  # what a reader returns for every option page: the same statements of the shared text
        for value, quote in ((440, "Supporting up to 440 pounds"), (12, "12” Grab bar"), (16, "16” Grab bar"), (24, "24” Grab bar")):
            at = row["text"].index(quote)
            out.append({"store": row["store"], "product_id": row["product_id"], "variant_id": row["variant_id"],
                        "figure": "weight_capacity" if value == 440 else "length", "kind": "single", "value": value, "low": value,
                        "high": value, "unit": "lb" if value == 440 else "in", "quote": quote, "start": at, "end": at + len(quote),
                        "span_found_in_text": True, "extractor": "test"})
    return out


def test_the_option_name_is_read_as_a_figure_only_when_one_figure_has_that_kind_of_unit():
    pool = rows()
    named = options.named_figures(pool[1], SHEET, spans.quote_numbers, rules.unit_name, spans.family_of)
    assert named == [{"figure": "length", "value": 18.0, "unit": "in", "quote": "18 Inch",
                      "start": pool[1]["text"].index("18 Inch"), "end": pool[1]["text"].index("18 Inch") + 7}]
    assert pool[1]["text"][named[0]["start"]:named[0]["end"]] == "18 Inch"  # the name has a span in the candidate's own text
    assert options.named_figures(dict(pool[1], variant_title="White", text=PAGE + "\nSelected option: White."), SHEET,
                                 spans.quote_numbers, rules.unit_name, spans.family_of) == []


def test_a_statement_about_another_size_is_not_a_statement_about_this_option():
    pool = rows()
    made = state._option_names(pool, figures(pool), SHEET)
    built = rules.build_state(SHEET, pool, made, [], [])
    by_option = {c["product"]["variant_id"]: c for c in built["lines"][0]["candidates"]}
    # the page describes a 16 in bar and the option is named 16 Inch: they agree, and the page's own words are shown
    sixteen = by_option["v16"]
    assert sixteen["status"] == "inside" and sixteen["checks"][1]["expr"] == "16 >= 16"
    assert sixteen["checks"][1]["terms"][0]["quote"] == "16” Grab bar"
    # the 18 Inch option: the page describes 12, 16 and 24, none of them this option. Not "12, so outside": unclear, both shown
    eighteen = by_option["v18"]
    assert eighteen["status"] == "unclear" and eighteen["reason"] == "bar length: option says 18 in; the page describes 12, 16 and 24 in"
    assert not eighteen["picked"] and eighteen["checks"][1]["terms"][0]["quote"] == "18 Inch"
    # the 12 in option fails on its own size, with the page's statement about the 12 in bar
    twelve = by_option["v12"]
    assert twelve["status"] == "outside" and twelve["reason"] == "bar length: 12 >= 16 is false"
    assert built["lines"][0]["pick"].endswith("v16")  # the cheaper 18 Inch option is not picked on a guess


def test_the_words_shown_for_an_option_are_its_own_line_not_the_list_of_every_size():
    pool = rows()
    made = state._option_names(pool, figures(pool), SHEET)
    built = rules.build_state(SHEET, pool, made, [], [])
    sixteen = next(c for c in built["lines"][0]["candidates"] if c["product"]["variant_id"] == "v16")
    term = sixteen["checks"][1]["terms"][0]
    assert term["quote"] == "16” Grab bar" and term["sentence"] == "16” Grab bar- 19.11” end to end"
    assert term["sentence"][slice(*term["quote_in_sentence"])] == term["quote"]
    assert "12” Grab bar" not in term["sentence"] and "24” Grab bar" not in term["sentence"]
    assert term["option_match"]["why"] == "the option you would buy is 16 Inch; the page's line for it: 16” Grab bar- 19.11” end to end"


def stmt(value, figure="length", variant="v16", **over):
    base = {"store": "v.example", "product_id": "p", "variant_id": variant, "figure": figure, "kind": "single", "value": value,
            "low": value, "high": value, "unit": "in", "quote": "q%s" % value, "start": 0, "end": 2, "span_found_in_text": True}
    return dict(base, **over)


def test_both_readers_must_agree_a_figure_counts_only_when_the_second_reader_reports_the_same_value():
    key = lambda variant: ("v.example", "p", variant, "length")  # noqa: E731
    reference = [stmt(16, variant="a"), stmt(31, variant="b"), stmt(12, variant="c"), stmt(20, variant="e"), stmt(17, variant="e")]
    second = {key("a"): [stmt(16, variant="a")],                      # the same value: it counts
              key("b"): [stmt(14.75, variant="b")],                   # another number: the readers disagree
              key("d"): [stmt(24, variant="d")],                      # only the second reader reports it
              key("e"): [stmt(17, variant="e")]}                      # one of two statements is confirmed
    made, tally = state._require_agreement(reference, second)
    by = {(f["variant_id"], f["value"]): f for f in made}
    assert tally == {"agreed": 2, "disagreed": 1, "only_reference": 1, "only_second": 1}
    assert "disagree" not in by[("a", 16)] and "disagree" not in by[("e", 17)]
    assert by[("b", 31)]["disagree"] == "readers disagree: 31 and 14.75 in"
    assert by[("c", 12)]["disagree"] == "only one reader found it" and by[("d", 24)]["disagree"] == "only one reader found it"
    assert by[("e", 20)]["disagree"] == "only one reader found this statement"
    # and the rules: a statement the readers do not agree on cannot be compared, so the check is unclear, not absent
    assert rules.comparable(by[("b", 31)], "in") == "readers disagree: 31 and 14.75 in"
    assert rules.comparable(by[("a", 16)], "in") is None
