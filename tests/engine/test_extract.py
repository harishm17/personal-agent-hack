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


def test_an_anthropic_model_uses_the_api_with_a_key_and_falls_back_to_the_command_line(monkeypatch):
    calls = []
    monkeypatch.setattr(reader, "ask_claude_cli", lambda m, s, u: (calls.append("cli") or '{"figures": []}', {}))
    monkeypatch.setattr(reader.config, "have", lambda name: False)
    assert reader.ask("claude-sonnet-5-5", "s", "u")[2] == "anthropic:claude-sonnet-5-5" and calls == ["cli"]

    def broken(model, system, user):
        calls.append("api")
        raise RuntimeError("401")
    monkeypatch.setattr(reader.config, "have", lambda name: True)
    monkeypatch.setattr(reader.config, "env", lambda name, default=None: None)
    monkeypatch.setattr(reader, "ask_anthropic_api", broken)
    assert reader.ask("claude-sonnet-5-5", "s", "u")[0] == '{"figures": []}' and calls == ["cli", "api", "cli"]
    monkeypatch.setattr(reader, "ask_anthropic_api", lambda m, s, u: (calls.append("api ok") or "{}", {"via": "api"}))
    assert reader.ask("claude-sonnet-5-5", "s", "u")[1] == {"via": "api"} and calls[-1] == "api ok"
