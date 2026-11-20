import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def load():
    spec = importlib.util.spec_from_file_location("fd", ROOT / "evals" / "firedrill" / "fd.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_command_that_sends_something_is_in_the_ledger_before_it_runs(monkeypatch):
    fd = load()
    seen, ran = [], []
    from signoff import obs
    monkeypatch.setattr(obs, "egress", lambda recipient, purpose, payload=None, fact_classes=None: seen.append((recipient, purpose, payload, fact_classes)))
    monkeypatch.setattr(fd.subprocess, "call", lambda cmd: ran.append(cmd) or 0)
    fd.main(["library", "save", "--kind", "persona", "--file", str(ROOT / "evals" / "firedrill" / "persona_cart.json")])
    assert ran == [["firedrill", "library", "save", "--kind", "persona", "--file", str(ROOT / "evals" / "firedrill" / "persona_cart.json")]]
    assert seen[0][0] == "firedrill" and "library save" in seen[0][1] and "Elena needs the cart now" in seen[0][2]
    fd.main(["status"])                                      # reading status sends nothing
    assert len(seen) == 1
