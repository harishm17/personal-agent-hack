"""Persona identity check for the signer (sandbox only; labelled as sandbox everywhere).

Works without keys: with no PERSONA_API_KEY or PERSONA_TEMPLATE_ID, `start` and `status` answer
"identity not checked" and the signing flow carries on. The Inquiry is created and read from the backend only;
no verification data ever reaches a model."""
from __future__ import annotations

import threading

import httpx

from signoff import config

API = "https://api.withpersona.com/api/v1"
VERSION = "2025-10-27"
NOT_CHECKED = "identity not checked"
_lock = threading.Lock()
_record: dict = {}


def _headers() -> dict:
    return {"Authorization": "Bearer %s" % config.env("PERSONA_API_KEY"), "Content-Type": "application/json",
            "Persona-Version": VERSION}


def configured() -> bool:
    return config.have("PERSONA_API_KEY") and config.have("PERSONA_TEMPLATE_ID")


def reset() -> None:
    with _lock:
        _record.clear()


def record() -> dict:
    """What goes into the signature record and the screen's seal."""
    with _lock:
        if _record.get("inquiry_id"):
            return dict(_record)
    return {"inquiry_id": None, "status": "not_checked", "verified": False, "sandbox": True, "label": NOT_CHECKED,
            "configured": configured()}


def _apply(inquiry_id: str, status: str, detail: str | None = None) -> dict:
    verified = status in ("completed", "approved")
    label = {"approved": "identity checked (sandbox)", "completed": "identity checked (sandbox)",
             "pending": "identity check started (sandbox), not finished", "created": "identity check started (sandbox), not finished",
             "declined": "identity check declined (sandbox)", "failed": "identity check failed (sandbox)",
             "needs_review": "identity check needs review (sandbox)", "expired": "identity check expired (sandbox)"}.get(
        status, "identity check %s (sandbox)" % status)
    out = {"inquiry_id": inquiry_id, "status": status, "verified": verified, "sandbox": True, "label": label,
           "configured": True}
    if detail:
        out["detail"] = detail
    with _lock:
        _record.clear()
        _record.update(out)
    return out


def start(reference_id: str | None = None) -> dict:
    if not configured():
        return {**record(), "link": None, "reason": "PERSONA_API_KEY and PERSONA_TEMPLATE_ID are both needed"}
    body = {"data": {"attributes": {"inquiry-template-id": config.env("PERSONA_TEMPLATE_ID")}}}
    if reference_id:
        body["data"]["attributes"]["reference-id"] = reference_id
    try:
        response = httpx.post(API + "/inquiries", headers=_headers(), json=body, timeout=15)
        if response.status_code >= 400:
            return {**record(), "status": "error", "link": None, "label": "identity not checked (Persona refused: HTTP %d)" % response.status_code,
                    "detail": _first_error(response)}
        data = response.json()["data"]
        inquiry_id = data["id"]
        out = _apply(inquiry_id, data["attributes"].get("status", "created"))
        out["link"] = "https://inquiry.withpersona.com/verify?inquiry-id=%s" % inquiry_id
        return out
    except (httpx.HTTPError, KeyError, ValueError) as error:
        return {**record(), "status": "error", "link": None, "label": "identity not checked (Persona not reachable)",
                "detail": type(error).__name__}


def status() -> dict:
    current = record()
    inquiry_id = current.get("inquiry_id")
    if not inquiry_id or not configured():
        return current
    try:
        response = httpx.get("%s/inquiries/%s" % (API, inquiry_id), headers=_headers(), timeout=15)
        if response.status_code >= 400:
            return {**current, "detail": "Persona answered HTTP %d" % response.status_code}
        return _apply(inquiry_id, response.json()["data"]["attributes"]["status"])
    except (httpx.HTTPError, KeyError, ValueError) as error:
        return {**current, "detail": type(error).__name__}


def _first_error(response: httpx.Response) -> str:
    try:
        return str(response.json()["errors"][0].get("title", ""))[:120]
    except Exception:  # noqa: BLE001
        return ""
