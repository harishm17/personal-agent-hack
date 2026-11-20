import json

from signoff.sign import senso

from .standin import ROOT


def state():
    return json.loads((ROOT / "fixtures" / "state.json").read_text())


def test_sentences_are_terms_and_never_name_a_store():
    rows = senso.sentences_for(state())
    assert rows
    stores = {r["store"] for r in rows}
    for r in rows:
        assert not any(s in r["sentence"] for s in stores)  # a claim naming another brand gets no verdict
    assert {r["kind"] for r in rows} == {"limit", "order"}  # store quotes are not sent: a claim naming no brand got no verdict
    assert all(r["blocks"] for r in rows if r["kind"] == "order") and not any(r["blocks"] for r in rows if r["kind"] == "limit")
    assert all(r["sentence"].startswith("Our order requires") for r in rows)


def test_store_sentences_on_request(monkeypatch):
    monkeypatch.setattr(senso, "STORE_SENTENCES", True)
    assert "store" in {r["kind"] for r in senso.sentences_for(state())}


def test_pick_up_line_is_checked_as_pick_up_not_as_a_cart():
    rows = senso.sentences_for(state())
    assert any("picked up locally" in r["sentence"] for r in rows if r["line_id"] == "L5")


def test_moved_limit_is_labelled(monkeypatch):
    st = state()
    for line in st["sheet"]["lines"]:
        for limit in line["limits"]:
            if limit["id"] == "L2.height":
                limit["bound"]["value"] = 21.0
                limit["from_order"] = {"value": 19.0, "matches": False, "quote": "q"}
    rows = {r["sentence"]: r for r in senso.sentences_for(st) if r["kind"] == "limit"}
    moved = [r for r in rows.values() if r["moved_from_order"]]
    assert len(moved) == 1 and "21 inches" in moved[0]["sentence"]


class FakeClient:
    def __init__(self, verdicts):
        self.verdicts, self.calls = list(verdicts), 0

    def post(self, url, json):
        self.calls += 1
        verdict = self.verdicts.pop(0) if self.verdicts else "verified"
        claims = [{"claim_text": json["text"], "verdict": verdict, "quote": "q", "evidence": [{"content_id": "c1"}]}] if verdict else []

        class R:
            status_code = 200
            def json(self_inner):
                return {"status": "completed", "eval_run_id": "r1", "claims": claims}
        return R()


def test_blocking_sentence_is_asked_twice_before_it_counts_as_unsupported():
    client = FakeClient(["unsupported", "verified"])
    row = senso.judge(client, {"sentence": "A walker is required for the hall.", "blocks": True})
    assert row["verdict"] == "verified" and client.calls == 2


def test_conflict_is_not_retried_away():
    client = FakeClient(["conflict", "verified"])
    row = senso.judge(client, {"sentence": "x", "blocks": True})
    assert row["verdict"] == "conflict" and client.calls == 1


def test_no_verdict_on_a_blocking_sentence_means_unsupported():
    client = FakeClient([None, None, None])
    row = senso.judge(client, {"sentence": "A stair lift is required for the hall.", "blocks": True})
    assert row["verdict"] == "unsupported"


def test_advisory_sentence_is_asked_once():
    client = FakeClient(["unsupported"])
    row = senso.judge(client, {"sentence": "x", "blocks": False})
    assert row["verdict"] == "unsupported" and client.calls == 1


def test_a_verdict_names_the_version_of_the_document_it_was_checked_against(monkeypatch, tmp_path):
    monkeypatch.setattr(senso, "REGISTRY", tmp_path / "docs.json")
    senso._save_registry({"order:sheet2": {"title": "Bathroom remodel order (invented)", "content_id": "c1", "kb_node_id": "n1",
                                           "version_id": "v3", "version_num": 3, "sha": "x"}})

    class Client:
        def post(self, url, json):
            class R:
                status_code = 200
                def json(s):
                    return {"status": "completed", "eval_run_id": "r", "claims": [
                        {"claim_text": "c", "verdict": "verified", "quote": "q", "evidence": [{"content_id": "c1", "content_version_id": "v3", "chunk_index": 2}]}]}
            return R()
    row = senso.judge(Client(), {"sentence": "Our order requires a toilet for the bathroom.", "blocks": True, "kind": "order"})
    assert row["source"]["version_id"] == "v3" and row["source"]["version_num"] == 3 and row["source"]["title"].startswith("Bathroom")
    senso.set_checks([row], "h")
    assert senso.checks()["order_document"]["versions"][0]["version_num"] == 3
    # a verdict that rests on an older version says so
    class Old(Client):
        def post(self, url, json):
            r = super().post(url, json)
            body = r.json()
            body["claims"][0]["evidence"][0]["content_version_id"] = "v2"
            r.json = lambda: body
            return r
    old = senso.judge(Old(), {"sentence": "x", "blocks": False, "kind": "limit"})
    assert old["source"]["version_id"] == "v2" and old["source"]["version_num"] is None and old["source"]["latest_version_id"] == "v3"


def test_a_changed_document_becomes_a_new_version_of_the_same_node(monkeypatch, tmp_path):
    monkeypatch.setattr(senso, "REGISTRY", tmp_path / "docs.json")
    monkeypatch.setattr(senso, "documents", lambda sheet=None: [{"key": "order", "title": "T", "text": "new text"}])
    senso._save_registry({"order": {"title": "T", "content_id": "c1", "kb_node_id": "n1", "version_id": "v1", "version_num": 1, "sha": "old"}})
    calls = []

    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def put(self, url, json):
            calls.append(("put", url))
            class R:
                status_code = 200
                def json(s): return {"id": "c1", "kb_node_id": "n1", "latest_content_version_id": "v2", "version_num": 2}
            return R()
        def post(self, url, json):
            calls.append(("post", url)); raise AssertionError("a changed document must not be posted as a new one")
    monkeypatch.setattr(senso.httpx, "Client", Client)
    out = senso.load_documents()
    assert calls == [("put", senso.BASE + "/org/kb/nodes/n1/raw")] and out["documents"]["order"]["version_num"] == 2
    assert out["documents"]["order"]["version_id"] == "v2" and out["documents"]["order"]["content_id"] == "c1"


def test_every_sentence_is_sent_with_the_question_it_answers():
    sent = []

    class Client:
        def post(self, url, json):
            sent.append(json)
            class R:
                status_code = 200
                def json(s): return {"status": "completed", "eval_run_id": "r", "claims": [{"claim_text": "c", "verdict": "verified", "evidence": []}]}
            return R()
    senso.judge(Client(), {"sentence": "Our order requires pencils for writing.", "blocks": False, "kind": "order"})
    assert sent[0]["question"] == "What does our order require?" and sent[0]["author"] == "organization"
