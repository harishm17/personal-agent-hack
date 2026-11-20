
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

## 12:10 from ENGINE — receipt chain: one call from you for every signed request, accepted or refused
- `from signoff.engine import receipts` then, in `/api/issuer/request`, once per request that arrives:
  `receipts.signed_request(payload, key_id, accepted, reason=None)`
  - `payload`: the request's payload, the JSON string as signed (`body["payload"]`) or the parsed dict; only its hash is kept.
  - `key_id`: the enrolled key's id, or `None` when there is none.
  - `accepted`: `True` after the engine applied it (or the carts were created); `False` for every refusal: bad signature, replayed
    `seq`, stale hash, already signed, Senso block, identity needed, cart failure, and the engine's own refusals. Pass the refusal's
    message as `reason` (it is stored in the receipt).
  - It never raises and returns the receipt (`{n, at, type, actor, key_id, body_hash, prev_hash, hash, detail}`) or `None`.
  Simplest placement: one call in the success return paths and one in `_fail` (or a `finally`).
- The engine itself already writes a receipt for each change it applies (`limit_set`, `strike`, `unstrike`, `shopper_fact`,
  `reader_switched`, `signed`, `carts_created`), so an accepted limit change gives two receipts: your `request_accepted` and my
  `limit_set`. `engine.reset()` starts a new chain whose first receipt names the chain before it and its last hash.
- Routes (mine): `GET /api/receipts` → `{chain, previous, file, receipts}` oldest first; `GET /api/receipts/verify` →
  `{count, verified, first_bad, checked}`. `/api/state` → `receipts: {count, verified, last_hash, chain}`.
- In tests set `SIGNOFF_RECEIPTS=memory` to keep the chain out of `data/receipts/`.

## 12:22 from ENGINE — the seal race is closed on my side; two small changes in your signing path
- `engine.mark_signed(signature, carts)` now seals **`signature["sheet_hash"]`**, the hash that was signed (you already pass it), and
  refuses with a 409 `EngineError` ("the sheet changed after it was signed (signed …, now …): nothing is sealed …") if the sheet no
  longer has that hash. A signature without `sheet_hash` is refused. Your existing refusal handling (`hasattr(error, "status")`) shows it.
- [ ] Use `engine.signed_picks(payload["sheet_hash"])` in place of your own `_picks(state)`: it returns the picks of exactly that hash,
  `[{store, variant_id, quantity, line_id, candidate_id, product_id, title, price_cents}]` (pass them to `create_carts` as they are; the
  extra keys are for your cart-total comparison per store), refuses with 409 if the hash is not the current one, and **holds the sheet**:
  until `mark_signed` any change by anyone is refused ("the sheet is being signed right now"), so nothing can move while the stores are
  called. If cart creation fails, call `engine.release_signing()` before you return the refusal (the hold also ends by itself after 90 s).
  Until you switch, the first point alone guarantees a changed sheet is never sealed as signed.
- The hash now also covers the pick rule and each pick's delivery quote, so hashes differ from this morning's. `/api/state` →
  `seal.covers` lists what the hash covers (also when unsigned); `signing: {in_progress, sheet_hash, since}` appears during a hold.
## 12:45 from STORE — the outbound ledger is on stream/STORE; and create_carts has a timeout now
`obs.egress("senso", "check sentence of the sheet against the order", sentence, ["order","limit"])` for each call to Senso, Persona
and Firedrill (recipient `senso`, `persona`, `firedrill`; payload as sent; classes you know it carries). Never raises or blocks.
`create_carts(picks, timeout_s=4, tries=1)` answers in about 4 s and returns `mode: "pending"` plus `error` for a store that did not
answer (no exception); the other store's cart is still returned. Rows: `GET /api/egress`.
## From AIRBYTE (Relay) 12:30 — a live-human claim for the signature record
- `signoff.relay.status() -> dict | None` (never raises): `{"claim_type": "live_human_presence", "result": "passed", "sandbox": true, "at": ...}` once a person has taken the check, else `None`. Attach it to the signature record as optional key `relay` when present (omit the key when `None`); label it "sandbox" wherever you show it.
- Page: `/relay/` (on main, works over the tunnel on a phone). The phone's Sign view can link to it (open in a new tab); the person taps "I am a real person", the page then shows "Live human: passed (sandbox)". Do it before signing; `relay.status()` keeps the last result in memory (a new `POST /api/issuer/relay/start` clears it).
- Routes (optional router `signoff.relay.api`): `POST /api/issuer/relay/start`, `POST /api/issuer/relay/complete`, `GET /api/issuer/relay/status`. Nothing in the signature path should depend on it.

## TALK 14:50 — one line where the signing happens, and the same short code in three places (the judge, item B)
- The line: `Dana signs: 6 limits · 8 quotes · 3 picks · $114.69` and the code `3ac9 4ba1 dd01`. Both are data:
  `GET /api/seal/proof` → `summary: {text, code, limits, quotes, picks, total_cents}` (read-only, on `stream/TALK`).
- The same from your own copy of the canonical sheet, so the phone prints what it computed itself and not what the
  server says (`c` is the parsed canonical sheet, `hash` its SHA-256 hex; on the phone these are `canon.obj`, `canon.hash`):
  ```js
  const picks = c.lines.filter((l) => l.pick), n = (k, one) => `${k} ${one}${k === 1 ? "" : "s"}`;
  const line = `${name} signs: ${n(c.lines.reduce((a, l) => a + l.limits.length, 0), "limit")} · ${n(picks.reduce((a, l) => a + l.pick.quotes.length + (l.pick.delivery.quote ? 1 : 0), 0), "quote")} · ${n(picks.length, "pick")} · $${(c.total_cents / 100).toFixed(2)}`;
  const code = hash.slice(0, 12).replace(/(.{4})(?=.)/g, "$1 ");
  ```
  quotes = each pick's figure quotes plus its delivery quote when the store stated one. `/seal/` prints the same line and code.
- For the phone'"'"'s sign screen (`web/phone/index.html:369`, under "What you sign"): print `line` and `code` above the full hash.
