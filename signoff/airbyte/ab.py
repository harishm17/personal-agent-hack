"""Thin client for the local Airbyte public API. Values come from config.env; none is printed."""
import time

import httpx

from signoff import config

BASE = (config.env("AIRBYTE_URL") or "http://localhost:8900").rstrip("/")
_token = {"value": None, "at": 0.0}


def token() -> str:
    if _token["value"] and time.time() - _token["at"] < 120:
        return _token["value"]
    r = httpx.post(f"{BASE}/api/public/v1/applications/token", timeout=20,
                   json={"client_id": config.env("AIRBYTE_CLIENT_ID"), "client_secret": config.env("AIRBYTE_CLIENT_SECRET")})
    r.raise_for_status()
    _token.update(value=r.json()["access_token"], at=time.time())
    return _token["value"]


def call(method: str, path: str, body: dict | None = None, timeout: int = 60):
    r = httpx.request(method, f"{BASE}/api/public/v1{path}", json=body, timeout=timeout,
                      headers={"Authorization": f"Bearer {token()}"})
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
    return r.json() if r.content else {}
