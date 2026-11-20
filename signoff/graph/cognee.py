"""Cognee, the graph memory: one dataset per owner, written with that owner's own identity.

The identities are Cognee agent users made by the account that holds the key: one for the issuer, one for the
shopper. The account itself ("system") writes what the stores state. An owner's agent has write permission
on its own dataset only, so a write to the issuer's dataset with the shopper's key is refused by Cognee, and
every attempt (accepted or refused) is appended to data/graph/cognee_log.jsonl.

Secrets: the agents' keys live in data/graph/private/ (ignored by git) and are never printed or logged.
"""
import datetime
import json
import pathlib
import time

import httpx

from signoff import config

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "graph"
FACTS = DATA / "cognee.json"            # dataset ids, agent ids, timings: no secrets, committed
LOG = DATA / "cognee_log.jsonl"         # every write attempt and its outcome
KEYS = DATA / "private" / "identities.json"
PREFIX = "signoff"


class CogneeError(Exception):
    pass


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def facts() -> dict:
    return json.loads(FACTS.read_text()) if FACTS.exists() else {}


def _save_facts(update: dict) -> dict:
    held = facts()
    held.update(update)
    DATA.mkdir(parents=True, exist_ok=True)
    FACTS.write_text(json.dumps(held, indent=1, sort_keys=True) + "\n")
    return held


def _keys() -> dict:
    return json.loads(KEYS.read_text()) if KEYS.exists() else {}


def log(entry: dict) -> dict:
    entry = dict(at=_now(), **entry)
    DATA.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def read_log() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(line) for line in LOG.read_text().splitlines() if line.strip()]


def configured() -> bool:
    return all(config.have(n) for n in ("COGNEE_API_URL", "COGNEE_API_KEY", "COGNEE_TENANT_ID"))


def client(identity: str = "system", timeout: float = 60) -> httpx.Client:
    """`identity` is "system" (the account's key) or an owner whose agent key was made by `setup`."""
    if not configured():
        raise CogneeError("no Cognee key in the keys file")
    if identity == "system":
        key = config.env("COGNEE_API_KEY")
    else:
        key = (_keys().get(identity) or {}).get("key")
        if not key:
            raise CogneeError(f"no Cognee identity for {identity}: run setup")
    return httpx.Client(base_url=config.env("COGNEE_API_URL").rstrip("/"), timeout=timeout,
                        headers={"X-Api-Key": key, "X-Tenant-Id": config.env("COGNEE_TENANT_ID")})


def dataset_name(owner: str) -> str:
    """issuer -> signoff-issuer; a store's domain -> signoff-store-carex-com; system (what the product itself
    worked out: the outcome of each check) -> signoff-run."""
    if owner in ("issuer", "shopper"):
        return f"{PREFIX}-{owner}"
    if owner == "system":
        return f"{PREFIX}-run"
    return f"{PREFIX}-store-" + owner.replace(".", "-")


def setup(owners: list[str]) -> dict:
    """Datasets for every owner, an agent identity for the issuer and for the shopper, and each agent's
    permission on its own dataset only. Safe to run again."""
    sys = client()
    datasets = dict(facts().get("datasets") or {})
    for owner in owners:
        r = sys.post("/api/v1/datasets/", json={"name": dataset_name(owner)})
        r.raise_for_status()
        datasets[owner] = {"id": r.json()["id"], "name": dataset_name(owner)}
    agents = dict(facts().get("agents") or {})
    keys = _keys()
    for owner in ("issuer", "shopper"):
        if owner in keys and owner in agents:
            continue
        r = sys.post("/api/v1/agents/create", params={"name": dataset_name(owner)})
        if r.status_code >= 400:
            raise CogneeError(f"agent for {owner}: {r.status_code} {r.text[:200]}")
        body = r.json()
        agent_id = body.get("agentId") or body.get("agent_id")
        key = body.get("agentApiKey") or body.get("agent_api_key")
        keys[owner] = {"key": key}
        agents[owner] = {"id": agent_id, "email": body.get("agentEmail") or body.get("agent_email")}
        KEYS.parent.mkdir(parents=True, exist_ok=True)
        KEYS.write_text(json.dumps(keys))
        KEYS.chmod(0o600)
    grants = []
    for owner in ("issuer", "shopper"):
        for permission in ("read", "write"):
            r = sys.post(f"/api/v1/permissions/datasets/{agents[owner]['id']}",
                         params={"permission_name": permission}, json=[datasets[owner]["id"]])
            grants.append({"principal": owner, "dataset": owner, "permission": permission, "status": r.status_code})
    return _save_facts({"datasets": datasets, "agents": agents, "grants": grants, "set_up_at": _now()})


def write(identity: str, owner: str, texts: list[str], what: str) -> dict:
    """Add text to `owner`'s dataset using `identity`'s key. Returns the logged attempt; never raises on a
    refusal, because a refusal is a result we keep."""
    dataset = facts()["datasets"][owner]
    started = time.monotonic()
    r = client(identity, timeout=180).post("/api/v1/add_text", json={"textData": texts, "datasetId": dataset["id"]})
    try:
        detail = r.json()
    except ValueError:
        detail = r.text
    return log({"action": "write", "identity": identity, "dataset_owner": owner, "dataset": dataset["name"],
                "what": what, "texts": len(texts), "status": r.status_code, "accepted": r.status_code < 300,
                "seconds": round(time.monotonic() - started, 2), "reply": json.dumps(detail)[:300]})


def cognify(owners: list[str], background: bool = True) -> dict:
    ids = [facts()["datasets"][o]["id"] for o in owners]
    started = time.monotonic()
    r = client(timeout=900).post("/api/v1/cognify", json={"datasetIds": ids, "runInBackground": background})
    return log({"action": "cognify", "identity": "system", "owners": owners, "status": r.status_code,
                "background": background, "seconds": round(time.monotonic() - started, 2), "reply": r.text[:300]})


def status(owners: list[str] | None = None) -> dict:
    held = facts().get("datasets") or {}
    by_id = {v["id"]: k for k, v in held.items() if owners is None or k in owners}
    r = client().get("/api/v1/datasets/status", params=[("dataset", i) for i in by_id])
    r.raise_for_status()
    return {by_id.get(k, k): v for k, v in r.json().items()}


def graph_size(owner: str) -> dict:
    r = client().get(f"/api/v1/datasets/{facts()['datasets'][owner]['id']}/graph")
    r.raise_for_status()
    body = r.json()
    return {"nodes": len(body.get("nodes") or []), "edges": len(body.get("edges") or [])}


def ask(question: str, owners: list[str], search_type: str = "GRAPH_COMPLETION", top_k: int = 15) -> dict:
    """One question answered by Cognee from the named owners' datasets. Raises CogneeError if it cannot."""
    held = facts().get("datasets") or {}
    ids = [held[o]["id"] for o in owners if o in held]
    if not ids:
        raise CogneeError("no Cognee datasets: run setup")
    started = time.monotonic()
    r = client(timeout=120).post("/api/v1/search", json={"searchType": search_type, "datasetIds": ids,
                                                           "query": question, "topK": top_k})
    seconds = round(time.monotonic() - started, 2)
    if r.status_code >= 300:
        raise CogneeError(f"search {r.status_code}: {r.text[:200]}")
    return {"reply": r.json(), "seconds": seconds, "search_type": search_type,
            "datasets": [held[o]["name"] for o in owners if o in held]}
