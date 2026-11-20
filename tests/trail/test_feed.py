"""The trail feed: built from records only, never raises, and every event names one of seven steps and five kinds."""
from signoff.trail import feed

RECEIPTS = [
    {"n": 1, "at": "2026-11-20T12:00:00.000-08:00", "type": "chain_started", "actor": "system", "hash": "a" * 64,
     "prev_hash": "0" * 64, "detail": {"reason": "reset"}},
    {"n": 2, "at": "2026-11-20T12:01:00.000-08:00", "type": "request_refused", "actor": "issuer", "hash": "b" * 64,
     "prev_hash": "a" * 64, "detail": {"request": "set_limit", "accepted": False, "refused_because": "not_enrolled"}},
    {"n": 3, "at": "2026-11-20T12:02:00.000-08:00", "type": "request_accepted", "actor": "issuer", "hash": "c" * 64,
     "prev_hash": "b" * 64, "detail": {"request": "sign_sheet", "accepted": True}},
]


def ledger(n, at, recipient, purpose, kind, classes=("none",), **more):
    return {"n": n, "at": at, "recipient": recipient, "purpose": purpose, "kind": kind, "bytes": 10,
            "payload_sha256": "f" * 64, "fact_classes": list(classes), "sealed_hits": [], **more}


def state():
    product = {"store": "shop.example", "product_id": "p1", "title": "A thing", "price_cents": 1200,
               "url": "https://shop.example/p1", "fetched_at": "2026-11-20T11:00:00-08:00"}
    other = dict(product, product_id="p2", title="Another", fetched_at="2026-11-20T11:00:01-08:00")
    figure = {"figure": "overall_width", "value": 30, "low": 30, "high": 30, "unit": "in", "quote": "30 in wide",
              "span_found_in_text": True}
    return {"version": 3, "mode": "replay", "total_cents": 1200,
            "sheet": {"id": "s", "title": "T", "issuer": {"name": "Marco"}, "shopper": {"name": "Priya"},
                      "stores": ["shop.example"], "lines": []},
            "seal": {"signed": False, "carts": []}, "counts": {"products_found": 2, "inside_limits": 1, "lines_ready": 1},
            "lines": [{"line_id": "T1", "need": "vanity", "pick": "c1", "why": {"rule": "cheapest"}, "candidates": [
                {"id": "c1", "product": product, "figures": [figure], "status": "inside", "checks": [{"expr": "30 <= 30"}]},
                {"id": "c2", "product": other, "figures": [], "status": "not_stated", "reason": "width never stated"}]}]}


def build(**src):
    return feed.build(src)


def test_empty_sources_give_seven_empty_steps_and_never_raise():
    for nothing in (None, {}, {"state": None, "receipts": None, "egress": None}):
        out = feed.build(nothing)
        assert [s["id"] for s in out["steps"]] == list(feed.STEP_IDS)
        assert out["events"] == [] and out["summary"]["receipts"] == 0
        assert all(not s["done"] and s["events"] == 0 for s in out["steps"])


def test_every_event_has_a_step_and_a_kind_and_comes_from_a_record():
    out = build(state=state(), receipts=RECEIPTS, receipt_check={"verified": True, "first_bad": None},
                egress=[ledger(1, "2026-11-20T11:30:00-08:00", "anthropic:x", "read figures", "model", ["store_text"])])
    assert out["events"]
    for e in out["events"]:
        assert e["step"] in feed.STEP_IDS and e["kind"] in feed.KINDS
        assert e["items"] and e["count"] >= 1 and len(e["label"].split()) <= 5
    assert sum(s["events"] for s in out["steps"]) == len(out["events"])
    assert out["steps"][5]["label"] == "Marco signs"


def test_records_close_in_time_are_one_event_with_a_count_and_a_span():
    out = build(state=state())
    pages = [e for e in out["events"] if e["mark"] == "page"]
    assert len(pages) == 1 and pages[0]["count"] == 2 and pages[0]["label"] == "2 pages"
    assert pages[0]["duration_ms"] == 1000 and pages[0]["step"] == "stores_searched" and pages[0]["kind"] == "evidence"


def test_a_record_without_a_time_keeps_no_time():
    out = build(state=state())
    figures = [e for e in out["events"] if e["mark"] == "figure"]
    assert figures and all(e["at"] is None and e["duration_ms"] is None for e in figures)
    assert figures[0]["step"] == "pages_read" and figures[0]["kind"] == "reading" and figures[0]["verified"] is True
    assert out["steps"][3]["first_at"] is None and out["steps"][3]["duration_ms"] is None


def test_a_refused_request_is_its_own_stopped_approval():
    out = build(receipts=RECEIPTS, receipt_check={"verified": True, "first_bad": None})
    refused = [e for e in out["events"] if e["stopped"]]
    assert len(refused) == 1 and refused[0]["label"] == "Set limit refused" and refused[0]["kind"] == "approval"
    assert refused[0]["step"] == "signs" and refused[0]["receipt"] == 2 and refused[0]["detail"] == "not_enrolled"
    signs = out["steps"][5]
    assert signs["receipts"] == 2 and signs["refused"] == 1 and signs["done"] is False


def test_receipts_verified_counts_only_up_to_the_first_bad_link():
    out = build(receipts=RECEIPTS, receipt_check={"verified": False, "first_bad": 3})
    assert out["summary"]["receipts"] == 3 and out["summary"]["receipts_verified"] == 2
    assert [c["verified"] for c in out["chain"]] == [True, True, False]


def test_a_record_keeping_message_joins_the_step_in_progress_without_adding_to_its_time():
    rows = [ledger(1, "2026-11-20T11:30:00-08:00", "anthropic:x", "read figures", "model", ["store_text"]),
            ledger(2, "2026-11-20T11:30:05-08:00", "amplitude", "event", "sponsor service"),
            ledger(3, "2026-11-20T11:30:09-08:00", "amplitude", "event", "sponsor service")]
    out = build(egress=rows, egress_summary={"messages": 3, "to_stores": 0, "limits_in_store_messages": 0})
    kept = [e for e in out["events"] if e["detail"].startswith("amplitude")]
    assert kept[0]["step"] == "pages_read" and kept[0]["own_step"] is False and kept[0]["count"] == 2
    assert out["steps"][2]["duration_ms"] is None
    assert out["summary"]["messages_out"] == 3 and out["summary"]["limits_to_stores"] == 0


def test_measured_tool_calls_add_up_and_an_earlier_runs_checks_are_left_out():
    tools = [{"name": "check_run", "at": "2026-11-20T11:00:00.000-08:00", "duration_ms": 9.0, "success": True},
             {"name": "check_run", "at": "2026-11-20T12:00:30.000-08:00", "duration_ms": 3.0, "success": True},
             {"name": "check_run", "at": "2026-11-20T12:00:31.000-08:00", "duration_ms": 2.0, "success": True},
             {"name": "figure_read", "at": "2026-11-20T10:00:00.000-08:00", "duration_ms": 3100.0, "success": True}]
    out = build(tools=tools, receipts=RECEIPTS, receipt_check={"verified": True, "first_bad": None})
    runs = [e for e in out["events"] if e["label"].startswith("2 check")]
    assert len(runs) == 1 and runs[0]["duration_ms"] == 5 and runs[0]["timed"] == "measured" and runs[0]["step"] == "checked"
    assert out["summary"]["earlier_runs"] == 1 and not [e for e in out["events"] if e["label"] == "check run"]
    read = [e for e in out["events"] if e["step"] == "pages_read"]
    assert read and read[0]["kind"] == "reading" and read[0]["duration_ms"] == 3100   # cached reading outlives a reset


def test_a_blocked_store_message_is_stopped():
    rows = [ledger(1, "2026-11-20T11:30:00-08:00", "shop.example", "search_catalog", "store", ["order"], blocked=True,
                   sealed_hits=[{"class": "limit", "match": "30 in"}])]
    e = build(egress=rows)["events"][0]
    assert e["stopped"] and e["verified"] is False and e["step"] == "stores_searched" and e["label"] == "1 message blocked"


def test_collect_never_raises_and_names_each_source():
    src = feed.collect()
    assert {s["id"] for s in src["sources"]} >= {"state", "receipts", "egress"}
    feed.build(src)


def test_a_slow_source_is_read_once_and_then_held():
    calls = []
    feed._slow.pop("t", None)
    first = feed._held("t", lambda: calls.append(1) or {"n": len(calls)})
    again = feed._held("t", lambda: calls.append(1) or {"n": len(calls)})
    assert first == {"n": 1} and again == {"n": 1} and len(calls) == 1


def test_context_of_model_calls_comes_from_the_ledger_rows_and_a_found_limit_is_shown():
    read = dict(declared_classes=["product", "store_text"])
    rows = [ledger(1, "2026-11-20T11:30:00-08:00", "anthropic:x", "read figures from one store page", "model",
                   ["product", "store_text"], bytes=4000, sealed_found_in_payload=[], **read),
            ledger(2, "2026-11-20T11:30:02-08:00", "anthropic:x", "read figures from one store page", "model",
                   ["limit", "product", "store_text"], bytes=5000, sealed_found_in_payload=["limit: 300 lb"], **read),
            ledger(3, "2026-11-20T11:20:00-08:00", "anthropic:x", "read the limits from the written order", "model",
                   ["limit", "order", "person"], bytes=6000, declared_classes=["limit", "order", "person"],
                   sealed_found_in_payload=["limit: 300 lb"])]
    out = build(egress=rows, egress_classes=["limit", "home_measurement", "person", "order", "store_text", "product", "price", "none"])
    reads = next(e for e in out["events"] if e["step"] == "pages_read")
    c = reads["context"]
    assert c["calls"] == 2 and [(g["id"], g["calls"]) for g in c["given"]] == [("store_text", 2), ("product", 2)]
    assert [(f["id"], f["calls"], f["matches"]) for f in c["found"]] == [("limit", 1, ["300 lb"])]
    assert [n["id"] for n in c["not_given"]] == ["order", "home_measurement", "person", "price"] and c["only"] == 1
    assert c["bytes"] == {"min": 4000, "median": 5000, "max": 5000, "total": 9000}
    order = next(e for e in out["events"] if e["step"] == "list_read")["context"]
    assert [g["id"] for g in order["given"]] == ["order", "limit", "person"] and order["found"] == []
    assert out["steps"][2]["context"]["calls"] == 2 and out["steps"][0]["context"]["calls"] == 1
    total = out["summary"]["model_calls"]
    assert total["calls"] == 3 and total["only"] == 1
    assert all("_rows" not in e for e in out["events"])


def test_the_senders_own_parts_and_withheld_lists_are_passed_through_when_a_row_has_them():
    rows = [ledger(1, "2026-11-20T11:30:00-08:00", "anthropic:x", "read figures from one store page", "model",
                   ["store_text"], declared_classes=["store_text"], sealed_found_in_payload=[],
                   parts=[{"name": "page text", "chars": 3900, "pages": 1}, {"name": "figure meanings", "chars": 400}],
                   withheld=["limits", "prices"])]
    c = build(egress=rows)["events"][0]["context"]
    assert c["parts"] == [{"name": "page text", "calls": 1, "chars": 3900}, {"name": "figure meanings", "calls": 1, "chars": 400}]
    assert c["withheld"] == [{"name": "limits", "calls": 1}, {"name": "prices", "calls": 1}]


def test_the_flow_follows_one_item_from_the_records_and_says_nothing_it_has_no_record_for():
    out = build(state=state())
    f = out["flow"]
    assert f["focus"]["line_id"] == "T1" and f["pick"]["title"] == "A thing" and f["pick"]["price"] == "$12.00"
    assert f["said"]["page"]["excerpt"] == [{"text": "30 in wide", "quote": [0, 10]}] and f["model"]["quoted"] == ["30 in wide"]
    assert f["model"]["source"] == "prompt builder" and f["model"]["outside"] is None   # no ledger rows for the reads
    assert f["refused"] is None and f["talk"] is None and f["memory"] is None and f["signature"]["signed"] is False
    assert [s["id"] for s in f["rail"]] == list(feed.STEP_IDS)
    assert feed.build({})["flow"] is None


def test_the_guard_row_is_the_message_about_the_picked_product_with_the_most_removed():
    talk = [{"draft": "hello", "removed": [], "left": [], "product": {"id": "p1"}, "store": "shop.example", "reply": {"text": "hi"}},
            {"draft": "my mum, 280 lb", "removed": [{"text": "280 lb", "mark": "health detail"}], "left": [{"mark": "product name"}],
             "product": {"id": "p1"}, "store": "shop.example", "reply": {"text": "ok"}, "decision": "rewritten"},
            {"draft": "other", "removed": [{"text": "a"}, {"text": "b"}], "product": {"id": "p2"}, "store": "shop.example"}]
    g = build(state=state(), talk=talk)["flow"]["talk"]
    assert g["draft"] == "my mum, 280 lb" and g["removed"] == [{"text": "280 lb", "mark": "health detail"}]
    assert g["left"] == ["product name"] and g["reply"] == "ok" and g["messages"] == 3 and g["stopped"] == 3
