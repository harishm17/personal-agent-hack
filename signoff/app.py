"""The one server process. Integrator-owned: streams add routes in their own router module, never here.

Run: uv run uvicorn signoff.app:app --port 8800 --reload
"""
import importlib
import json
import pathlib

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

app = FastAPI(title="Sign-Off")

# Each stream owns one router module. A module that is missing or broken is skipped and reported at
# /api/health, so one stream's error never stops the others' pages from loading.
ROUTERS = ["signoff.engine.api", "signoff.store.api", "signoff.sign.api"]
OPTIONAL_ROUTERS = ["signoff.airbyte.api", "signoff.relay.api"]  # added tools: missing or broken never fails health
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
if (ROOT / "web" / "relay").is_dir():
    app.mount("/relay", StaticFiles(directory=ROOT / "web" / "relay", html=True), name="relay")


@app.middleware("http")
async def cache_header_for_profile(request, call_next):
    """Stores fetch the agent profile and need a Cache-Control header on it."""
    response = await call_next(request)
    if request.url.path.startswith("/profile/"):
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response
