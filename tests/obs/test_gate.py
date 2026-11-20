from signoff import obs
from signoff.obs import gate

MEASURED = {"mode": "both must agree", "real_disagreements_caught": 5, "figures_blocked_that_only_the_reference_found": 27,
            "figures_only_the_second_reader_found": 3, "figures_agreed": 238, "candidates_changed": 19, "moved_to_unclear": 18,
            "picks_changed": [{"line_id": "L4", "one_reader": {"title": "Walker A", "price_cents": 4471},
                               "both_must_agree": {"title": "Walker B", "price_cents": 6999}}],
            "total_cents_one_reader": 11469, "total_cents_both_must_agree": 13997}


class FakeEngine:
    def __init__(self, signed=False, measured=MEASURED):
        self.signed, self.mode, self.calls, self.measured = signed, "disagreement blocks", [], measured

    def get_state(self):
        return {"seal": {"signed": self.signed}, "counts": {},
                "two_readers": {"mode": self.mode, "reference": "ref", "second": "sec", "strict_mode_measured": self.measured},
                "readers": {"readers": [{"extractor": "ref", "pages_read": 10, "seconds_per_page_median": 3.0, "cost": {"usd_total": 1}},
                                        {"extractor": "sec", "pages_read": 10, "seconds_per_page_median": 6.0, "cost": {"sie_credits_total": 9}}]}}

    def set_reading_mode(self, mode):
        self.calls.append(mode)
        self.mode = mode


def _fresh(monkeypatch, eng):
    monkeypatch.setattr(gate, "_engine", lambda: eng)
    monkeypatch.setattr(gate, "_override", None)
    monkeypatch.setattr(gate, "_save_history", lambda: None)
    gate._s.update(value=False, arm="disagreement-blocks", changed_at=None, history=[], refused=None, error=None)
    events, exps = [], []
    monkeypatch.setattr(obs, "tool_call", lambda *a, **k: events.append(a))
    monkeypatch.setattr(obs, "set_experiments", lambda e: exps.append(e))
    return events, exps


def test_gate_on_switches_the_reading_mode_tags_the_arm_and_logs_one_event(monkeypatch):
    eng = FakeEngine()
    events, exps = _fresh(monkeypatch, eng)
    gate.set_override(True)
    assert eng.calls == ["both must agree"] and exps == [[{"key": "sie_reader", "variant": "both-must-agree"}]]
    assert [e[0] for e in events] == ["gate.changed"] and set(events[0][2]) >= {"before", "after", "decision"}
    gate.set_override(True)
    assert len(events) == 1
    gate.set_override(False)
    assert eng.calls[-1] == "disagreement blocks" and exps[-1][0]["variant"] == "disagreement-blocks" and len(events) == 2


def test_no_switch_after_signing(monkeypatch):
    eng = FakeEngine(signed=True)
    events, exps = _fresh(monkeypatch, eng)
    gate.set_override(True)
    assert eng.calls == [] and events == [] and gate._s["arm"] == "disagreement-blocks"


def test_engine_refusal_never_raises(monkeypatch):
    eng = FakeEngine()
    eng.set_reading_mode = lambda mode: (_ for _ in ()).throw(RuntimeError("refused"))
    events, exps = _fresh(monkeypatch, eng)
    gate.set_override(True)
    assert gate._s["refused"] and gate._s["arm"] == "disagreement-blocks"


def test_the_verdict_is_decided_from_what_the_strict_mode_costs_in_what_is_bought(monkeypatch):
    eng = FakeEngine()
    _fresh(monkeypatch, eng)
    monkeypatch.setitem(gate._s, "history", [{"at": "t", "value": True, "arm": "both-must-agree"}])
    ev = gate.evidence()
    assert ev["real_disagreements_caught"] == 5 and ev["extra_cost_cents"] == 2528 and ev["per_page"]["second"]["seconds_median"] == 6.0
    assert gate.verdict_from(ev) == "switch back"
    off, on = gate.decision(ev, False), gate.decision(ev, True)
    assert off["decision"] == "switched back" and on["decision"] == "switch back advised (the gate is on)"
    assert "caught 5 real disagreements" in off["text"] and "L4" in off["text"] and "$25.28 more" in off["text"]
    assert "Amplitude" not in off["text"] and off["decided_by"].startswith("code")
    free = dict(MEASURED, picks_changed=[], total_cents_both_must_agree=11469)
    eng2 = FakeEngine(measured=free)
    _fresh(monkeypatch, eng2)
    ev2 = gate.evidence()
    assert gate.verdict_from(ev2) == "kept" and gate.decision(ev2, True)["decision"] == "kept" and gate.decision(ev2, False)["decision"] == "not adopted"
    assert gate.verdict_from({}) is None and gate.verdict_from({"error": "x"}) is None
