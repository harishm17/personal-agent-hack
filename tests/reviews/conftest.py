import pytest


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """No analytics, a ledger and a cache folder of the test's own; replay mode, so nothing can reach the web."""
    from signoff.obs import _egress_module as ledger
    from signoff.reviews import reviews
    monkeypatch.setenv("SIGNOFF_OBS", "off")
    monkeypatch.setenv("SIGNOFF_MODE", "replay")
    monkeypatch.setattr(ledger, "LEDGER", tmp_path / "ledger.jsonl")
    ledger.reset_for_tests()
    monkeypatch.setattr(reviews, "DIR", tmp_path / "reviews")
    monkeypatch.setattr(reviews, "SPACING_SECONDS", 0.0)
