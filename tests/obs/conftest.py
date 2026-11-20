import pytest


@pytest.fixture(autouse=True)
def _no_analytics_events(monkeypatch):
    monkeypatch.setenv("SIGNOFF_OBS", "off")
