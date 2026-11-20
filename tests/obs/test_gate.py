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
