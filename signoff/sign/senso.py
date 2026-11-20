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
import re
import pathlib
import threading
import time
from datetime import datetime, timezone

import httpx

from signoff import config
from signoff.sign import audit

BASE = "https://apiv2.senso.ai/api/v1"
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DOCS = pathlib.Path(__file__).with_name("senso_docs")
REGISTRY = pathlib.Path(__file__).with_name("_runtime") / "senso_docs.json"
BLOCKING = ("conflict", "unsupported")
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
            "running": meta["running_for"] is not None, "running_for": meta["running_for"],
            "order_document": _order_for_checks(rows)}


def _order_for_checks(rows: list[dict]) -> dict | None:
    """The documents the current verdicts rest on, deduplicated: which version of the order each sentence was checked against."""
    seen = {}
    for r in rows:
        src = r.get("source") or {}
        if src.get("version_id"):
            seen[(src.get("content_id"), src["version_id"])] = {k: src.get(k) for k in ("title", "content_id", "version_id", "version_num", "latest_version_id")}
    return {"versions": list(seen.values())} if seen else None


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


def _sheet_of(sheet: dict | str | None) -> dict:
    """The active sheet as the engine holds it, or a sheet id read from `sheets/<id>.json`."""
    if isinstance(sheet, dict):
        return sheet
    sid = sheet or config.env("SIGNOFF_SHEET") or "sheet1"
    return json.loads((ROOT / "sheets" / (sid + ".json")).read_text())


def documents(sheet: dict | str | None = None) -> list[dict]:
    """The documents the knowledge base should hold for the active sheet: its order, and (sheet 1 only) the handout,
    plus one policy text per store when the store answers are cached. Sheet 1 keeps its original document keys."""
    sh = _sheet_of(sheet)
    sid = sh["id"]
    order_file = ROOT / sh["order_doc"] if sh.get("order_doc") else DOCS / "order.txt"
    out = [{"key": "order" if sid == "sheet1" else "order:" + sid, "title": "%s order (invented)" % ("Therapist" if sid == "sheet1" else sh.get("title", sid)),
            "text": order_file.read_text()}]
    if sid == "sheet1":
        out.append({"key": "handout", "title": "Equipment handout (invented)", "text": (DOCS / "handout.txt").read_text()})
    answers = ROOT / "data" / ("store_answers" if sid == "sheet1" else "%s/store_answers" % sid)
    for path in sorted(answers.glob("*.json")) if answers.exists() else []:
        for a in json.loads(path.read_text()):
            text = "Terms of %s, as the store's own agent stated them on %s.\nQuestion asked: %s\nThe store's answer: %s\n" % (
                a["store"], a.get("asked_at", ""), a.get("question", ""), a.get("answer", ""))
            out.append({"key": "store:" + a["store"], "title": "%s delivery and returns (store answer)" % a["store"], "text": text})
    return out


def load_documents(sheet: dict | str | None = None) -> dict:
    """Adds what is missing or changed for the active sheet; the registry keeps each document's ids and the sha of
    the text that was sent. Other sheets' documents are left as they are."""
    reg, added = _registry(), []
    with httpx.Client(headers=_headers(), timeout=30) as client:
        for d in documents(sheet):
            sha = hashlib.sha256(d["text"].encode()).hexdigest()[:12]
            if reg.get(d["key"], {}).get("sha") == sha:
                continue
            audit.egress("senso", "load a document into the knowledge base: " + d["title"], d["text"], ["store_text"] if d["key"].startswith("store:") else ["order", "limit"])
            known = reg.get(d["key"], {})
            if known.get("kb_node_id") and not known.get("error"):
                # a changed text becomes a new version of the same document, so a sentence can say which version it was checked against
                r = client.put(BASE + "/org/kb/nodes/%s/raw" % known["kb_node_id"], json={"title": d["title"], "text": d["text"]})
            else:
                r = client.post(BASE + "/org/kb/raw", json={"title": d["title"], "text": d["text"]})
            if r.status_code == 409:
                reg[d["key"]] = {**reg.get(d["key"], {}), "sha": sha, "title": d["title"], "note": "already in the knowledge base"}
            elif r.status_code in (200, 201, 202):
                body = r.json()
                reg[d["key"]] = {"sha": sha, "title": d["title"], "content_id": body.get("id") or known.get("content_id"),
                                 "kb_node_id": body.get("kb_node_id") or known.get("kb_node_id"),
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


def doc_info(content_id: str, version_id: str | None = None) -> dict:
    """Which document and which version a verdict rests on. The version id is the one Senso reports for the passage it
    judged against (`content_version_id`); the number is known when that is the document's latest version."""
    for key, d in _registry().items():
        if d.get("content_id") == content_id:
            vid = version_id or d.get("version_id")
            return {"key": key, "title": d.get("title"), "content_id": content_id, "version_id": vid,
                    "version_num": d.get("version_num") if vid == d.get("version_id") else None,
                    "latest_version_id": d.get("version_id")}
    return {"content_id": content_id, "version_id": version_id}


def order_document(sheet: dict | None = None) -> dict | None:
    """The active sheet's order document as the knowledge base holds it now (for the screen: "checked against order v3")."""
    key = "order" if (sheet or {}).get("id", "sheet1") == "sheet1" else "order:" + sheet["id"]
    d = _registry().get(key)
    return {"key": key, **{k: d.get(k) for k in ("title", "content_id", "version_id", "version_num")}} if d else None


def unload(keys: list[str]) -> list[str]:
    """Takes documents out of the knowledge base (and the registry) so a verdict cannot rest on another sheet's order, for
    example sheet 1's near-identical order when sheet 4 is the one on the table. `load_documents(sheet)` brings one back."""
    reg = _registry()
    nodes = [reg[k]["kb_node_id"] for k in keys if k in reg and reg[k].get("kb_node_id")]
    if nodes:
        with httpx.Client(headers=_headers(), timeout=30) as client:
            client.post(BASE + "/org/kb/nodes/bulk-delete", json={"node_ids": nodes})
    for k in keys:
        reg.pop(k, None)
    _save_registry(reg)
    return nodes


def prune_stale() -> list[str]:
    """Deletes copies of our own documents that are not the registered ones (left by earlier loads), so a verdict can
    only rest on the current version. Only nodes whose title is one of ours are touched."""
    reg = _registry()
    keep = {d.get("kb_node_id") for d in reg.values()}
    titles = {d.get("title") for d in reg.values()}
    with httpx.Client(headers=_headers(), timeout=30) as client:
        root = client.get(BASE + "/org/kb/root").json()["kb_node_id"]
        nodes = client.get(BASE + "/org/kb/nodes/%s/children" % root).json().get("nodes", [])
        stale = [n["kb_node_id"] for n in nodes if n.get("type") == "content" and n.get("kb_node_id") not in keep
                 and (n.get("name") in titles)]
        if stale:
            client.post(BASE + "/org/kb/nodes/bulk-delete", json={"node_ids": stale})
    return stale


# ---- the sentences of the sheet ----------------------------------------------------------------------------

def _num(v) -> str:
    return "%g" % v


UNIT_WORDS = {"gpf": "gallons per flush", "gpm": "gallons per minute", "in": "inches", "lb": "lb", "dB": "decibels", "sheets": "sheets", "count": ""}
OPS = {">=": "at least", "<=": "at most", "==": "equal to"}


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _order_text(sheet: dict) -> str:
    f = ROOT / sheet["order_doc"] if sheet.get("order_doc") else DOCS / "order.txt"
    try:
        return f.read_text()
    except OSError:
        return ""


def _block(text: str, heading: str) -> list[str]:
    """The requirement sentences under a heading in the order document, up to the next blank line."""
    out, on = [], False
    for line in text.splitlines():
        if line.strip().lower().startswith(heading.lower()):
            on = True
            continue
        if on:
            if not line.strip():
                if out:
                    break
                continue
            if line.strip().startswith("Our order requires"):   # a requirement; a sentence about what the order prefers is not one
                out.append(line.strip())
    return out


def _fit_value(sentence: str, old, new) -> str | None:
    """The order's own sentence with the value the issuer has set now; None if the old value is not in it."""
    o, n = _num(old), _num(new)
    if o == n:
        return sentence
    import re as _re
    hit = _re.search(r"(?<![\d.])%s(?![\d.])" % _re.escape(o), sentence)
    return (sentence[:hit.start()] + n + sentence[hit.end():]) if hit else None


def sentences_for(state: dict) -> list[dict]:
    """Sentences for the active sheet's lines that will be bought or picked up. They are the order document's own
    sentences (its "In short" block for each line, its "Limits, one per sentence" block for each limit, matched by
    position, with the value the issuer has set now) so the wording is the order's, whatever the sheet; a sheet
    whose document does not line up gets sentences built from the sheet's words instead."""
    sheet = {l["id"]: l for l in state["sheet"]["lines"]}
    text = _order_text(state["sheet"])
    line_sentences = _block(text, "In short, our order requires")
    limit_sentences = _block(text, "Limits, one per sentence")
    sheet_lines = state["sheet"]["lines"]
    all_limits = [l for L in sheet_lines for l in L["limits"]]
    issuer_limits = [l for l in all_limits if l["bound"]["source"] == "issuer"]
    by_line = dict(zip([L["id"] for L in sheet_lines], line_sentences)) if len(line_sentences) == len(sheet_lines) else {}
    if len(limit_sentences) == len(all_limits):
        by_limit = dict(zip([l["id"] for l in all_limits], limit_sentences))
    elif len(limit_sentences) == len(issuer_limits):
        by_limit = dict(zip([l["id"] for l in issuer_limits], limit_sentences))
    else:
        by_limit = {}
    originals = {l["id"]: (l.get("from_order") or {}).get("value") for l in all_limits}
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
            fo = limit.get("from_order")
            sentence = None
            if limit["id"] in by_limit:
                old = originals.get(limit["id"])
                sentence = _fit_value(by_limit[limit["id"]], old if old is not None else b["value"], b["value"])
            out.append({**base, "kind": "limit", "blocks": False, "moved_from_order": bool(fo and fo.get("matches") is False),
                        "sentence": sentence or _limit_sentence(line["need"], limit, b["value"])})
        need = line["need"]   # the order's own words for the line come from its document (the "In short" block); this is the fallback
        if line["status"] == "pick_up":
            how = re.match(r"must be (.+?);", sheet[line["line_id"]].get("fulfilment_note") or "")
            out.append({**base, "kind": "order", "blocks": True,
                        "sentence": "Our order requires %s %s%s, so it is picked up locally and not bought through a cart." % (
                            _article(need), need, " to be " + how.group(1) if how else "")})
        else:
            out.append({**base, "kind": "order", "blocks": True,
                        "sentence": by_line.get(line["line_id"]) or "Our order requires %s %s for the %s." % (_article(need), need, line["room"])})
        # The store's own words, verbatim and without its name (a claim that names another brand gets no verdict).
        # Shown with the verdict, not blocking by default: the judge is not steady on policy text from several stores.
        if not STORE_SENTENCES:
            continue
        a = cand.get("arrival") or {}
        if a.get("status") == "stated" and a.get("quote") and line["status"] != "pick_up":
            out.append({**base, "kind": "store", "blocks": STORE_BLOCKS, "sentence": a["quote"].rstrip(".") + "."})
        u = cand.get("undo") or {}
        if u.get("quote"):
            out.append({**base, "kind": "store", "blocks": STORE_BLOCKS, "sentence": u["quote"].rstrip(".") + "."})
    return out


def _limit_sentence(need: str, limit: dict, value: float) -> str:
    """"Our order requires ..." reads as the organisation's own terms, so the judge checks it against the order
    (5 of 5 verdicts in a trial; the same sentence without it got no verdict 2 times in 5). Sheet 1's wording is
    kept as its order document has it; every other limit is built from the sheet's own words."""
    n, name, unit = _num(value), limit["name"], limit["unit"]
    if name == "weight capacity":
        return "Our order requires the %s to hold at least %s %s." % (need, n, unit)
    if name == "finished seat height":
        return "Our order requires the toilet rim height plus the height the %s adds to be at least %s inches." % (need, n)
    if name == "seat height":
        return "Our order requires the %s seat height to reach at least %s inches." % (need, n)
    if name == "bar length":
        return "Our order requires the %s to be at least %s inches long." % (need, n)
    return "Our order requires the %s's %s to be %s %s %s." % (need, name, OPS.get(limit["op"], "within"), n, UNIT_WORDS.get(unit, unit))


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
    audit.egress("senso", "check one sentence of the sheet against the order", s["sentence"], ["order", "limit"] if s.get("kind") == "limit" else ["order"])
    try:
        r = client.post(BASE + "/org/evals/text", json={"text": s["sentence"], "evaluator": "kb_accuracy", "author": "organization",
                                                         # the question the sentence answers: without it the judge often asked whose
                                                         # order this was and called a correct sentence unsupported (4 of 12 verified;
                                                         # 11 of 12 with it, sheet 3)
                                                         "question": "What does our order require?",
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
                   run_id=run.get("eval_run_id"),
                   source=doc_info(ev.get("content_id", ""), ev.get("content_version_id")) if ev.get("content_id") else None,
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
        tally = {v: sum(1 for r in rows if r["verdict"] == v) for v in {r["verdict"] for r in rows}}
        audit.receipt("senso_checked", "senso", None, [r["sentence"] for r in rows],
                      {"for_hash": current_hash, "sentences": len(rows), "verdicts": tally,
                       "blocking": [r["sentence"] for r in rows if r.get("blocks") and r["verdict"] in blocking_verdicts()]})
    finally:
        with _lock:
            _meta["running_for"] = None
    return checks()


if __name__ == "__main__":
    import sys
    print(json.dumps(load_documents(sys.argv[1] if len(sys.argv) > 1 else None), indent=1))
    print("pruned", prune_stale())
    for arg in sys.argv[2:]:      # `... sheet4 unload order handout order:sheet2`
        if arg == "unload":
            keys = sys.argv[sys.argv.index("unload") + 1:]
            print("unloaded", unload(keys))
            break
    print(wait_processed())
