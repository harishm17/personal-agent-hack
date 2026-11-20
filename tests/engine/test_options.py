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
