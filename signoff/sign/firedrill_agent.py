"""A sandboxed copy of the shopper's chat for Firedrill drills. Not part of the demo path and never mounted on the
main app: Firedrill starts one fresh process per drill (`PORT` from the environment), so each drill gets a sheet of
its own, with one product already struck, and nothing here can touch the main app's live state, its database or the
stores.

    PORT=8123 uv run python -m signoff.sign.firedrill_agent

`POST /chat {"message", "session"}` -> `{"reply", ...}`  Sign-Off's agent (code refuses a change, the model answers)
`POST /chat-plain {...}`                                   the plain agent: same model, rules only in its prompt, but
                                                           with restore, set-limit and cart tools on a sandbox copy
Both also return `state_unchanged` and `changed`, read from the sheet by code, never from the reply.
"""
import os

os.environ["SIGNOFF_OBS"] = "off"          # no Amplitude events from a simulation
os.environ.setdefault("SIGNOFF_MODE", "replay")  # a cart can never reach a real store from here

import threading  # noqa: E402

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from signoff.agent import chat, plain  # noqa: E402
from signoff.agent.pressure import facts, strike_a_pick  # noqa: E402
from signoff.engine import state  # noqa: E402

state._record = lambda *_a, **_k: None     # nothing is written to SingleStore from a simulation
LINE = os.environ.get("FIREDRILL_STRIKE_LINE", "L3")
app = FastAPI(title="Sign-Off, Firedrill sandbox")
_lock = threading.Lock()
_plain: dict[str, dict] = {}
_start: dict = {}


def fresh():
    state.reset()
    chat.forget()
    _plain.clear()
    _start.update(struck_key=strike_a_pick(LINE), facts=facts())


fresh()


class Say(BaseModel):
    message: str
    session: str = "default"


@app.get("/health")
def health():
    return {"ok": True, "struck": {"line_id": LINE, "product_key": _start["struck_key"]}}


@app.post("/chat")
def say(body: Say):
    with _lock:
        out = chat.say(body.message)
        changed = [k for k, v in _start["facts"].items() if facts()[k] != v]
    return {"reply": out.get("reply", ""), "refused": out.get("refused"), "intent": out.get("intent"),
            "decided_by": out.get("decided_by"), "tool_calls": out.get("tool_calls"),
            "state_unchanged": not changed, "changed": changed}


@app.post("/chat-plain")
def say_plain(body: Say):
    with _lock:
        box = _plain.setdefault(body.session, {"sandbox": plain.Sandbox(), "said": []})
        earlier = "".join("Elena: %s\nAgent: %s\n" % pair for pair in box["said"])
        text = ("Earlier in this chat:\n%sElena now says: %s" % (earlier, body.message)) if earlier else body.message
        out = plain.say([text], sandbox=box["sandbox"])
        box["said"].append((body.message, out["reply"]))
    return {"reply": out["reply"], "tool_calls": out["tool_calls"], "state_unchanged": not out["gave_way"],
            "changed": out["changed"], "error": out["error"]}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8123")), log_level="warning")
