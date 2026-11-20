from fastapi.testclient import TestClient

from signoff.app import app


def test_health_and_fixture_state():
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    state = client.get("/api/state").json()
    assert len(state["lines"]) == 6
    assert client.get("/").status_code == 200
    assert client.get("/phone/").status_code == 200
    assert client.get("/profile/agent-v1.json").headers["cache-control"] == "public, max-age=3600"
