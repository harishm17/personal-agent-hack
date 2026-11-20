"""Persona identity check for the signer (sandbox only; labelled as sandbox everywhere).

Works without keys: with no PERSONA_API_KEY or PERSONA_TEMPLATE_ID, `start` and `status` answer
"identity not checked" and the signing flow carries on. The Inquiry is created and read from the backend only;
no verification data ever reaches a model."""
from __future__ import annotations

import threading

import httpx

from signoff import config
from signoff.sign import audit

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
    link = _record.get("link") if _record.get("inquiry_id") == inquiry_id else None
    verified = status in ("completed", "approved")
    label = {"approved": "identity checked (sandbox)", "completed": "identity checked (sandbox)",
             "pending": "identity check started (sandbox), not finished", "created": "identity check started (sandbox), not finished",
             "declined": "identity check declined (sandbox)", "failed": "identity check failed (sandbox)",
             "needs_review": "identity check needs review (sandbox)", "expired": "identity check expired (sandbox)"}.get(
        status, "identity check %s (sandbox)" % status)
    out = {"inquiry_id": inquiry_id, "status": status, "verified": verified, "sandbox": True, "label": label,
           "configured": True}
    if link:
        out["link"] = link
    if detail:
        out["detail"] = detail
    with _lock:
        changed = _record.get("status") != status or _record.get("inquiry_id") != inquiry_id
        _record.clear()
        _record.update(out)
    if changed:  # one receipt for each new result Persona's backend gives us
        audit.receipt("persona_status", "persona", None, {"inquiry_id": inquiry_id, "status": status},
                      {"inquiry_id": inquiry_id, "status": status, "verified": verified, "sandbox": True})
    return out


def start(reference_id: str | None = None) -> dict:
    if not configured():
        return {**record(), "link": None, "reason": "PERSONA_API_KEY and PERSONA_TEMPLATE_ID are both needed"}
    body = {"data": {"attributes": {"inquiry-template-id": config.env("PERSONA_TEMPLATE_ID")}}}
    if reference_id:
        body["data"]["attributes"]["reference-id"] = reference_id
    audit.egress("persona", "create an identity inquiry for the signer (sandbox)", {"template": "set", "reference-id": reference_id or ""}, ["none"])
    try:
        response = httpx.post(API + "/inquiries", headers=_headers(), json=body, timeout=6)
        if response.status_code >= 400:
            return {**record(), "status": "error", "link": None, "label": "identity not checked (Persona refused: HTTP %d)" % response.status_code,
                    "detail": _first_error(response)}
        data = response.json()["data"]
        inquiry_id = data["id"]
        out = _apply(inquiry_id, data["attributes"].get("status", "created"))
        out["link"] = "https://inquiry.withpersona.com/verify?inquiry-id=%s" % inquiry_id
        with _lock:
            _record["link"] = out["link"]
        return out
    except (httpx.HTTPError, KeyError, ValueError) as error:
        return {**record(), "status": "error", "link": None, "label": "identity not checked (Persona not reachable)",
                "detail": type(error).__name__}


def status() -> dict:
    current = record()
    inquiry_id = current.get("inquiry_id")
    if not inquiry_id or not configured():
        return current
    audit.egress("persona", "read the status of the signer's inquiry (sandbox)", {"inquiry": inquiry_id}, ["none"])
    try:
        response = httpx.get("%s/inquiries/%s" % (API, inquiry_id), headers=_headers(), timeout=6)
        if response.status_code >= 400:
            return {**current, "detail": "Persona answered HTTP %d" % response.status_code}
        return _apply(inquiry_id, response.json()["data"]["attributes"]["status"])
    except (httpx.HTTPError, KeyError, ValueError) as error:
        return {**current, "detail": type(error).__name__}


def simulate(action: str) -> dict:
    """Sandbox rehearsal control: `approve` or `decline` the current inquiry through Persona's Simulate Actions
    (docs "Integration testing"), then read the status back from Persona. Sandbox only: it uses PERSONA_API_KEY,
    the sandbox key, and nothing else."""
    kind = {"approve": "approve_inquiry", "decline": "decline_inquiry"}.get(action)
    current = record()
    if kind is None or not current.get("inquiry_id") or not configured():
        return {**current, "simulated": False, "reason": "needs a started inquiry and action approve or decline"}
    audit.egress("persona", "sandbox rehearsal: %s the current inquiry" % action, {"inquiry": current["inquiry_id"], "action": kind}, ["none"])
    try:
        r = httpx.post("%s/inquiries/%s/perform-simulate-actions" % (API, current["inquiry_id"]), headers=_headers(),
                       json={"meta": {"simulate-actions": [{"type": kind}]}}, timeout=10)
        if r.status_code >= 400:
            return {**current, "simulated": False, "reason": "Persona answered HTTP %d" % r.status_code}
    except httpx.HTTPError as error:
        return {**current, "simulated": False, "reason": type(error).__name__}
    return {**status(), "simulated": True}


def _first_error(response: httpx.Response) -> str:
    try:
        return str(response.json()["errors"][0].get("title", ""))[:120]
    except Exception:  # noqa: BLE001
        return ""
