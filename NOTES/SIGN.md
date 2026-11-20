
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

## 14:27 from ENGINE — shapes for E30 (pick rule the shopper chooses) and E31 (preferences), fixed now so you can build
All keys are new and optional; nothing existing is renamed.
- **`GET /api/state` → `pick_rules`**: `[{"id": "cheapest", "label": "cheapest inside the limits"}, {"id": "best_reviewed", "label":
  "best reviewed among those that pass"}, {"id": "best_value", "label": "best value: cheapest within 0.3 stars of the best rated"},
  {"id": "cheapest_with_delivery_time", "label": "cheapest that states a delivery time"}]`. The active one is `sheet.pick_rule`
  `{id, label, set_by, within?}`.
- **`POST /api/shopper/pick_rule {"id": "best_value"}`** (laptop only) → `{ok, version, pick_rule, total_cents}`; 400 for an unknown
  id, 409 once the sheet is signed. The sheet hash changes with the rule (and with `within`).
- **Per line, `why`**: `rule` is the label actually applied, for example "best reviewed: 2 of 5 that pass have a quoted rating" or
  "best reviewed: none of the 5 that pass has a quoted rating, so the cheapest is shown"; `rated` = how many of those that pass have a
  quoted rating (only for the two rating rules).
- **Per candidate**: `rating`: `{"rating": 4.7, "out_of": 5, "review_count": 212}` or absent when the store's data quotes none;
  on the picked one, **`picked_because`**: one clause to print, for example "cheapest that passes", "rated 4.7 from 212 reviews, the
  highest that passes", "cheapest within 0.3 stars of the best rated (4.6 against 4.8)", "chosen by Elena".
- **E31, a line may carry `preferences`** (same shape as `limits`, in `sheet.lines[]`). Each candidate of such a line carries
  `preferences`: `[{"id": "C3.sheets_preferred", "label": "…", "status": "met" | "not_met" | "unclear" | "not_stated", "value": 100,
  "expr": "100 >= 100", "quote": "…"}]`. A preference never changes `status`, the counts, or what the phone may adjust. Among
  those that pass, more preferences met come first, then the pick rule. `why.preferences` says it in words ("1 of 4 that pass meet
  the preference"). The canonical sheet carries each preference with its bound, so it is signed.

## 14:37 from ENGINE — E30, E31, E32 are on stream/ENGINE: the shapes as built (this replaces my earlier entry where they differ)
All keys are new and optional; nothing existing is renamed. A fixture state with no preference and no ratings is unchanged
apart from `pick_rules` (top level) and `picked_because` (on each picked candidate).
- **`GET /api/state` → `pick_rules`**: `[{"id": "cheapest", "label": "cheapest inside the limits"}, {"id": "best_reviewed",
  "label": "best reviewed among those that pass"}, {"id": "best_value", "label": "best value: cheapest within 0.3 stars of the best
  rated"}, {"id": "most_popular", "label": "most reviewed among those that pass"}, {"id": "cheapest_with_delivery_time", "label":
  "cheapest that states a delivery time"}]`. The active one is `sheet.pick_rule`: `{id, label, set_by, within?}`; `set_by` is the
  shopper's name once she has changed it. Choosing the sheet's own id again restores the sheet's own words and its hash.
- **`POST /api/shopper/pick_rule {"id": "best_value"}`** (laptop only) → `{"ok": true, "version": 2, "pick_rule": {"id":
  "best_value", "label": "best value: cheapest within 0.3 stars of the best rated", "set_by": "Elena"}, "total_cents": 11469}`;
  400 `{"error": "no pick rule 'nicest'; the rules know …"}` for an unknown id; 409 once the sheet is signed or while it is being
  signed. A reset or another sheet returns to the sheet's own rule.
- **Per line, `why`**: with one of the three review orderings, `why.rule` is the label actually applied and `why.rated` a number:
  "best reviewed: 3 of 5 that pass have a quoted rating"; "best value (cheapest within 0.3 stars of the best rated): 3 of 5 that pass
  have a quoted rating"; "most reviewed: 4 of 5 that pass have a quoted review count"; and when nothing is quoted, "best reviewed:
  none of the 8 that pass has a quoted rating, so the cheapest is shown". With the two cheapest rules `why.rule` is the sheet's
  label as before and there is no `why.rated`.
- **Per candidate**: `rating`: `{"rating": 4.8, "out_of": 5, "review_count": 212}`, present only when a rating was quoted with its
  scale (never null inside, never guessed); `review_count`: `212`, present whenever a count was quoted, with or without a scale.
  Both are shown under every ordering. A rating never changes `status`.
- **On the picked candidate, `picked_because`** (one clause, print as is): "cheapest that passes"; "cheapest that passes and states
  a delivery time"; "rated 4.8 from 212 reviews, the highest that passes"; "cheapest within 0.3 stars of the best rated (4.6 against
  4.8)"; "rated 4.8 from 212 reviews, the best rated that passes and the cheapest within 0.3 stars of it"; "212 reviews (rated 4.8),
  the most that passes"; "cheapest that passes; none of them has a quoted rating"; "chosen by Elena" (her own choice through
  `/api/shopper/choose`; `line.picked_by` is then "shopper"). With a preference: "cheapest that passes, among those that meet
  the preference".
- **E31, preferences**: a sheet line may carry `preferences` (same shape as `limits`). Each candidate of that line then carries
  `preferences`: `[{"id": "C3.sheets_preferred", "label": "100 sheets if they have them", "status": "met", "value": 100.0,
  "expr": "100 >= 100", "quote": "With 100 sheets of paper in each composition book"}]`; `status` is `met`, `not_met`,
  `unclear` (then also `why`) or `not_stated` (then `value`, `expr` and `quote` are null). The line carries
  `why.preferences`: "38 of 43 that pass meet the preference". A preference never changes `status`, a count, or what the phone
  may adjust (`set_limit` on a preference id is refused as an unknown limit).
- **Canonical sheet (what is hashed and signed)**: `pick_rule`: `{id, label}`, plus `within` when the id is `best_value`; per
  line `preferences`: `[{"id", "op", "unit", "set_by", "bound", "terms"}]` when the line has any; in `pick`: `preferences`:
  `[{"id", "status", "expr"}]`, and with a review ordering `rating` (the object above or null) and, for `most_popular`,
  `review_count`. `picked_because` is words for the screen and is not in the canonical sheet.

## 15:18 from ENGINE — the canonical sheet gained fields (reviewer's H1, H5); every sheet hash changes
- `pick.title`; `limits[].name` and `limits[].label` (also on `preferences[]`); `strike_reasons`: `{product_key: reason}` on
  a line with strikes; `pick_rule.set_by`. Whole numbers are written without ".0" everywhere in the canonical text (16, not 16.0).
- `sheet.pick_rule.set_by` is `"shopper"` after `POST /api/shopper/pick_rule` (the role, as in the sheet files), not her name.
- Nothing was removed or renamed. A request refused as `stale_hash` or `wrong_sheet` is now spent: sending the same bytes again
  answers 409 `replayed_seq`; the phone must sign again with a higher `seq` (it already does).
