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


def test_laptop_only_routes_refuse_requests_from_the_tunnel(monkeypatch):
    monkeypatch.setenv("SIGNOFF_ADMIN_TOKEN", "test-token")
    client = TestClient(app)
    tunnel = {"cf-connecting-ip": "203.0.113.9"}
    for path in ("/api/admin/reset", "/api/gate/override", "/api/admin/refresh-pool", "/api/shopper/fact"):
        r = client.post(path, json={}, headers=tunnel)
        assert r.status_code == 403 and r.json()["error"] == "local_only", path
        r = client.post(path, json={}, headers={**tunnel, "x-admin-token": "wrong"})
        assert r.status_code == 403, path
    assert client.get("/api/state", headers=tunnel).status_code == 200
    # the approver's routes are not behind this guard: her key protects them
    assert client.post("/api/issuer/request", json={}, headers=tunnel).status_code != 403 or \
        client.post("/api/issuer/request", json={}, headers=tunnel).json().get("error") != "local_only"
