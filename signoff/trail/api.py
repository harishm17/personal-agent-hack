"""Optional router: GET /api/trail, the run as ordered events merged from the records that already exist.
Read-only. The product never depends on it."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from signoff.trail import feed

router = APIRouter()


@router.get("/api/trail")
def trail():
    try:
        body = feed.build(feed.collect())
    except Exception as error:  # noqa: BLE001
        body = feed.build({"sources": [{"id": "feed", "ok": False, "note": type(error).__name__}]})
    return JSONResponse(body, headers={"Cache-Control": "no-store"})
