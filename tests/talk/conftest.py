import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """No analytics, a ledger and a thread folder of the test's own, live mode unless a test says otherwise."""
    from signoff.obs import _egress_module as ledger
    from signoff.talk import talk
    monkeypatch.setenv("SIGNOFF_OBS", "off")
    monkeypatch.setenv("SIGNOFF_MODE", "live")
    monkeypatch.setenv("SIGNOFF_SHEET", "sheet4")
    monkeypatch.setattr(ledger, "LEDGER", tmp_path / "ledger.jsonl")
    ledger.reset_for_tests()
    monkeypatch.setattr(talk, "DIR", tmp_path / "threads")
    monkeypatch.setattr(talk, "SPACING_SECONDS", 0.0)


@pytest.fixture
def sheet():
    return json.loads((ROOT / "sheets" / "sheet4.json").read_text())


WORDS = {"hip replacement": "medical procedure", "diabetes": "health condition", "280 pounds": "body weight",
         "my mother": "family member", "Maria": "person name", "$120": "amount of money",
         "14 Oak Street": "street address"}


def fake_finder(text, labels):
    """Stands in for the span model: marks known phrases with a label and offsets, as the real one does."""
    out = []
    for phrase, label in WORDS.items():
        at = text.find(phrase)
        if at >= 0 and label in labels:
            out.append({"text": phrase, "label": label, "score": 0.9, "start": at, "end": at + len(phrase)})
    return out


@pytest.fixture
def finder():
    return fake_finder
