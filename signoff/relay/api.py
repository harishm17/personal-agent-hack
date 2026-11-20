"""Optional router: /api/issuer/relay/{start,complete,status}. The product never depends on it."""
from fastapi import APIRouter

from signoff.relay import core

router = APIRouter()


@router.post("/api/issuer/relay/start")
def start():
    return core.start()


@router.post("/api/issuer/relay/complete")
def complete():
    return core.complete()


@router.get("/api/issuer/relay/status")
def status():
    return {"sandbox": True, "claim_type": core.CLAIM_TYPE, **core.session_state()}
