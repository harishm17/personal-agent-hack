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

## Amendment 12:25 — Persona Relay (optional, time box 13:15), and the Amplitude + Statsig brief
- **Relay.** The sandbox Persona key works for Relay: with `@persona/sdk-node` 0.5.1 a sandbox session
  for `live_human_presence` was created and a Privacy Pass issued at 12:20. The AIRBYTE thread (its
  Airbyte work is done) also owns `signoff/relay/**`, `web/relay/**`, `tests/relay/**` and builds: a
  "live human" claim taken at the moment of signing, recorded on the signature as optional key `relay`
  (`{claim_type, result, sandbox: true, at}`). Inquiries answer who signed; Relay answers that a person,
  not the agent, tapped Sign. Optional router `signoff.relay.api`; the product never depends on it. Not
  working on main by 13:15: cut. `PERSONA_PRODUCTION_API_KEY` is never read by any code.
- **Amplitude + Statsig's own brief (their deck):** try a change behind a gate; see what happened in
  Agent Analytics (tool calls, completion, failures, latency, cost); keep it or switch back; "leave with
  one feature gate, one useful insight, one better agent; show what changed and why it helped". Ours: the
  gate is the small reader; the insight is its misread of an `h x w x d` string; the better agent is a
  code check on multi-dimension strings added because of it, re-measured.

## Amendment 12:30 — fourth review (it attacked a copy of the app): what held, what is being closed
Held under real requests: unsigned, forged, replayed and stale-hash requests are refused; no cart without
a verified signature; picks follow from the figures; all 173 counted figures match the store text at their
offsets and ten of ten sampled are right readings. Being closed now:
1. **Approver takeover** (anyone could reset and enrol their own key over the tunnel). Done by the
   integrator: reset, reader override, reloads and shopper routes are laptop-only (`LOCAL_ONLY` in
   `signoff/app.py`). SIGN: enrolment needs a one-time code that the laptop's screen shows
   (`GET /api/issuer/enroll-code`, laptop-only; the phone sends it with `enroll`; a new code after each
   reset). The signer's name is "self-declared" on the seal until an identity check passes.
2. **Seal race.** `mark_signed` takes the signed hash and refuses if it differs from the current hash;
   carts are created for exactly the signed picks (ENGINE and SIGN).
3. **Cart total.** The store's cart total is compared with the signed total per store; a difference is
   shown on the seal as "store total differs" with both numbers, never hidden (SIGN and STORE).
4. **The hash covers the rule and the delivery evidence**: the pick rule and each pick's arrival quote
   join the canonical sheet (ENGINE). The seal lists what the hash covers.
5. **Unambiguous numbers, as a general rule** (the builder: no overfitting, no format lists): a figure
   counts only if its number is unambiguous in its quote. When a quote holds several numbers of the same
   unit, the reader must also return the label the text itself attaches to the number, and code checks
   that pairing from the text; otherwise the figure is unsure. No prompt line or rule names a format.
Claims: do not call signed approvals, mandates, replay protection or quote checking new. The closest
prior work is "Signing the Transaction but Not the Decision" (arXiv 2609.11757, Sept 2026), which
proposes binding the decision to the signature; say that this build does that, with a signer who is not
the payer, over real stores. The Personal Agent Protocol is real (Persona's deck today names Persona as a
design partner; personalagentprotocol.org).

## Amendment 12:40 — the paper, read first-hand (Louck, Dvir, Stulman, arXiv 2609.11757)
- Correction to Amendment 12:30: the paper does **not** bind the decision. It shows AP2 "signs the
  transaction but not the decision" (a merchant's text moves the choice in up to 73% of runs, the cart
  differs from what was shown in 56%), and its fix binds the cart to **what was displayed** ("display
  binding": product id, unit price, currency, quantity, payee, one cart per approval, no replay) and
  surfaces overspend against the cheapest item meeting the hard constraints. Its own words: "the mandate
  chain contains no evidence for that judgment" and "no downstream check can fully validate the product
  choice".
- How to cite it: "Louck et al. showed that AP2 signs the transaction but not the decision, and bind the
  cart to what was displayed. This build goes one step further and puts the reasons (limits, quotes, sums
  and the pick rule) under the approver's signature, on real stores." Adopt their terms "display binding"
  and "surfaced, not closed". The Personal Agent Protocol's roadmap does list signed approvals as future
  work (read first-hand at personalagentprotocol.org/docs/introduction).
- Gaps it exposes here, to close in this order:
  1. **Display binding on the phone** (SIGN). The phone fetches `/api/sheet/canonical`, hashes it itself
     with WebCrypto, refuses to sign if that differs from the server's hash, and renders the review from
     that same JSON, so what she sees is exactly what she signs.
  2. **Quantity, currency and the variant** join the canonical pick (ENGINE): `quantity`, `currency`,
     `variant_title`. After cart creation SIGN compares the store's cart lines (variant id, quantity,
     unit price) with the signed picks, not only totals; a difference is shown, not hidden.
  3. **Scope labels** (ENGINE, SCREEN): a delivery or returns answer that is the store's general answer is
     marked `scope: "store-wide"`; a figure read from a product description that has several variants
     carries `variants` (count) and the bought variant's title is shown. No figure is dropped for it.
  4. SIGN uses the engine's signed picks for the signed hash (currently unused), so no cart is orphaned.
- Said aloud as limits, not fixed: a quote proves where a figure came from, not that the store's claim is
  true; signatures have no expiry; no third party verifies.

## Amendment 12:50 — the builder's decision: the main example becomes sheet 2, "the plumber's fixture list"
- **Why.** The builder found the home-after-surgery example confusing and unconvincing. An ideation pass
  with 24 real store searches, confirmed by STORE's fetch, found a clearer one: a homeowner (Priya,
  invented) buys four bathroom fixtures; the plumber who installs and guarantees them (Marco, invented)
  wrote the list and signs before anything is bought. One or two obvious numbers per item.
- **Files** (integrator): `sheets/sheet2.json`, `sheets/sheet2_order.txt` (the order document; the sheet
  names it in `order_doc`). Lines `T1` toilet (rough-in equals the house's measured 10 in; flush volume at
  most 1.28 gpf, a dual flush read as a spread so the full flush decides), `T2` sink faucet (at most
  1.2 gpm), `T3` shower head (at most 1.8 gpm), `T4` vanity (overall width at most the 30 in alcove).
  Stores: swissmadison.com, horow.com, deervalleybath.com, kingstonbrass.com. Pick rule `cheapest`
  (cheapest inside the limits; delivery time is shown, not required, because Horow states none).
- **Sheet 1 stays whole as the fallback** (`SIGNOFF_SHEET` unset, or `use_sheet("sheet1")`). The main app
  runs sheet 2 as soon as it works end to end; if sheet 2 is not rehearsed by 14:30, the demo is sheet 1.
- **Work.** ENGINE: op `==` (today any op that is not `>=` is silently treated as `<=`: fix that for every
  sheet), units gpf and gpm, order document and derived limits per sheet, replies and instruction scan per
  sheet, a planted page for sheet 2, pick rule by id, names instead of pronouns in the chat; then the
  reading passes. STORE: the bathroom pool moves to `data/sheet2/pool/` with its store answers (the
  cookware draft is deleted), tables and the SQL for sheet 2, Airbyte and the ledger follow the active
  sheet. SIGN: the Senso documents for `sheets/sheet2_order.txt`, phone wording from the sheet (no fixed
  names or roles). SCREEN and TRAIL: nothing may assume sheet 1's ids, names, rooms or six items.
- **What was found in the real pages** (STORE, pattern count): 52 toilets, rough-in stated on 45 (17 are
  10 in), flush volume on 41 (33 state two numbers); every faucet states 1.2 gpm; shower heads state 1.8
  or 2.5 gpm; vanity width is stated explicitly on about half, the size in a title being nominal. Horow
  sells the same toilet as T0338W (12 in rough-in, $299) and T0338W-10 (10 in, $349).
- **The audit trail gets its own stream, TRAIL** (`streams/TRAIL.md`): `/trail/`, the run as a sequence
  diagram drawn from the receipt chain, the outbound ledger and the other real records.

## Amendment 13:10 — the audit: we were over-restricting. Three general rules replace it
An independent reviewer read all 47 `not_stated` candidates and all 20 `unsure` figures of sheet 1 against
the store text. **In 28 of 47 the "missing" figure is on the page**; only 19 pages truly lack it. All 20
unsure figures are real statements with the right number. One `outside` of 8 read is wrong. Three picks
change. The quote check itself is sound (188 of 188 quotes found; no wrong number in anything read). So
the headline "N pages never state the figure" was mostly our own strictness, and it is withdrawn until
re-measured. Causes: an unsure figure was treated as absent; the reader's prompt demanded an "exact
measure"; only the cheapest option of a product was read; an adjustable range had to contain the bound.
The fix is general, with no rule for any product, format or store (the builder: no overfitting):
1. **Every value the page states is tested.** A figure may carry several stated values (a spread, two
   mentions, an unclear label). If every one passes the limit, the candidate is inside on that limit; if
   every one fails, outside; if they differ, it is `unclear` ("page states both"), a status of its own.
   `unsure` no longer means absent.
2. **Every option on sale is judged.** A product is read once per in-stock option, the option's name
   being part of the text ("Selected option: 18 Inch"); each option is its own candidate with its own
   price and variant id; the pick is the cheapest candidate that passes. STORE's pool carries every
   in-stock option.
3. **A limit is compared as written.** "At least" and "at most" pass when a stated setting or value
   meets them (an adjustable seat that can reach 19 in passes "must reach at least 19 in"); only an
   equality or "fits" needs the exact figure. The comparison comes from the order's own sentence.
Also: a number with a label and no unit is `unclear` ("no unit stated"), not absent. Figure meanings live
in the sheet (`figures`), in the order's own words; the reader's built-in glossary goes. Statuses of a
candidate are now `inside`, `outside`, `unclear`, `not_stated`, `struck`. The three counts are shown
separately: truly absent, stated but unclear, outside. Store agents answered "does not specify" for
pages that do state the figure, so "the store's agent" is used for delivery and returns only.
Removed as fitted to today's examples: the planted page's wording in the scan prompt and pattern; the
brand list in `store/build_pool.py`; per-product-type word lists and the hard-coded question in
`store/sheet2.py`; every hard-coded `sheet1` path (one path rule for all sheets); the fixture fallbacks
in `signoff/app.py` and `extract/run.py`. "168 of 168 agreement" is not shown.
After the three rules: both sheets are re-read and re-counted, and the integrator reads a sample of
`not_stated` and `unclear` by hand before any count is said aloud.

## Amendment 13:30 — the lead example is sheet 3, "the teacher's list" (the builder's choice; two research passes)
- **Why.** The builder: "I still don't get the real life case. Why not just tell the other person what to
  buy?" An honest search over eleven situations found the real everyday case is not the second signature
  but **a list written by someone who is not shopping, stated as facts rather than products, and shopped
  by many people**. The answer to "why not name the product": the teacher knows what is required, not
  what is in stock or cheapest at each family's store, and one list is shopped by 25 families.
- **The example** (`sheets/sheet3.json`, `sheets/sheet3_order.txt`; all people invented): Ms. Alvarez, a
  3rd-grade teacher, writes the list. Dev, the room parent, buys a set for each of 24 students with the
  class fund; class fund purchases need her signature (PTA practice is two authorisations). Lines: `C1`
  headphones no louder than 85 dB (the loudest stated level counts), `C2` crayons exactly 24 in a box,
  `C3` notebook at least 70 sheets, `C4` pencils at least 12 in a pack. Pick rule `cheapest`.
- **Found on real pages** (pattern counts by two probes, not the reader): a volume level on 26 of 30
  headphone pages at three kids' brands and on 0 of 10 at Skullcandy; crayon count 16 of 20; notebook
  sheets 20 of 27; pencil count 19 of 30. Catches: "BuddyPhones School+ Wireless" states "three sound
  levels—75dB, 85dB, or 94dB"; JLab JBuddies Pop Wireless states "Volume limiting: Yes (85 dB)" and "95 dB
  as the default"; a 64-count crayon box beside the 24.
- **Not expressible today and left out**: word facts (wide ruled, #2, blunt tip), "no wheels", brand rules.
  Optional and general if cheap: a line's `quantity` (24) carried into the cart and the total.
- **Order of the three sheets**: sheet 3 leads the demo; sheet 2 (the plumber) is the second example and
  the fallback; sheet 1 (home after surgery) stays in the repo and is not shown. The parent-and-teenager
  draft is dropped; its best finding (headphones) is line `C1`.
- **Claims not to make**: that approvals today are blind (Apple's Ask to Buy shows the item; Ramp checks
  every transaction against policy); that teachers approve parents' carts or that schools work this way
  today; anything about allergy safety; any pattern count as an accuracy figure; that nothing like this
  exists (kits and list-to-cart services do).
- **First twenty seconds of the pitch**: "Every August a teacher writes a list. Twenty-five families
  guess. Here the list itself shops, and buys nothing it cannot quote."

## Amendment 13:40 — the demo's examples are decided (the builder: "your choice", after a blind pick)
A blind judge, given all four examples neutrally and no files, ranked them: home after surgery, class
list, teenager, plumber. Its reason: "the therapist knows the patient, the daughter knows the house, the
store knows the product": it is the only example where nobody can name the right product alone, because
the rule-writer has not measured the house. The earlier confusion came from the telling (six items, a
sum, a screen of dots), not from the case.
- **Lead: sheet 4, "Home after surgery", short** (`sheets/sheet4.json`, `sheets/sheet4_order.txt`). Three
  items from sheet 1 with the same line and limit ids: shower chair (holds 300 lb; fits inside the tub),
  walker (holds 300 lb; passes the bathroom door), grab bar (holds 300 lb; at least 16 in long; bought
  through the cart). It names `"data_from": "sheet1"`: it uses sheet 1's fetched pages, readings and store
  answers and fetches nothing. Found in the live data at 13:27: seventeen grab bars cheaper than the pick
  are rejected, among them a $16 suction handle whose page states 75 lb; a bathing stool states its width
  with no unit (unclear).
- **Second, about 15 seconds: sheet 3, the teacher's class list**, for one finding (headphones that state
  a level above 85 dB, and a brand that states none) and to show the same engine runs any list. No
  signing in this part of the demo. The each-family arrangement (the teacher signs the list once, each
  parent signs their own purchase) is said aloud as what comes next; it is not built today.
- **Not shown**: sheet 2 (the plumber) and the six-item sheet 1; both stay in the repo with their tests.
- **Work.** ENGINE: `data_from` in the one path rule; sheet 4 read from sheet 1's data with its own order
  document; a laptop-only way to switch the running sheet (`POST /api/admin/use-sheet`), which resets the
  run and starts a new receipt chain. SIGN: Senso's order document for sheet 4; one phone rehearsal on
  sheet 4. SCREEN: a quiet sheet switcher in the top bar. STORE: tables, SQL, ledger and carts follow
  sheet 4 through `data_from`. The integrator switches main to sheet 4 when it holds.
- Also in this commit: `figures` for sheet 1 in the order's words (E18), and `"several": "largest"` on
  sheet 2's flush limit, as ENGINE asked.
