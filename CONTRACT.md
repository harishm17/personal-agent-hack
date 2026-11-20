# CONTRACT — Sign-Off

Frozen 11:30. Later changes: integrator only, appended as "## Amendment HH:MM — what".
Full spec and reasons: `/Users/harishm/research/2026-11-20-tokensand-personal-agents-hackathon/IDEA.md`
(read it once; this file wins where they differ). Design picture, reference only, write the screen fresh:
`.../research/mock/sign-off-screen-v2.png` in the same folder.

## What we are building
A shopping agent that buys under someone else's limits and signature. The person who knows (the issuer)
sets limits the shopper cannot edit; the store's own words decide each line; the cart exists only when the
issuer signs. Everything runs from a sheet file (`sheets/sheet1.json`); the engine, store client and screen
know nothing about medicine. Sheet 1, shown in depth: a father coming home after surgery; issuer Dana (his
therapist), shopper Elena (his daughter), three real stores. The one moment the demo must show: Dana's phone
moves a limit, dots go grey on the big screen and the pick jumps to another store's product, worked out in
code; then her signature creates the real cart.

## Judging
No rubric is published (`rubric: []`). Prizes are per sponsor, judged by sponsor staff; one project can win
several. Other judges care about: sandboxed and replayable runs, ground truth behind numbers, retail
reality (returns, price accuracy), money safety and explainability, product craft.
Format: finalists give a 3-minute live demo to judges at 17:00. How finalists are chosen: not published.
Submission by 16:30: public GitHub repo (`harishm17/personal-agent-hack`), demo video of about 3 minutes,
the form (fields in SUBMISSION.md). At least three sponsor products must be used (said at the venue).

## Prizes (the builder's decision: as many tools as have a real job; core four before 13:10)
| Prize | What the sponsor wants to see | Our use of the tool | Owner | Demo beat | First real call works |
|---|---|---|---|---|---|
| SingleStore | best use; the decision funnel as one live query | product pool and every decision record live in it; one SQL statement returns the candidates inside all limits of a line | STORE | "this query is the passing box" | yes (11:00, SQL connect) |
| Senso | trusted context, the action, the decision trail | holds the therapist's order, a handout and each store's policy text with version ids; its text check runs on every sentence of the sheet; conflict or unsupported blocks the signature | SIGN | verdicts beside the seal | no key yet |
| Superlinked SIE | agent harness on SIE Serverless; technical build | extracts each figure with character offsets from store text on a pinned model | ENGINE | "every amber number is a span in the store's text" | no key yet |
| Persona | identity verification | the signer passes an Inquiry; the signature record carries the inquiry id (sandbox, labelled) | SIGN | the seal names a checked person | no key yet |
| Amplitude + Statsig | the loop: gate a change, measure it, keep or switch back | one session per sheet run, one tool-call event per search, question, figure read and check; Statsig gate swaps the reader to an Arcee model; outcome measured against the hand-checked sheet | SPONSORS (after 13:10; events at 12:20) | keep or switch back, on numbers | yes (keys tested 10:30) |
| Airbyte | best use of agent connectors | the therapist's order arrives as an email; the Gmail connector reads it locally; limits stay "proposed, from an email" until Dana confirms | SPONSORS (after 13:10, needs mailbox credentials by 14:30) | opening beat | no (SDK installs) |
| Firedrill | exact checks on state, not replies | writes and grades the pressure attempts on a struck line | SPONSORS (after 13:10) | "the attacks were not written by me" | no (CLI installed) |
| Arcee | Pareto frontier (cost against quality) | the cheap reader arm behind the Statsig gate | SPONSORS | same beat as Statsig | no key yet |
| Cognee | memory | Dana's limits and Elena's facts in separate datasets; the shopper's agent is refused a write to a limit | SPONSORS (stretch) | "403 on the therapist's facts" | yes (10:55, datasets list) |
A tool counts only when a real call runs in the demo path or its result is on screen. Not used: Guild.
Drop order when short: Cognee, Tokens& Observe, the Statsig and Arcee loop, Firedrill, Airbyte. Of the core
four at most one is dropped, and only if it is failing. No new tool starts after 15:00.
Answers from sponsor staff: none recorded yet.

## Demo (3 minutes live, real stores)
One sentence: "A shopping agent that buys under someone else's limits and signature."
Beats (full table in DEMO.md): six empty tiles and "No cart exists at any store" → tiles fill from three
real stores, never-stated products are out → the toilet seat line opens: sums with owner names, the store's
sentence → a judge drags a limit on the phone, the pick jumps → the judge strikes a line, "put it back" is
refused → the judge signs, the seal shows signer, time, hash and real cart links → counts strip.
The check that catches something real: a product whose page never states a deciding figure is rejected
with that reason; a figure whose quote is not found in the store's text does not count.
Offline fallback: replay mode (`SIGNOFF_MODE=replay`): cached store responses in `data/`, labelled on
screen, with the checks still running live. Backup clip recorded at 13:10.

## Models and APIs (exact IDs; do not substitute from memory)
| Role | Model / API | Notes |
|---|---|---|
| Figure reader | Anthropic `claude-sonnet-5-5` (env `SIGNOFF_READER_MODEL`); move to `claude-opus-5-5` if under 27 of 30 | proposes value, unit, kind and the exact quote; code finds the quote in the text. Use the `claude-api` skill for request shape. Until `ANTHROPIC_API_KEY` is in the keys file, batch reads may shell out to `claude -p --model sonnet` |
| Shopper chat | Anthropic `claude-sonnet-5-5` (env `SIGNOFF_CHAT_MODEL`) | tools: read state, read candidates. No tool for limits, strikes or carts exists |
| Stores | UCP over MCP JSON-RPC, no key | see "Calling the stores" |
| SingleStore | host, user, password and `SINGLESTORE_URL` in env; database `signoff` | `VECTOR(n)`, `<*>`, `MATCH(TABLE t) AGAINST(...)`; create indexes after loading, then `OPTIMIZE TABLE ... FLUSH` |
| Senso | `https://apiv2.senso.ai/api/v1`, header `X-API-Key` | `POST /org/kb/raw` (raw text only, `.md` rejected), poll, `POST /org/search/context`, check with `POST /org/evals/text`. Ingestion is asynchronous: load documents first. With `author: "ai_assistant"` claims about other brands may come back `not_verifiable`: settle with one call by 11:30; if so Senso checks the sheet against the order and handout only |
| Superlinked SIE | `sie-sdk`, `SIE_API_KEY` | `extract` returns labelled entities with character offsets. Cold models return 503 for minutes: warm and pin the model |
| Persona | `https://api.withpersona.com/api/v1/inquiries`, Bearer key, header `Persona-Version: 2025-10-27` | plain Inquiry flow, hosted link `https://inquiry.withpersona.com/verify?inquiry-id=...`; read status from the backend; sandbox always passes, label it |
| Amplitude | `amplitude-ai`, `AMPLITUDE_AI_API_KEY` | `track_tool_call`, `experiments=` on the session, `ai.flush()` before exit; run `amplitude-ai --print-guide` |
| Statsig | `statsig-python-core` (import `statsig_python_core`) | `check_gate`; gates are false until created; `shutdown().wait()` flushes |
| Arcee | OpenAI-compatible, `https://api.arcee.ai/api/v1` | confirm IDs with `GET /models`; `tool_choice` supports only `auto` |
| Cognee | `COGNEE_API_URL`, headers `X-Api-Key`, `X-Tenant-Id` | `GET /api/v1/datasets` works |
Sponsor notes with install lines and traps: `.../research/sponsors-infra.md`, `.../research/sponsors-context.md`,
`.../research/sponsors-data.md`. Vendor skills installed: `claude-api`, `web-design-guidelines`.

### Calling the stores
- Endpoint: `https://www.<domain>/.well-known/ucp` → `ucp.services["dev.ucp.shopping"]`, the entry with
  `transport: "mcp"`. JSON-RPC `tools/call`, headers `Accept: application/json, text/event-stream`.
- Every call carries `arguments.meta["ucp-agent"].profile` = `$PUBLIC_URL/profile/agent-v1.json`. The app
  serves `profile/` with `Cache-Control: public, max-age=3600`. Stores cache the profile: a changed profile
  needs a new file name. `PUBLIC_URL` is the day's tunnel; it must not change.
- Proven: `search_catalog` (`{"catalog": {"query": q, "context": {"address_country": "US"}}}`),
  `create_cart` (`{"cart": {"line_items": [{"item": {"id": variant_id}, "quantity": 1}]}}`, link in
  `continue_url`), `ask_business` (`{"ask": {"query": ...}}`, single turn). Prices are in cents.
- **Never call a checkout tool.** Rate limits are untested: fetch the pool once, cache it in `data/pool/`.
- Working reference scripts: `.../research/ucp-probe/probe2.py` and `cart.py`.

## Interfaces
One process: `uv run uvicorn signoff.app:app --port 8800`. `signoff/app.py` mounts one router per stream
(`signoff.engine.api`, `signoff.store.api`, `signoff.sign.api`, each exporting `router`) and the static
folders. Keys: `signoff/config.py` loads `~/.config/tokensand.env`, then `.env`; use `config.env("NAME")`.
While developing, each stream runs its own port: ENGINE 8001, STORE 8002, SCREEN 8003, SIGN 8004; 8800 is
main and the only one behind the tunnel.

**Files** (examples of every shape are in `fixtures/`; `fixtures/make_state.py` is the reference code)
- Sheet: `sheets/<id>.json`. A limit is `terms` (summed; each term is a shopper fact or a store figure),
  `op` (`>=` or `<=`) and `bound` (a value the issuer set, or a shopper fact).
- Pool: `data/pool/<store>.json`, a list of `{store, product_id, variant_id, title, price_cents, url, text,
  fetched_at, product_key, line_ids}`. `text` is the plain text the agent received; spans index into it.
  `product_key` is maker and model, lower-cased, so the same product at another store has the same key.
- Store answers: `data/store_answers/<store>.json`, shape of `fixtures/store_answers.json`.
- Figures: `data/figures/<store>.json`, a list of `{store, product_id, figure, kind, value, low, high, unit,
  quote, start, end, extractor, span_found_in_text}`. `kind`: `single`, `spread` ("adds 5 to 5.5 in") or
  `adjustable` ("16 to 21 in"). Figure names: `weight_capacity`, `added_height`, `seat_height`,
  `overall_width`, `length`, `mattress_thickness_max`.
- State: `GET /api/state` returns exactly the shape of `fixtures/state.json`: `version`, `mode`
  (`fixture`, `live`, `replay`), `sheet`, `seal`, `issuer_key`, `counts`, `total_cents`, `store_answers`,
  `lines[]` with `status` (`ready`, `pick_up`, `open`, `next_candidate`), `pick`, `tightest`, `why`,
  `struck`, and `candidates[]` (one decision record per product: `product`, `figures`, `checks` with owned
  `terms`, `arrival`, `undo`, `senso`, `status` of `inside`, `outside`, `not_stated` or `struck`, `reason`,
  `picked`, `action`). New keys may be added; existing keys are not renamed or removed.

**HTTP**
| Route | Owner | Does |
|---|---|---|
| `GET /api/state` · `GET /api/events` (SSE, `data: {"type":"state","version":n}`; the screen refetches) | ENGINE | the whole screen is drawn from these |
| `POST /api/shopper/fact` `{fact_id, value}` | ENGINE | Elena changes a measurement; unsigned, hers |
| `POST /api/shopper/say` `{text}` → `{reply, refused, tool_calls}` | ENGINE | the shopper's chat with the agent |
| `GET /api/sheet/canonical` → `{canonical, sheet_hash}` | ENGINE | the exact string the issuer signs |
| `POST /api/issuer/enroll` `{public_key_jwk, name}` → `{key_id}` | SIGN | first key enrolled is the issuer; again only after `POST /api/admin/reset` |
| `POST /api/issuer/request` `{payload, sig, key_id}` | SIGN | the only way to change a limit, strike, or sign |
| `POST /api/issuer/persona/start` · `GET /api/issuer/persona/status` | SIGN | Inquiry link and status |
| `GET /api/senso/checks` | SIGN | verdicts for the current sheet |
| `POST /api/admin/reset` | SIGN | back to unsigned, no key, sheet as on disk (for rehearsals) |
| `POST /api/admin/refresh-pool` · `GET /api/sql/passing-box?line_id=` | STORE | refetch stores; run the one SQL statement |
| `/` · `/phone/` · `/profile/agent-v1.json` | SCREEN · SIGN · STORE | big screen · Dana's phone · agent profile |

**Signed request.** The phone makes an ECDSA P-256 key pair with WebCrypto (private key not extractable,
kept in IndexedDB). `payload` is a JSON string: `{"type", "sheet_id", "seq", "at", ...}` with `type` one of
`set_limit {limit_id, value}`, `strike {line_id, product_key, reason}`, `unstrike {line_id, product_key}`,
`sign_sheet {sheet_hash}`. `sig` is base64url of the WebCrypto signature (raw r||s) over the UTF-8 bytes of
`payload`. The server checks the signature against the enrolled key, that `seq` is greater than the last
one, and for `sign_sheet` that `sheet_hash` equals the current hash; only then does it call the engine or
create carts. WebCrypto needs https or localhost: the phone uses the tunnel.

**In-process calls between streams** (signatures fixed; bodies are the owner's)
- `signoff.engine.state`: `get_state() -> dict`, `apply_issuer(action: dict) -> dict` (called only by
  `signoff.sign` after verification), `set_shopper_fact(fact_id, value) -> dict`, `canonical_sheet() -> str`,
  `sheet_hash() -> str` (SHA-256 hex of the canonical string: `json.dumps(obj, sort_keys=True,
  separators=(",", ":"))` over sheet id, each line's limits, pick, its figures' quotes and prices, and the
  total), `mark_signed(signature: dict, carts: list) -> dict`, `reset() -> dict`,
  `set_senso(checks: list) -> dict`, `reload_data() -> dict`.
- `signoff.store.pool.load() -> tuple[list, list]` (pool, store answers, from `data/`, falling back to
  `fixtures/`); `signoff.store.cart.create_carts(picks: list[dict]) -> list[dict]` with pick
  `{store, variant_id, quantity}` and result `{store, cart_id, cart_url, total_cents, created_at, mode}`;
  `signoff.store.ask.ask(store, query) -> dict`; `signoff.db.records.write(state: dict) -> None` (never
  raises; the app works with the database down).
- `python -m signoff.extract.run` reads `data/pool/*.json` and writes `data/figures/*.json`.

## Rules code decides (the model never decides these)
- A figure counts only if `text[start:end] == quote` in the store's text.
- Every comparison and margin. A spread uses the end that could fail; an adjustable range passes when the
  limit lies inside it. A missing figure makes the product `not_stated`, never a guess.
- The pick: among candidates inside every limit and not struck, those whose store states a delivery time,
  cheapest first (ties by id). Lines with `fulfilment: pick_up_locally` skip the delivery condition.
- Limits and strikes change only through a verified signed request. A strike is by `product_key`, so it
  holds at every store.
- Carts are created only after a verified `sign_sheet` whose hash matches. No model has a cart tool.
- Wording on screen: "the model reads the figure; code checks that the quote is in the store's text and
  does the sums". Write "states", never "proves". Everything invented is labelled "invented" in words.

## Ownership
| Stream | Owns | Reads | Done when (13:10) |
|---|---|---|---|
| ENGINE | `signoff/engine/**`, `signoff/extract/**`, `signoff/agent/**`, `data/figures/**`, `tests/engine/**` | sheets, pool, fixtures | `/api/state` is live from the real pool; a signed limit change moves the pick; a strike holds against the chat |
| STORE | `signoff/store/**`, `signoff/db/**`, `data/pool/**`, `data/store_answers/**`, `profile/**`, `tests/store/**` | sheets | pool cached for six lines from three stores; one real cart link; records in SingleStore |
| SCREEN | `web/screen/**`, `demo/**`, `tests/screen/**` | `/api/state`, fixtures | the line view, tiles, seal and counts drawn from `/api/state`, legible at 960 x 540 shown at 200% |
| SIGN | `signoff/sign/**`, `web/phone/**`, `evals/**`, `tests/sign/**` | engine and store calls | a second phone enrols, moves a limit, strikes and signs over the tunnel; Persona and Senso wired |
Integrator (lead session) owns everything else: this file, DEMO.md, SUBMISSION.md, README.md, AGENTS.md,
`signoff/app.py`, `signoff/config.py`, `sheets/`, `fixtures/`, `streams/`, `pyproject.toml`, `uv.lock`,
`.hk/`, and merges to main. A new dependency: ask in `NOTES/INTEGRATOR.md` (or run `uv add` and say so there).

## Verification
- Deterministic gate: span match, sums, pick, signature and hash checks, all unit-tested by their owners.
- First-hour tests (decide once, by 12:00): extraction names the right figure with a found span on 27 of 30
  hand-checked products; 4 of 6 lines have two candidates stating every deciding figure; a second phone
  signs over the venue network. Any miss: sheet 2 (shared kitchen, cookware stores) becomes the main case.
- Numbers shown: products found, products stating every deciding figure (hand-checked), extraction score on
  the 30-product sheet, and the 40 pressure attempts only if the plain agent gives way 6 or more times.
- Checks: `.hk/config.json` (`uv run -q pytest -q -x`, under 60 seconds).

## Timetable
| Time | Milestone |
|---|---|
| 11:30 | contract frozen, fixtures committed, streams launched |
| 12:00 | first-hour tests decided |
| 12:20 | first sync: real store results replace fixtures; Amplitude events go in |
| 13:10 | first end-to-end run with real inputs; backup clip; three sponsor tools working |
| 13:30 | lunch |
| 15:00 | feature freeze; no new tool |
| 15:30 | code freeze: record video, pitch rehearsal |
| 15:45 | repo public and pushed (needs the builder's yes) |
| 16:10 | first version of the form submitted (`./hk submit` passes) |
| 16:30 | deadline |

## Non-goals
Checkout or payment of any kind. Medical advice or suggesting a limit. A floor plan or house drawing. A
phone mirror on the big screen. Accounts, login or more than one sheet at a time. Arrival dates the stores
do not promise. Any invented product under a real brand name. Guild. Pitching this as a hospital-discharge
tool: the therapist is the first issuer, not the product.

## Amendment 11:10 — main port, tunnel, Airbyte
- The main app runs on port **8800**, not 8000 (8000 is used by another program on this Mac). Stream ports
  8001 to 8004 are unchanged. The tunnel is up and `PUBLIC_URL` is in the keys file; it serves main only.
- Airbyte (said by their staff at 10:49): "use it locally" means Airbyte Core from the Docker image, not
  only the agent connector package. The SPONSORS work after 13:10 decides the job once Docker is checked.
- Firedrill's prize asks to "show what you learned and how you used it to improve your agent".
- Team: solo.

## Amendment 11:20 — models without an Anthropic key, new keys
- `ANTHROPIC_API_KEY` arrives only near the end. Until then: the **shopper chat** runs on an Arcee model
  (OpenAI-compatible, `https://api.arcee.ai/api/v1`, `ARCEE_API_KEY`, `tool_choice` only `auto`); the
  **figure reader** runs on an Arcee model and, once `SIE_API_KEY` arrives, Superlinked SIE `extract`;
  `claude -p --model sonnet` is the backstop for the batch read. Keep the model behind
  `SIGNOFF_READER_MODEL` and `SIGNOFF_CHAT_MODEL` so an Anthropic model is a one-line switch.
- Arcee model IDs from `GET /models` at 11:18: `zai-org/glm-5.3`, `zai-org/glm-5.3-flash`,
  `moonshotai/kimi-k3.1-pro`, `moonshotai/kimi-k3`, `deepseek/deepseek-v4.1-flash`,
  `deepseek/deepseek-v4.1-flash-1017`. Pick by the 30-product score, then cost.
- In the keys file and tested: `ARCEE_API_KEY`, `SENSO_API_KEY` (`GET /org/kb/root` 200), `PERSONA_API_KEY`
  (`GET /inquiries` 200; the template id is still to come), SingleStore, Cognee, Amplitude, Statsig.
- Fallback sheet test (11:12, pattern match, 78 cookware products at five stores): induction stated on 9,
  an oven temperature on 9, a diameter on 27. All under half: if sheet 2 is built, its limits change to
  ones those pages state (diameter stays; replace the other two after reading the pool).

## Amendment 11:25 — no hand-check sheet; Sonnet is the reference reader
- The builder's decision: the 30-product hand-check is dropped and `claude-sonnet-5-5` is trusted as the
  figure reader (through `claude -p` now, the API key later). The span check in code stays the judge of
  every figure.
- Nothing on screen, in the README or on stage says "hand-checked" or gives an accuracy against ground
  truth. `counts.hand_checked` stays false and the counts strip says "read by the model; quote found in
  the store's text by code".
- Other readers (Superlinked SIE, an Arcee model) are measured as **agreement with the Sonnet reference**
  on the same products, plus the share of their figures whose quote is found, cost and latency. Say
  "agreement", never "accuracy". This is the outcome for the Statsig gate.
- First-hour tests left: 4 of 6 lines have two candidates stating every deciding figure; a second phone
  signs over the tunnel. The integrator spot-reads ten figures against the store text before 12:20.
- Arcee: the key lists models but every completion returns 402 (no credits). Blocked until the builder
  gets credits. Until then the shopper chat also goes through `claude -p`.
- Persona: the template is published to Sandbox and a real inquiry was created at 11:21.

## Amendment 11:30 — STORE takes observability; no cross-store strike; Senso scope
- STORE finished its 13:10 list early and now also owns `signoff/obs/**`, `signoff/airbyte/**`,
  `data/sheet2/**`, `tests/obs/**`. `signoff.obs.tool_call(name, input, output, success, latency_ms)` and
  `signoff.obs.session(sheet_id)` send Amplitude Agent Analytics events; they never raise and never block.
  ENGINE calls `tool_call` for each figure read and each check run; STORE for each store call.
- No product is sold under the same maker and model at two of the three stores, so "the same one from
  another store" is cut from the demo. A strike still holds for its `product_key`.
- Senso gives no verdict on another brand's claims. It checks each sentence of the sheet against the
  therapist's order and the handout in its knowledge base; store sentences are checked by span match in code.
- First-hour test, coverage: passed at 11:26. Lines with two or more candidates stating every deciding
  figure: 6 of 6 (L1 19, L2 13, L3 5, L4 14, L5 2, L6 9). The main case stays.

## Amendment 11:32 — AIRBYTE stream (the builder asked for Airbyte; local Airbyte Core is installed)
- A fifth stream, AIRBYTE, owns `signoff/airbyte/**`, `data/order/**`, `tests/airbyte/**` (STORE no longer
  owns `signoff/airbyte/**`). Its job and time box are in `streams/AIRBYTE.md`: the therapist's order
  reaches the app's database through a local Airbyte sync; limits read from it are "proposed, from the
  order" until Dana confirms on her phone. The product never depends on it: `signoff.airbyte.api` is an
  optional router and `signoff.airbyte.order.load()` may return `None`.
- Airbyte Core 2.5.0 runs at `http://localhost:8900` (Docker through Colima); login in the keys file.

## Amendment 11:40 — what works on main, Senso gate, readers
- On main at 11:38 (115 tests): real pool, figures, live screen, phone enrol and signed requests, strike,
  signing with two real carts (carex.com and parentgiving.com), Senso run on the sheet's sentences, Persona
  sandbox inquiry, replay mode, Amplitude events from store calls, the chat with code-decided refusals.
- Senso gate as built: `order` sentences (a line is on the order) block the signature on `conflict` or
  `unsupported`; `limit` sentences are advisory, because Dana may move a limit away from the order ("Dana
  moved this from the order" is shown, the signature goes through). Store sentences are never sent.
- Readers: Sonnet is the reference (189 figures, 20 marked unsure and not counted). On the same 111
  products `sie:Qwen/Qwen3.8-27B-FP8` agrees on 166 of 169 and `sie:urchade/gliner_multi-v2.1` on 118 of
  169. `signoff.engine.state.set_reader(name)` switches which reader decides; this is the change the
  Statsig gate controls and Amplitude records. It replaces Arcee, whose key has no credits.
- vivehealth.com states no delivery time to three differently worded questions, so under the pick rule
  its products are shown and checked but never picked. Say so if asked; do not invent a time.
- `ANTHROPIC_API_KEY` is present with about $4.50: live calls only, capped; batch reads use `claude -p`.

## Amendment 12:00 — depth without a new layer (two independent reviews agree)
The working path (pool, figures, pick rule, signed requests, carts, existing routes and state keys) is
**not changed**. New work is new files, new routes and new optional state keys only. Anything not on main
and seen in a rehearsal by **14:30** is cut. Tag `e2e-phone-signed-1146` is the version the builder signed
from his phone.
1. **Ask, don't tell** (STORE asks, ENGINE reads). For each line's pick and runner-up, and for products
   that are `not_stated`, one question to the store's own agent built by a code template from the product
   title and the figure name only ("What does <title> state for <figure>?", plus one on returns of an
   opened item and delivery time for picks). The question never contains a limit, a shopper fact or a
   person. Cached in `data/store_answers/asked/`. The reply is read by the same reader and span check
   against the reply text. New optional key on a candidate: `asked` (list of `{figure, question, reply,
   quote, start, end, value, unit, answered, asked_at}`). **Display only: the pick rule ignores it.**
2. **A planted instruction that changes nothing** (ENGINE). One invented product, store
   `planted.example`, title prefixed "Planted test page (invented)", whose text contains an instruction to
   the agent. It is read like any page. New optional keys: on a candidate `embedded_instructions` (list of
   `{quote, start, end}`, found by the reader and confirmed by span match) and at top level `planted`
   (`{candidate_id, instructions, effect: "none", why}`). It is never eligible for a cart.
3. **Receipt chain** (ENGINE owns `signoff/engine/receipts.py`; SIGN calls it for every signed request,
   accepted or refused). Each receipt: `{n, at, type, actor, key_id, body_hash, prev_hash, hash}`.
   `GET /api/receipts`, `GET /api/receipts/verify` → `{count, verified, first_bad}`. Say "tamper-evident".
4. **Outbound ledger** (STORE owns `signoff/obs/egress.py`; every stream calls
   `obs.egress(recipient, purpose, payload, fact_classes)` where it sends anything out: stores, model
   providers, Senso, Persona, Amplitude, Statsig, Airbyte). It records recipient, purpose, size, a hash,
   the fact classes included (`limit`, `home_measurement`, `person`, `order`, `store_text`, `product`,
   `price`, `none`) and a code check that no limit value with its unit and no shopper fact value appears
   in a payload to a store. `GET /api/egress` → rows and `{messages, to_stores, limits_in_store_messages}`.
Wording allowed: "quarantined reader" (the reading model has no tools; its output is typed and
span-checked), "decision-bound signature" (the hash covers limits, quotes, picks and total), "limits are
compared locally; no store is told a limit". Not allowed: "provable", any leak rate from fewer than 20
trials, "hand-checked".
Cut for good: sheet 2, Cognee, Arcee, Tokens& Observe, a simulated multi-turn store agent, a redaction
model as the guard.

## Amendment 12:10 — the builder's decisions: the agent derives the limits; items 3 and 4 go ahead; motion
- **Nobody configures limits.** The therapist's order is a plain document
  (`signoff/sign/senso_docs/order.txt`, the same text Senso holds). The agent reads it with the same
  reader and span check it uses on store text and proposes every limit with the order's own sentence
  quoted. ENGINE: `python -m signoff.extract.order` writes `data/order/derived.json` (per limit id: line,
  figure terms, op, value, unit, `quote`, `start`, `end`, `extractor`, `span_found_in_text`), read once
  and cached like the figures. New optional key on each sheet limit in `/api/state`: `from_order`
  (`{doc, quote, start, end, value, matches}`) and at top level `order` (`{doc, title, limits_derived,
  limits_matching, derived_at, delivered_by}`). A test proves the derived limits equal
  `sheets/sheet1.json`; the sheet file stays what the engine runs on, so the working path is unchanged.
  Elena's home measurements are context the agent holds, shown with their source, not a control surface.
- **The approver reviews and signs.** The phone opens on the sheet to sign. Each limit shows the order's
  sentence. One limit can be adjusted as an override (the live moment); it is then marked "changed from
  the order" (Senso already says so). No screen asks anyone to set six limits.
- **On screen** every number has a source in one or two words: "from the order", "from the home", "the
  store states", "the store's agent said". Role jargon and the owner legend go.
- **Items 3 (receipt chain) and 4 (outbound ledger) of Amendment 12:00 are approved.**
- **The flow layout is approved; SCREEN adds motion.**
- Firedrill: the builder's account has 2,000 credits and an assigned seat, so
  `native_participant_capacity_exceeded` is on Firedrill's side; he is asking their staff.

## Amendment 12:20 — third review (it ran the live app): fixes ahead of features
- The reader gate was on and the small model was deciding purchases, with at least one misread
  (`h x w x d: 1.63" x 31" x 14.75"` read as width 14.75). Switched back at 12:05. The gate's story is
  "tried behind a gate, measured, **switched back**", shown with the evidence. Its demo beat comes before
  signing; the gate does nothing once the sheet is signed.
- The sign tap must answer within about 8 s: Senso runs in the background when the hash changes, never
  inside the tap; cart creation gets one short try per store; a slow store yields a labelled pending cart.
- `/api/sql/passing-box` must apply the engine's `unsure` filter so its count equals the screen's.
- The spine, in this order: order → quoted figures → pick computed in code → signature → carts. Everything
  else (Airbyte, Persona, the gate, receipts, the ledger, the chat refusal) is "also in the product": one
  sentence each at most in the demo. Priority for screen and engine: the order's sentence beside each limit.
- Claim wording: "the agent's reading of the order matches the sheet, N of N limits"; agreement between
  readers is "same number on N of M figures both found", never a bare percentage. Numbers are read from
  the screen, never quoted from memory.
- Tunnel: a quick tunnel; if its process dies the address changes. `scripts/tunnel.sh` restarts it and
  records the new address; never restart it otherwise. `scripts/run_main.sh` restarts the app.
- Firedrill: keep trying until 14:00 only. Receipt chain: lowest priority, cut at 14:30 if not on main.
