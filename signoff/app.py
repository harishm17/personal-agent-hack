"""The one server process. Integrator-owned: streams add routes in their own router module, never here.

Run: uv run uvicorn signoff.app:app --port 8800 --reload
"""
import importlib
import os
import json
import pathlib
import secrets

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

app = FastAPI(title="Sign-Off")

# Routes that reset the app, switch the reader, reload data or act as the shopper are for the laptop only.
# A request that arrived through the public tunnel must carry X-Admin-Token (SIGNOFF_ADMIN_TOKEN in the
# keys file). The approver's own routes (/api/issuer/...) are protected by her key, not by this.
LOCAL_ONLY = ("/api/admin/", "/api/gate/override", "/api/airbyte/sync", "/api/senso/load",
              "/api/handcheck/save", "/api/drill/", "/api/shopper/")


def _came_through_tunnel(request) -> bool:
    h = request.headers
    if h.get("cf-connecting-ip") or h.get("cf-ray") or h.get("x-forwarded-for"):
        return True
    host = request.client.host if request.client else ""
    return host not in ("127.0.0.1", "::1", "localhost", "testclient")


@app.middleware("http")
async def admin_guard(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith(LOCAL_ONLY):
        if _came_through_tunnel(request):
            token = os.environ.get("SIGNOFF_ADMIN_TOKEN") or ""
            given = request.headers.get("x-admin-token") or ""
            if not (token and given and secrets.compare_digest(given, token)):
                return JSONResponse({"error": "local_only", "detail": "This route is for the laptop running "
                                     "the app, or needs X-Admin-Token."}, status_code=403)
    return await call_next(request)

# Each stream owns one router module. A module that is missing or broken is skipped and reported at
# /api/health, so one stream's error never stops the others' pages from loading.
ROUTERS = ["signoff.engine.api", "signoff.store.api", "signoff.sign.api"]
OPTIONAL_ROUTERS = ["signoff.airbyte.api", "signoff.relay.api", "signoff.trail.api", "signoff.memory.api"]  # added tools: missing or broken never fails health
LOADED, FAILED = [], {}
for name in ROUTERS:
    try:
        app.include_router(importlib.import_module(name).router)
        LOADED.append(name)
    except Exception as error:  # noqa: BLE001
        FAILED[name] = repr(error)[:300]
SKIPPED = {}
for name in OPTIONAL_ROUTERS:
    try:
        app.include_router(importlib.import_module(name).router)
        LOADED.append(name)
    except Exception as error:  # noqa: BLE001
        SKIPPED[name] = repr(error)[:300]


@app.get("/api/health")
def health():
    return {"ok": not FAILED, "routers": LOADED, "failed": FAILED, "skipped": SKIPPED}


if "signoff.engine.api" not in LOADED:
    @app.get("/api/state")
    def fixture_state():
        """Until the engine router exists, the screen draws the committed fixture run."""
        return JSONResponse(json.loads((ROOT / "fixtures" / "state.json").read_text()))


@app.get("/")
def screen():
    return FileResponse(ROOT / "web" / "screen" / "index.html")


@app.get("/phone")
def phone():
    return RedirectResponse("/phone/")


app.mount("/phone", StaticFiles(directory=ROOT / "web" / "phone", html=True), name="phone")
app.mount("/screen", StaticFiles(directory=ROOT / "web" / "screen", html=True), name="screen")
app.mount("/profile", StaticFiles(directory=ROOT / "profile"), name="profile")
if (ROOT / "web" / "trail").is_dir():
    app.mount("/trail", StaticFiles(directory=ROOT / "web" / "trail", html=True), name="trail")
if (ROOT / "web" / "relay").is_dir():
    app.mount("/relay", StaticFiles(directory=ROOT / "web" / "relay", html=True), name="relay")


@app.middleware("http")
async def cache_header_for_profile(request, call_next):
    """Stores fetch the agent profile and need a Cache-Control header on it."""
    response = await call_next(request)
    if request.url.path.startswith("/profile/"):
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response
