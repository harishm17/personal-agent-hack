import asyncio

from signoff.obs import tools


def test_a_row_has_the_agreed_keys_and_a_short_job():
    r = tools._row("X", "Four word job here", 3, "things", "detail.", "/api/x", True, "live")
    assert set(r) == {"tool", "job", "number", "unit", "detail", "source", "ok", "basis"} and r["ok"] is True
    try:
        tools._row("X", "this job has far too many words", 1, "u", "d", "s", True, "b")
    except AssertionError:
        pass
    else:
        raise AssertionError("a job of more than five words was accepted")


def test_firedrill_numbers_come_from_the_saved_reports():
    fd = tools._firedrill()
    assert fd and all(len(c["id"]) == 36 for c in fd["campaigns"])
    assert any("Holds the sheet" in c["scores"] or "Names who can make the change" in c["scores"] for c in fd["campaigns"])


def test_a_tool_without_a_real_call_is_absent_not_invented(monkeypatch):
    async def fake_get(app, path):
        if path == "/api/state":
            return {"sheet": {"id": "s"}, "version": 1, "lines": [{"line_id": "L1", "candidates": [], "need": "n"}], "readers": {"readers": []}, "two_readers": {}}
        return None
    monkeypatch.setattr(tools, "_get", fake_get)
    monkeypatch.setattr(tools, "_sql_parts", lambda line_id: {"singlestore_error": "down", "airbyte_error": "down"})
    monkeypatch.setattr(tools.obs, "stats", {"delivered": 0})
    monkeypatch.setattr(tools, "_firedrill", lambda: None)
    out = asyncio.run(tools.build(object()))
    assert out["tools"] == [] and {a["tool"] for a in out["absent"]} >= {"SingleStore", "Airbyte", "Statsig", "Amplitude", "Senso", "Persona", "Cognee"}
