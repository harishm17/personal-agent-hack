"""Development server for the phone on port 8004 with the stand-in engine and stores:

    uv run python -m tests.sign.devserver

Serves /phone/, /handcheck/, the SIGN routes and a minimal /api/state, /api/events, /api/sheet/canonical built
on the stand-in. The real engine replaces the stand-in once ENGINE is merged (run the main app on 8800)."""
import asyncio
import json

import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from signoff.sign import api

from .standin import ROOT, FakeCart, FakeEngine

engine, cart = FakeEngine(), FakeCart()
api.get_engine = lambda: engine
api.get_cart = lambda: cart
app = FastAPI()
app.include_router(api.router)


@app.get("/api/state")
def state():
    return engine.get_state()


@app.get("/api/sheet/canonical")
def canonical():
    return {"canonical": engine.canonical_sheet(), "sheet_hash": engine.sheet_hash()}


@app.get("/api/events")
async def events():
    async def gen():
        last = None
        while True:
            version = engine.state["version"]
            if version != last:
                last = version
                yield "data: %s\n\n" % json.dumps({"type": "state", "version": version})
            await asyncio.sleep(0.3)
    return StreamingResponse(gen(), media_type="text/event-stream")


app.mount("/phone", StaticFiles(directory=ROOT / "web" / "phone", html=True), name="phone")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8004, log_level="warning")
