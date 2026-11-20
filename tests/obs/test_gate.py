from signoff import obs
from signoff.obs import gate


class FakeEngine:
    def __init__(self, signed=False):
        self.signed, self.reader, self.calls = signed, None, []

    def get_state(self):
        return {"seal": {"signed": self.signed}, "counts": {"state_every_figure": 1},
                "readers": {"deciding": self.reader or "anthropic:claude-sonnet-5-5", "readers": []}}

    def set_reader(self, name=None):
        self.calls.append(name)
        self.reader = name


def _fresh(monkeypatch, eng):
    monkeypatch.setattr(gate, "_engine", lambda: eng)
    monkeypatch.setattr(gate, "_override", None)
    monkeypatch.setattr(gate, "_save_history", lambda: None)
    gate._s.update(value=False, arm="sonnet", changed_at=None, history=[], refused=None, error=None)
    events, exps = [], []
    monkeypatch.setattr(obs, "tool_call", lambda *a, **k: events.append(a))
    monkeypatch.setattr(obs, "set_experiments", lambda e: exps.append(e))
    return events, exps


def test_gate_on_switches_reader_tags_arm_and_logs_one_event(monkeypatch):
    eng = FakeEngine()
    events, exps = _fresh(monkeypatch, eng)
    gate.set_override(True)
    assert eng.calls == ["sie:Qwen/Qwen3.8-27B-FP8"]
    assert exps == [[{"key": "sie_reader", "variant": "sie-qwen"}]]
    assert [e[0] for e in events] == ["gate.changed"] and set(events[0][2]) >= {"before", "after"}
    gate.set_override(True)  # no change, no second event
    assert len(events) == 1
    gate.set_override(False)
    assert eng.calls[-1] is None and exps[-1][0]["variant"] == "sonnet" and len(events) == 2


def test_no_switch_after_signing(monkeypatch):
    eng = FakeEngine(signed=True)
    events, exps = _fresh(monkeypatch, eng)
    gate.set_override(True)
    assert eng.calls == [] and events == [] and gate._s["arm"] == "sonnet"


def test_engine_refusal_never_raises(monkeypatch):
    eng = FakeEngine()
    eng.set_reader = lambda name=None: (_ for _ in ()).throw(RuntimeError("refused"))
    events, exps = _fresh(monkeypatch, eng)
    gate.set_override(True)
    assert gate._s["refused"] and gate._s["arm"] == "sonnet"


def test_the_verdict_comes_from_disagreement_on_the_same_quote_not_from_counts(monkeypatch):
    monkeypatch.setitem(gate._s, "history", [{"at": "t", "value": True, "arm": "sie-qwen"}])
    evid = {"products_accepted": {"sonnet": 67, "sie-qwen": 81, "of": 111}, "small_accepts_more": 14,
            "inside_only_small_reader": [{"candidate": "c"}] * 3,
            "disagreements": {"different_value": 3, "small_only": 15, "reference_only": 0}}
    assert gate.verdict_from(evid) == "switch back"
    assert gate.decision(evid, False)["decision"] == "switched back"
    assert gate.decision(evid, True)["decision"] == "switch back advised (the gate is on)"
    t = gate.decision(evid, False)
    assert "3 quote(s)" in t["text"] and "Amplitude" not in t["text"] and t["decided_by"].startswith("code")
    extra_only = dict(evid, disagreements={"different_value": 0, "small_only": 15, "reference_only": 0})
    assert gate.verdict_from(extra_only) == "kept" and gate.decision(extra_only, True)["decision"] == "kept"
    assert gate.decision(extra_only, False)["decision"] == "not adopted"
    assert gate.verdict_from({}) is None
