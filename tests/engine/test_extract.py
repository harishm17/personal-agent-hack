import json
import pathlib

from signoff.extract import combine, gliner, reader, spans

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TEXT = ("Shower Chair.\nSupports up to 300 lbs. Seat width 16 inches. Overall Width: 20.25”. "
        "Seat height adjusts from 16\" to 21\". Adds 4 1/2 inches of height. Seat (Height): 13.5-17.")
PRODUCT = {"store": "s.example", "product_id": "p1", "text": TEXT, "line_ids": ["L1"]}


def fig(**over):
    base = {"figure": "weight_capacity", "stated": True, "kind": "single", "value": 300, "low": None, "high": None,
            "unit": "lbs", "quote": "Supports up to 300 lbs"}
    return spans.finish(dict(base, **over), PRODUCT, "test")


def test_code_sets_the_offsets_and_the_quote_is_the_stores_text():
    f = fig()
    assert f["span_found_in_text"] and TEXT[f["start"]:f["end"]] == f["quote"] == "Supports up to 300 lbs"
    assert (f["value"], f["low"], f["high"], f["unit"]) == (300, 300, 300, "lb") and "unsure" not in f


def test_a_quote_that_is_not_in_the_text_is_not_found():
    f = fig(quote="Supports up to 350 lbs", value=350)
    assert f["span_found_in_text"] is False and f["start"] is None


def test_spacing_and_curly_marks_are_forgiven_but_the_stored_quote_is_the_stores():
    f = fig(figure="overall_width", value=20.25, unit="in", quote='overall  width: 20.25"')
    assert f["span_found_in_text"] and f["span_match"] == "normalised" and f["quote"] == "Overall Width: 20.25”"
    assert TEXT[f["start"]:f["end"]] == f["quote"]


def test_a_number_that_is_not_in_the_quote_makes_the_figure_unsure():
    f = fig(value=350)
    assert f["span_found_in_text"] and f["unsure"] and "not in the quoted words" in f["unsure_reason"]
    seat = fig(figure="overall_width", value=16, unit="in", quote="Seat width 16 inches")
    assert "unsure" not in seat  # code cannot tell seat width from overall width; the reader's prompt and the
    # second reader are there for that. Code only refuses numbers that are not in the words.


def test_ranges_fractions_and_missing_units():
    r = fig(figure="seat_height", kind="adjustable", value=None, low=21, high=16, unit='"',
            quote='Seat height adjusts from 16" to 21"')
    assert (r["kind"], r["value"], r["low"], r["high"], r["unit"]) == ("adjustable", None, 16, 21, "in")
    assert spans.numbers_in("Adds 4 1/2 inches") [0] == 4.5 and 4.5 in spans.numbers_in("4½ in")
    h = fig(figure="added_height", value=4.5, unit="in", quote="Adds 4 1/2 inches of height")
    assert h["span_found_in_text"] and "unsure" not in h
    n = fig(figure="seat_height", kind="adjustable", value=None, low=13.5, high=17, unit=None, quote="Seat (Height): 13.5-17")
    assert n["unsure"] and "without a unit" in n["unsure_reason"]
    cm = fig(figure="overall_width", value=20.25, unit="cm", quote="Overall Width: 20.25”")
    assert cm["unit"] == "in" and cm["stated_unit"] == "cm" and cm["value"] == 7.97


def test_the_reader_asks_only_for_the_figures_the_sheet_sums():
    sheet = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
    assert reader.wanted_figures({"line_ids": ["L2"]}, sheet) == ["weight_capacity", "added_height"]
    assert reader.wanted_figures({"line_ids": ["L9"]}, sheet) == []
    got = reader.parse('Here you go:\n```json\n{"figures": [{"figure": "length", "stated": false}]}\n```')
    assert got == [{"figure": "length", "stated": False}]


def test_the_entity_reader_parses_the_number_and_refuses_the_products_own_weight():
    text = "Weight Capacity: 300 lbs. Product Weight: 4.5 lbs. Seat height from 16 inches to 21 inches."
    at = text.index("300 lbs")
    made = gliner.proposal({"start": at, "end": at + 7, "text": "300 lbs", "score": 0.6}, "weight_capacity", text)
    assert made["value"] == 300 and made["unit"] == "lb"
    at = text.index("4.5 lbs")
    assert gliner.proposal({"start": at, "end": at + 7, "text": "4.5 lbs", "score": 0.9}, "weight_capacity", text) is None
    at = text.index("16 inches")
    made = gliner.proposal({"start": at, "end": at + 9, "text": "16 inches", "score": 0.6}, "seat_height", text)
    assert (made["kind"], made["low"], made["high"]) == ("adjustable", 16.0, 21.0)
    assert spans.finish(made, {"store": "s", "product_id": "p", "text": text}, gliner.EXTRACTOR)["span_found_in_text"]


def row(name, value, **over):
    base = {"store": "s", "product_id": "p", "figure": "weight_capacity", "kind": "single", "value": value,
            "low": value, "high": value, "unit": "lb", "quote": "q", "start": 0, "end": 1, "extractor": name,
            "span_found_in_text": True}
    return dict(base, **over)


def test_the_reference_reader_decides_and_agreement_is_recorded():
    out = combine.combine([("ref", [row("ref", 300)]), ("b", [row("b", 300)])], [("e", [row("e", 300)])])
    assert out[0]["extractor"] == "ref" and out[0]["agreed_by"] == ["ref", "b"]
    assert out[0]["also_marked_by"][0]["extractor"] == "e"
    out = combine.combine([("ref", [row("ref", 300)]), ("b", [row("b", 350)])])
    assert out[0]["value"] == 300 and out[0]["agreed_by"] == ["ref"] and len(out[0]["readers"]) == 2
    assert combine.combine([("ref", []), ("b", [row("b", 350)])]) == []  # the reference reports nothing: no figure
    unsure = combine.combine([("ref", [row("ref", 300, unsure=True, unsure_reason="two sizes")]), ("b", [row("b", 300)])])
    assert unsure[0]["unsure"] and "agreed_by" not in unsure[0]


def test_under_the_agree_policy_a_figure_counts_only_when_the_readers_match():
    both = [("a", [row("a", 300)]), ("b", [row("b", 300)])]
    assert combine.counted(combine.combine(both, policy="agree")[0])
    differ = combine.combine([("a", [row("a", 300)]), ("b", [row("b", 350)])], policy="agree")[0]
    assert differ["unsure"] and "readers differ" in differ["unsure_reason"]
    alone = combine.combine([("a", [row("a", 300)]), ("b", [])], policy="agree")[0]
    assert alone["unsure"] and "only a reports it" in alone["unsure_reason"]


def test_only_a_live_call_uses_the_api_key_and_it_is_capped_with_the_command_line_as_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(reader, "ask_claude_cli", lambda m, s, u, timeout=0: (calls.append("cli") or '{"figures": []}', {}))
    monkeypatch.setattr(reader.config, "have", lambda name: True)
    monkeypatch.setattr(reader.config, "env", lambda name, default=None: None)
    monkeypatch.setattr(reader, "ask_anthropic_api", lambda m, s, u: (calls.append("api") or "{}", {"via": "api"}))
    monkeypatch.setattr(reader, "_api_calls", {"made": 0, "capped_logged": False})
    assert reader.ask("claude-sonnet-5-5", "s", "u")[2] == "anthropic:claude-sonnet-5-5" and calls == ["cli"]  # batch
    assert reader.ask("claude-sonnet-5-5", "s", "u", live=True)[1] == {"via": "api"} and calls == ["cli", "api"]

    def broken(model, system, user):
        calls.append("api failed")
        raise RuntimeError("402")
    monkeypatch.setattr(reader, "ask_anthropic_api", broken)
    assert reader.ask("claude-sonnet-5-5", "s", "u", live=True)[0] == '{"figures": []}'
    assert calls[-2:] == ["api failed", "cli"]  # one try, no retry, then the command line
    reader._api_calls["made"] = reader.API_CALL_CAP
    reader.ask("claude-sonnet-5-5", "s", "u", live=True)
    assert calls[-1] == "cli" and calls.count("api failed") == 1 and reader._api_calls["capped_logged"]


def test_a_record_without_its_number_agrees_with_nothing_and_does_not_break_the_comparison():
    empty = row("ref", None, unsure=True, unsure_reason="no number was reported")
    out = combine.combine([("ref", [empty]), ("b", [row("b", 300)])], [("e", [row("e", 300)])])
    assert out[0]["unsure"] and "also_marked_by" not in out[0] and "agreed_by" not in out[0]
    assert combine.same(empty, row("b", 300)) is False


def test_units_come_from_the_sheets_limit_so_another_sheet_needs_no_code():
    text = "Stock Pot. Holds 8 QT. Also sold as 7.6 liters. Oven safe to 260°C."
    product = {"store": "s", "product_id": "p", "text": text}
    qt = spans.finish({"figure": "capacity", "kind": "single", "value": 8, "unit": "QT", "quote": "Holds 8 QT"},
                      product, "test", target_unit="qt")
    assert (qt["value"], qt["unit"], qt.get("unsure")) == (8, "qt", None)
    litres = spans.finish({"figure": "capacity", "kind": "single", "value": 7.6, "unit": "liters", "quote": "7.6 liters"},
                          product, "test", target_unit="qt")
    assert litres["unit"] == "qt" and litres["value"] == 8.03 and litres["stated_unit"] == "L"
    heat = spans.finish({"figure": "oven_safe", "kind": "single", "value": 260, "unit": "°C", "quote": "Oven safe to 260°C"},
                        product, "test", target_unit="°F")
    assert heat["value"] == 500.0 and heat["unit"] == "°F"
    wrong = spans.finish({"figure": "capacity", "kind": "single", "value": 8, "unit": "in", "quote": "Holds 8 QT"},
                         product, "test", target_unit="qt")
    assert wrong["unsure"] and "cannot be compared" in wrong["unsure_reason"]


def numbered(figure, quote, value, label=None, unit="in"):
    return {"figure": figure, "quote": quote, "kind": "single", "value": value, "low": value, "high": value,
            "unit": unit, "label": label, "span_found_in_text": True}


def test_a_number_counts_only_if_it_is_the_only_one_or_the_text_labels_it():
    rule = spans.apply_unambiguous_rule
    several = 'Product Dims (h x w x d): 1.63" x 31" x 14.75"'
    assert rule(numbered("overall_width", several, 31, "w")) is False            # the list of labels pairs w with 31
    wrong = numbered("overall_width", several, 14.75, "w")
    assert rule(wrong) is True and wrong["unsure_reason"].startswith(spans.AMBIGUOUS)
    assert "pairs the label 'w' with another number" in wrong["unsure_reason"]
    silent = numbered("overall_width", several, 31)
    assert rule(silent) is True and "gave no label" in silent["unsure_reason"]    # several numbers and no label: unsure
    assert rule(numbered("overall_width", "Overall Width: 21.5 inches", 21.5)) is False   # one number: nothing to settle
    # a number in another kind of unit is not a rival
    assert rule(numbered("weight_capacity", "Supports 300 lbs with a seat width of 16 inches", 300, unit="lb")) is False
    # a range the reader reported whole has no rival either
    whole = dict(numbered("seat_height", 'Seat height adjusts from 16" to 21"', None), kind="adjustable", low=16, high=21)
    assert rule(whole) is False


def test_the_pairing_is_read_from_the_text_alone_whatever_the_separator_or_the_words():
    ok = lambda *a, **k: spans.apply_unambiguous_rule(numbered(*a, **k)) is False  # noqa: E731
    assert ok("overall_width", 'Product Dims (h x w x d): 16" - 21" x 21" x 18"', 21, "w")       # 21 is also in the height range
    assert ok("overall_width", 'Outside Legs: 17.5" (W) x 17.25" (D)', 17.5, "W")                 # the label beside the number
    assert ok("overall_width", "Dimensions: 23.5”W x 20”L x 32” - 40”H", 23.5, "W")
    assert ok("overall_width", "W/D/H: 20/18/30 in", 20, "W")                                     # another separator
    assert not ok("overall_width", "Width, Depth, Height: 20, 18, 30 inches", 18, "Width")        # words, and the wrong place
    assert ok("capacity", "Capacity: 300 lbs. Product Weight: 4.5 lbs", 300, "Capacity", unit="lb")
    assert not ok("capacity", "Capacity: 300 lbs. Product Weight: 4.5 lbs", 4.5, "Capacity", unit="lb")
    assert ok("length", 'Length: 12" or 16"', 12, "Length")
    assert not ok("length", 'Available in 12", 16", 18", 24", and 32" length.', 12, "length")     # the text does not say 12
    assert not ok("overall_width", 'Product Dims (h x w x d): 1.63" x 31" x 14.75"', 31, "width") # a label that is not in the quote


def test_the_rule_runs_on_every_new_read_and_keeps_the_readers_label():
    text = 'Bench.\nProduct Dims (h x w x d): 1.63" x 31" x 14.75" Weight Capacity: 300 lbs.'
    page = {"store": "s", "product_id": "p", "text": text}
    quote = 'Product Dims (h x w x d): 1.63" x 31" x 14.75"'
    wrong = spans.finish({"figure": "overall_width", "kind": "single", "value": 14.75, "unit": "in", "quote": quote,
                          "label": "w"}, page, "any")
    assert wrong["span_found_in_text"] and wrong["unsure"] and wrong["caught_by"].startswith("code:")
    right = spans.finish({"figure": "overall_width", "kind": "single", "value": 31, "unit": "in", "quote": quote,
                          "label": "w"}, page, "any")
    assert "unsure" not in right and right["label"] == "w" and right["number_check"]["paired"] is True
    plain = spans.finish({"figure": "weight_capacity", "kind": "single", "value": 300, "unit": "lbs",
                          "quote": "Weight Capacity: 300 lbs."}, page, "any")
    assert "number_check" not in plain and "unsure" not in plain
    assert "label" in reader.SYSTEM and "h x w" not in reader.SYSTEM.lower()  # the instruction names no format


def test_the_comparison_lists_disagreements_extras_and_what_the_rule_caught(tmp_path):
    from signoff.extract import score
    quote = 'Product Dims (h x w x d): 1.63" x 31" x 14.75"'
    def fig(extractor, figure, value, q=quote, label=None):
        return {"store": "s", "product_id": "p", "figure": figure, "kind": "single", "value": value, "low": value,
                "high": value, "unit": "in", "quote": q, "start": 0, "end": len(q), "extractor": extractor,
                "span_found_in_text": True, "label": label}
    for name, rows in (("claude-sonnet-5-5", [fig("anthropic:claude-sonnet-5-5", "overall_width", 31, label="w")]),
                       ("small", [fig("small", "overall_width", 14.75, label="w"), fig("small", "length", 12, "12 in long")])):
        folder = tmp_path / "_runs" / name
        folder.mkdir(parents=True)
        (folder / "s.json").write_text(json.dumps(rows))
        (folder / "s.log").write_text(json.dumps([{"store": "s", "product_id": "p", "extractor": rows[0]["extractor"],
                                                   "asked": ["overall_width", "length"], "seconds": 1.0, "usage": {}}]))
    made = score.compare(tmp_path)
    small = next(r for r in made["readers"] if r["extractor"] == "small")
    # as read, the small reader disagrees on the width; with the rule on, code has marked its figure unsure
    assert small["number_rule"]["before"]["statement"] == (
        "same number on 0 of 1 figures both readers found; the reference alone found 0, this reader alone found 1")
    assert small["statement"] == ("same number on 0 of 0 figures both readers found; the reference alone found 1, "
                                  "this reader alone found 1")
    caught = small["number_rule"]["caught"]
    assert len(caught) == 1 and caught[0]["value"] == "14.75" and caught[0]["number_check"]["paired"] is False
    assert made["number_rule"]["reference_figures_caught"] == 0 and list(made["number_rule"]["caught"]) == ["small"]
    assert [e["figure"] for e in small["extra"]] == ["length"]
