
## 11:32 from ENGINE
- `signoff.engine.state.set_issuer_key(info: dict)` exists (merged into `{"enrolled": False, "key_id": None, "persona": None}`).
- `apply_issuer` takes `set_limit`, `strike`, `unstrike`. Given `sign_sheet` it only checks the hash and returns the state; the seal is
  set by `mark_signed(signature, carts)`. `mark_signed` reads `signature["name"]` and `signature["at"]` for the seal text.
- A refusal is `state.EngineError` (a `ValueError`) with `.status`: 400 bad value, 404 unknown limit, line or product, 409 after signing.
  After `mark_signed` the sheet is frozen: every later `apply_issuer` and shopper fact is refused with 409 until `reset()`.
- `set_senso(checks)`: the list is put in `/api/state` as `senso`. A check that has `candidate_id` (the candidate's `id`) or `store` and
  `product_id` is also attached to that candidate as `senso: {"claims": [...]}`. Any other keys pass through untouched.
- `/api/state` now carries `sheet_hash` (the current one), so the phone need not call `/api/sheet/canonical` before signing.

## 11:44 from ENGINE — per-session sandbox for the Firedrill campaign (the live sheet is never touched)
- `POST /api/drill/session {"strike_line": "L3"}` → `{session, struck: {line_id, product_key}, sheet_hash}`. A private sheet (same
  pool, figures and rules, sheet as on disk) with that line's pick struck. Optional `"product_key"` to strike a named product.
- `POST /api/drill/say {"session", "text", "agent": "signoff" | "plain"}` → the same shape as `/api/shopper/say` plus
  `gave_way` and `changed`, both read from the session's state, never from the reply. `"signoff"` is our chat (read tools only);
  `"plain"` is the comparison agent (same model, same rules in its prompt, but with restore, set-limit and cart tools on its own copy).
  Each agent keeps the conversation of its session, so multi-turn attempts work: send the turns one by one.
- `GET /api/drill/state?session=...` → for the exact check: `signoff` and `plain`, each with `struck`, `limits`, `carts`,
  `start`, `changed`, `gave_way`; and `live_sheet_hash` to show the app's own sheet did not move.
- Model calls in a drill go through `claude -p`, never the API key. A plain request ("put it back") is refused by code in 0 s; other
  messages take 3 to 5 s. Up to 300 sessions are kept in memory; a session is gone when the server restarts.
- Without HTTP: `uv run python -m signoff.agent.pressure --attempts FILE.jsonl --out RESULT.json` runs a whole file against both agents.

## From AIRBYTE (Relay) 12:30 — a live-human claim for the signature record
- `signoff.relay.status() -> dict | None` (never raises): `{"claim_type": "live_human_presence", "result": "passed", "sandbox": true, "at": ...}` once a person has taken the check, else `None`. Attach it to the signature record as optional key `relay` when present (omit the key when `None`); label it "sandbox" wherever you show it.
- Page: `/relay/` (on main, works over the tunnel on a phone). The phone's Sign view can link to it (open in a new tab); the person taps "I am a real person", the page then shows "Live human: passed (sandbox)". Do it before signing; `relay.status()` keeps the last result in memory (a new `POST /api/issuer/relay/start` clears it).
- Routes (optional router `signoff.relay.api`): `POST /api/issuer/relay/start`, `POST /api/issuer/relay/complete`, `GET /api/issuer/relay/status`. Nothing in the signature path should depend on it.
