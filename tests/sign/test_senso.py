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
    kinds = {r["kind"] for r in rows}
    assert kinds == {"limit", "order", "store"}
    assert all(r["blocks"] for r in rows if r["kind"] == "order") and not any(r["blocks"] for r in rows if r["kind"] in ("limit", "store"))


def test_pick_up_line_is_checked_as_pick_up_not_as_a_cart():
    rows = senso.sentences_for(state())
    assert any("picked up locally" in r["sentence"] for r in rows if r["line_id"] == "L5")


def test_moved_limit_is_labelled(monkeypatch):
    st = state()
    for line in st["sheet"]["lines"]:
        for limit in line["limits"]:
            if limit["id"] == "L2.height":
                limit["bound"]["value"] = 21.0
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
