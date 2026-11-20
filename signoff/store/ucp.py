"""UCP-over-MCP client for the stores. Never calls a checkout tool (see FORBIDDEN)."""
import json
import re
import time
import urllib.request

from signoff import config, obs

UA = "signoff-store/0.1"
HEADERS = {"User-Agent": UA, "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
ALLOWED_TOOLS = {"search_catalog", "create_cart", "ask_business", "get_product_details", "lookup_catalog"}
_ENDPOINTS: dict[str, str] = {}


def profile_url() -> str:
    base = config.public_url()
    if not base:
        raise RuntimeError("PUBLIC_URL is empty: the tunnel is not up")
    return base + "/profile/agent-v1.json"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as f:
        return json.loads(f.read())


def endpoint(domain: str) -> str:
    """The store's MCP endpoint from /.well-known/ucp."""
    if domain not in _ENDPOINTS:
        try:
            prof = _get("https://www." + domain + "/.well-known/ucp")
        except Exception:  # noqa: BLE001
            prof = _get("https://" + domain + "/.well-known/ucp")
        entries = prof["ucp"]["services"].get("dev.ucp.shopping", [])
        _ENDPOINTS[domain] = next(e["endpoint"] for e in entries if e.get("transport") == "mcp")
    return _ENDPOINTS[domain]


def _summary(tool: str, r: dict) -> dict:
    if tool == "search_catalog":
        return {"products": len(r.get("products", [])), "titles": [p.get("title") for p in r.get("products", [])[:5]],
                "mode": r.get("mode", "live")}
    if tool == "ask_business":
        return {"answer": (r.get("answer") or {}).get("plain"), "mode": r.get("mode", "live")}
    if tool == "create_cart":
        c = r.get("cart", r)
        return {"cart_id": c.get("id"), "totals": c.get("totals"), "has_continue_url": bool(c.get("continue_url")),
                "mode": r.get("mode", "live")}
    return {}


def _replay(domain: str, tool: str, arguments: dict) -> dict:
    from signoff.store import replay
    if tool == "search_catalog":
        return replay.search_catalog(domain, arguments["catalog"]["query"])
    if tool == "ask_business":
        return replay.ask_business(domain, arguments["ask"]["query"])
    if tool == "create_cart":
        return replay.create_cart(domain, [(i["item"]["id"], int(i.get("quantity", 1)))
                                           for i in arguments["cart"]["line_items"]])
    raise RuntimeError("replay: no saved reply for " + tool)


def _live(domain: str, tool: str, arguments: dict, retries: int) -> dict:
    args = {"meta": {"ucp-agent": {"profile": profile_url()}}, **arguments}
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(endpoint(domain), data=body, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as f:
                d = json.loads(f.read())
            if "error" in d:
                raise RuntimeError(json.dumps(d["error"])[:300])
            res = d["result"]
            return res.get("structuredContent") or json.loads(res["content"][0]["text"])
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{domain} {tool} failed: {last!r}"[:400])


def call(domain: str, tool: str, arguments: dict, retries: int = 2) -> dict:
    """One tools/call. Live: the store's MCP endpoint. SIGNOFF_MODE=replay: saved replies, no network, `mode: "replay"`.
    Each call emits one Amplitude tool-call event. Raises RuntimeError on a store error."""
    if tool not in ALLOWED_TOOLS:
        raise RuntimeError("tool not allowed: " + tool)  # no checkout tool, ever
    replay_mode = config.mode() == "replay"
    return obs.timed("store." + tool, {"store": domain, **{k: v for k, v in arguments.items()}},
                     (lambda: _replay(domain, tool, arguments)) if replay_mode else (lambda: _live(domain, tool, arguments, retries)),
                     lambda r: _summary(tool, r))


def search_catalog(domain: str, query: str) -> dict:
    return call(domain, "search_catalog", {"catalog": {"query": query, "context": {"address_country": "US"}}})


def ask_business(domain: str, query: str) -> dict:
    return call(domain, "ask_business", {"ask": {"query": query}})


def create_cart(domain: str, variant_id: str, quantity: int = 1) -> dict:
    return call(domain, "create_cart", {"cart": {"line_items": [{"item": {"id": variant_id}, "quantity": quantity}]}})


_BLOCK = re.compile(r"</?(p|li|ul|ol|br|div|h[1-6]|tr|table|section)\b[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")


def plain(html: str) -> str:
    """HTML to plain text: tags stripped, entities decoded, block boundaries kept as newlines."""
    import html as _h
    t = _BLOCK.sub("\n", html or "")
    t = _h.unescape(_TAG.sub(" ", t))
    t = re.sub(r"[ \t\u00a0]+", " ", t)
    t = re.sub(r" ?\n[ \n]*", "\n", t)
    return t.strip()
