"""Senso: the therapist's order, a handout and each store's policy text live in a knowledge base; every sentence
of the sheet is judged against them with `POST /org/evals/text` (evaluator kb_accuracy). `conflict` or
`unsupported` on a blocking sentence stops `sign_sheet`.

What the first calls showed (11:30): a claim that names another brand gets no verdict (about_brand false, bucket
"general"); a statement of terms ("must hold at least 300 lb", "opened bath seats cannot be returned") is judged
against the knowledge base with author "organization". So sentences here are written as terms, not as claims
about a named brand. Without SENSO_API_KEY nothing is called and the answer says "not connected".

Sentence kinds: `store` and `order` block on conflict or unsupported; `limit` (an issuer value set away from
the order) is shown with its verdict but does not block, because moving a limit is the issuer's job."""
from __future__ import annotations

import concurrent.futures as futures
import hashlib
import json
import pathlib
import threading
import time
from datetime import datetime, timezone

import httpx

from signoff import config

BASE = "https://apiv2.senso.ai/api/v1"
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DOCS = pathlib.Path(__file__).with_name("senso_docs")
REGISTRY = pathlib.Path(__file__).with_name("_runtime") / "senso_docs.json"
BLOCKING = ("conflict", "unsupported")
ORDER_NAME = {"shower chair": "shower chair or transfer bench"}  # the order's own words for a line
STORE_SENTENCES = config.env("SENSO_STORE_SENTENCES") == "1"  # off: a quote naming no brand got "unsupported" every time
STORE_BLOCKS = config.env("SENSO_BLOCK_STORE") == "1"
_lock = threading.RLock()
_checks: list[dict] = []
_meta: dict = {"for_hash": None, "ran_at": None, "error": None, "running_for": None}
_kick = threading.Event()  # set: start the next run now, without the debounce


def blocking_verdicts() -> tuple:
    """`conflict` and `unsupported` stop a signature (after up to three tries on `unsupported`, see `judge`).
    SENSO_BLOCK_UNSUPPORTED=0 relaxes it to `conflict` only, as a switch for the day if the judge turns flaky."""
    return ("conflict",) if config.env("SENSO_BLOCK_UNSUPPORTED") == "0" else BLOCKING


def configured() -> bool:
    return config.have("SENSO_API_KEY")


def _headers() -> dict:
    return {"X-API-Key": config.env("SENSO_API_KEY"), "Content-Type": "application/json"}


def reset() -> None:
    with _lock:
        _checks.clear()
        _meta.update(for_hash=None, ran_at=None, error=None)
    _kick.set()  # a reset starts a fresh run in the background


def set_checks(checks: list[dict], for_hash: str | None = None) -> None:
    with _lock:
        _checks[:] = checks
        _meta.update(for_hash=for_hash, ran_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), error=None)


def checks() -> dict:
    with _lock:
        rows, meta = list(_checks), dict(_meta)
    return {"configured": configured(), "label": None if configured() else "Senso not connected: no verdicts yet",
            "checks": rows, "blocking": [c for c in rows if c.get("blocks") and c.get("verdict") in blocking_verdicts()],
            "blocks_on": list(blocking_verdicts()),
            "for_hash": meta["for_hash"], "ran_at": meta["ran_at"], "error": meta["error"],
            "running": meta["running_for"] is not None, "running_for": meta["running_for"]}


def running_for() -> str | None:
    with _lock:
        return _meta["running_for"]


def kick() -> None:
    """Ask for a run now (the Sign view opened, or a reset); the background watcher starts it, never a request."""
    _kick.set()


def kicked() -> bool:
    return _kick.is_set()


def blocking() -> list[dict]:
    return checks()["blocking"]


# ---- documents ----------------------------------------------------------------------------------------

def _registry() -> dict:
    try:
        return json.loads(REGISTRY.read_text())
    except (OSError, ValueError):
        return {}


def _save_registry(reg: dict) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=1))


def documents() -> list[dict]:
    """Every document the knowledge base should hold: the order, the handout, one policy text per store."""
    out = [{"key": "order", "title": "Therapist order (invented)", "text": (DOCS / "order.txt").read_text()},
           {"key": "handout", "title": "Equipment handout (invented)", "text": (DOCS / "handout.txt").read_text()}]
    answers = ROOT / "data" / "store_answers"
    for path in sorted(answers.glob("*.json")) if answers.exists() else []:
        for a in json.loads(path.read_text()):
            text = "Terms of %s, as the store's own agent stated them on %s.\nQuestion asked: %s\nThe store's answer: %s\n" % (
                a["store"], a.get("asked_at", ""), a.get("question", ""), a.get("answer", ""))
            out.append({"key": "store:" + a["store"], "title": "%s delivery and returns (store answer)" % a["store"], "text": text})
    return out


def load_documents() -> dict:
    """Adds what is missing or changed (a changed text becomes a new version under a new title suffix); the
    registry keeps each document's ids and the sha of the text that was sent."""
    reg, added = _registry(), []
    with httpx.Client(headers=_headers(), timeout=30) as client:
        for d in documents():
            sha = hashlib.sha256(d["text"].encode()).hexdigest()[:12]
            if reg.get(d["key"], {}).get("sha") == sha:
                continue
            r = client.post(BASE + "/org/kb/raw", json={"title": d["title"], "text": d["text"]})
            if r.status_code == 409:
                reg[d["key"]] = {**reg.get(d["key"], {}), "sha": sha, "title": d["title"], "note": "already in the knowledge base"}
            elif r.status_code in (200, 201, 202):
                body = r.json()
                reg[d["key"]] = {"sha": sha, "title": d["title"], "content_id": body.get("id"), "kb_node_id": body.get("kb_node_id"),
                                 "version_id": body.get("latest_content_version_id"), "version_num": body.get("version_num")}
                added.append(d["key"])
            else:
                reg[d["key"]] = {**reg.get(d["key"], {}), "error": "HTTP %d" % r.status_code}
    _save_registry(reg)
    return {"added": added, "documents": reg}


def wait_processed(timeout: float = 90.0) -> dict:
    """Polls every registered node until Senso reports it processed."""
    reg, deadline, status = _registry(), time.time() + timeout, {}
    with httpx.Client(headers=_headers(), timeout=30) as client:
        while True:
            for key, d in reg.items():
                if d.get("kb_node_id") and status.get(key) != "complete":
                    r = client.get(BASE + "/org/kb/nodes/" + d["kb_node_id"])
                    status[key] = (r.json().get("content") or {}).get("processing_status") if r.status_code == 200 else "error"
            if all(v == "complete" for v in status.values()) or time.time() > deadline:
                return status
            time.sleep(3)


def doc_info(content_id: str) -> dict:
    for key, d in _registry().items():
        if d.get("content_id") == content_id:
            return {"key": key, "title": d.get("title"), "content_id": content_id, "version_id": d.get("version_id")}
    return {"content_id": content_id}


# ---- the sentences of the sheet ----------------------------------------------------------------------------

def _num(v) -> str:
    return "%g" % v


def sentences_for(state: dict) -> list[dict]:
    """Sentences for the lines that will be bought or picked up. Written as terms (see the module note)."""
    sheet = {l["id"]: l for l in state["sheet"]["lines"]}
    order_values = _order_values()
    out = []
    for line in state["lines"]:
        if line["status"] not in ("ready", "next_candidate", "pick_up") or not line.get("pick"):
            continue
        cand = next(c for c in line["candidates"] if c["id"] == line["pick"])
        base = {"line_id": line["line_id"], "candidate_id": cand["id"], "store": cand["product"]["store"],
                "product_id": cand["product"]["product_id"]}
        for limit in sheet[line["line_id"]]["limits"]:
            b = limit["bound"]
            if b["source"] != "issuer":
                continue
            sentence = _limit_sentence(line["need"], limit, b["value"])
            moved = order_values.get(limit["id"]) is not None and order_values[limit["id"]] != b["value"]
            out.append({**base, "kind": "limit", "blocks": False, "moved_from_order": moved,
                        "sentence": sentence})
        if line["status"] == "pick_up":
            out.append({**base, "kind": "order", "blocks": True,
                        "sentence": "Our order requires a %s to be screw-mounted and fitted, so it is picked up locally and not bought through a cart." % line["need"]})
        else:
            out.append({**base, "kind": "order", "blocks": True,
                        "sentence": "Our order requires a %s for the %s." % (ORDER_NAME.get(line["need"], line["need"]), line["room"])})
        # The store's own words, verbatim and without its name (a claim that names another brand gets no verdict).
        # Shown with the verdict, not blocking by default: the judge is not steady on policy text from three stores.
        if not STORE_SENTENCES:
            continue
        a = cand.get("arrival") or {}
        if a.get("status") == "stated" and a.get("quote") and line["status"] != "pick_up":
            out.append({**base, "kind": "store", "blocks": STORE_BLOCKS, "sentence": a["quote"].rstrip(".") + "."})
        u = cand.get("undo") or {}
        if u.get("quote"):
            out.append({**base, "kind": "store", "blocks": STORE_BLOCKS, "sentence": u["quote"].rstrip(".") + "."})
    return out


def _order_values() -> dict:
    """What the order file says for each issuer limit, so a moved limit is labelled as moved."""
    return {"L1.capacity": 300, "L2.capacity": 300, "L3.capacity": 300, "L4.capacity": 300, "L5.capacity": 300,
            "L6.capacity": 300, "L2.height": 19.0, "L3.seat": 19.0, "L5.length": 16.0}


def _limit_sentence(need: str, limit: dict, value: float) -> str:
    """"Our order requires ..." reads as the organisation's own terms, so the judge checks it against the order
    (5 of 5 verdicts in a trial; the same sentence without it got no verdict 2 times in 5)."""
    n = _num(value)
    if limit["name"] == "weight capacity":
        return "Our order requires the %s to hold at least %s %s." % (need, n, limit["unit"])
    if limit["name"] == "finished seat height":
        return "Our order requires the toilet rim height plus the height the %s adds to be at least %s inches." % (need, n)
    if limit["name"] == "seat height":
        return "Our order requires the %s seat height to reach at least %s inches." % (need, n)
    if limit["name"] == "bar length":
        return "Our order requires the %s to be at least %s inches long." % (need, n)
    return "Our order requires the %s %s %s %s %s." % (need, limit["label"], "at least" if limit["op"] == ">=" else "at most", n, limit["unit"])


# ---- judging --------------------------------------------------------------------------------------------

def judge(client: httpx.Client, s: dict) -> dict:
    """A sentence that must be backed (`blocks`) gets up to two more tries when the first answer is "unsupported" or
    has no verdict: a miss by the judge should not stop a signature, a `conflict` is never retried away."""
    row = _judge_once(client, s)
    tries = 1
    while s.get("blocks") and row["verdict"] in ("unsupported", "not_verifiable") and tries < 3:
        tries += 1
        again = _judge_once(client, s)
        if again["verdict"] in ("verified", "conflict"):
            row = again
            break
    row["tries"] = tries
    if row["verdict"] == "not_verifiable" and s.get("blocks"):
        row["verdict"] = "unsupported"  # nothing in the knowledge base backs it
    return row


def _judge_once(client: httpx.Client, s: dict) -> dict:
    row = {k: s.get(k) for k in ("kind", "blocks", "sentence", "line_id", "candidate_id", "store", "product_id", "moved_from_order")}
    try:
        r = client.post(BASE + "/org/evals/text", json={"text": s["sentence"], "evaluator": "kb_accuracy", "author": "organization",
                                                         "wait": True, "label": "signoff-" + (s.get("line_id") or "sheet")})
        if r.status_code >= 400:
            return {**row, "verdict": "error", "reasoning": "Senso answered HTTP %d" % r.status_code}
        run = r.json()
        deadline = time.time() + 75
        while run.get("status") in ("queued", "running", "pending") and run.get("eval_run_id") and time.time() < deadline:
            time.sleep(2)  # wait:true gave up under load; the run keeps going
            polled = client.get(BASE + "/org/evals/runs/" + run["eval_run_id"])
            if polled.status_code == 200:
                run = polled.json()
        if run.get("status") != "completed":
            return {**row, "verdict": "error", "reasoning": "run %s" % run.get("status")}
        claims = run.get("claims") or []
        scored = [c for c in claims if c.get("verdict")]
        pick = next((c for c in scored if c["verdict"] in BLOCKING), scored[0] if scored else (claims[0] if claims else {}))
        verdict = pick.get("verdict") or "not_verifiable"
        ev = (pick.get("evidence") or [{}])[0]
        row.update(verdict=verdict, quote=pick.get("quote"), reasoning=pick.get("reasoning"), claim=pick.get("claim_text"),
                   run_id=run.get("eval_run_id"), source=doc_info(ev.get("content_id", "")) if ev.get("content_id") else None,
                   chunk_index=ev.get("chunk_index"), claims_total=len(claims))
    except httpx.HTTPError as error:
        row.update(verdict="error", reasoning=type(error).__name__)
    return row


def run_checks(state: dict, current_hash: str | None = None) -> dict:
    """Judges every sentence (a few in parallel) and keeps the rows for `GET /api/senso/checks`."""
    if not configured():
        return checks()
    _kick.clear()
    with _lock:
        _meta["running_for"] = current_hash or "?"
    try:
        sentences = sentences_for(state)
        with httpx.Client(headers=_headers(), timeout=120) as client, futures.ThreadPoolExecutor(6) as pool:
            rows = list(pool.map(lambda s: judge(client, s), sentences))
        set_checks(rows, current_hash)
    finally:
        with _lock:
            _meta["running_for"] = None
    return checks()


if __name__ == "__main__":
    print(json.dumps(load_documents(), indent=1))
    print(wait_processed())
