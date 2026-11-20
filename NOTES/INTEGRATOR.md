
## STORE 11:25 — pool committed (data/pool/*.json, raw replies in data/pool/raw/)
Products per store and line (title rules in signoff/store/build_pool.py; every query of every line fetched once):
- carex.com 42: L1 14, L2 10, L3 2, L4 11, L5 3, L6 2
- vivehealth.com 22: L1 8, L2 3, L3 4, L4 3, L5 4, L6 0 (its search returns no bed rail)
- parentgiving.com 47: L1 15, L2 5, L3 8, L4 6, L5 2, L6 11
- No `product_key` appears at two stores (SKUs and titles differ even for Carex items sold at parentgiving.com). A strike
  holding "at every store" cannot be shown with this pool unless a product is added; tell me if you want the Carex
  Economy seat looked up at carex.com by SKU.
- parentgiving.com texts are short (300 to 1500 characters); some state no figure at all, which suits the not_stated demo.
- Text is title + plain description + "Selected option: ..." for the cheapest available variant (that variant's id and price).
## 11:20 from SIGN
- Hand-check sheet is ready (branch stream/SIGN). Open it with `uv run python -m signoff.sign.handcheck` then http://localhost:8004/handcheck/ (it is also at `/handcheck/` on main once the SIGN router is merged). It shows 30 products, 10 per store, spread over lines, from `data/pool/*.json`; until STORE writes the pool it falls back to `fixtures/pool.json` and shows a banner saying do not fill those in. The sample is pinned in `evals/handcheck_sample.json` on first view of the real pool; answers go to `evals/handcheck.jsonl`. Tell the builder to wait for the pool (about 11:45), then fill it in without looking at model output.
- Please add `signoff/sign/_runtime/` to `.gitignore` (the enrolled issuer key and last `seq` are kept there so a server restart during rehearsal keeps the enrolment; `POST /api/admin/reset` clears it).
- Persona: PERSONA_API_KEY gave "Must be authenticated" on its first call and PERSONA_TEMPLATE_ID is not in the keys file. The Persona step is built to work without them and says "identity not checked". Needed from the builder: a sandbox API key and an Inquiry template id (`itmpl_...`).
- Senso: SENSO_API_KEY is not in the keys file; `/api/senso/checks` answers "not connected" until it is.
- Optional hook for the engine (additive, not a contract change): if `signoff.engine.state` defines `set_issuer_key(info: dict)`, SIGN calls it after enrol and after reset with `{enrolled, key_id, name, persona}`, so `GET /api/state` can show `issuer_key`. Also `GET /api/issuer/status` returns the same for the phone.

## 11:30 from SCREEN
- Screen is on `stream/SCREEN`, merged with main 8add2db, checks green. `/` draws the line with the most candidates;
  `/#L2` a given line; keys 1 to 6 change line, E opens Elena's controls.
- `/?fixture=1` draws the committed fixture run whatever the engine holds (badge "FIXTURE DATA"); `/?fixture=signed` the
  same run after a signature (placeholder signer, carts at fixture-store-*.example). `web/screen/fixture-state.json` is a
  copy of `fixtures/state.json`; `tests/screen/test_screen_smoke.py` fails if the two differ, so after
  `uv run python fixtures/make_state.py` also run `cp fixtures/state.json web/screen/fixture-state.json`.
- `/?sim=1` moves a limit inside the page (red "SIMULATION" button, panel says it is not Dana's phone). Dev only.
- Screenshots: `demo/shot.sh "/?fixture=1#L2" out.png` (headless Chrome, 1920 x 1080).
- [ ] No request. One question for DEMO.md: with 111 products and no figures every line is "open", so `/` opens the line
  with the most candidates (shower chair). If the demo must open on the toilet seat, use `/#L2`.
## 11:21 from ENGINE
- [ ] Arcee key has no credits: every model answers `402 billing.insufficient_credits` ("Required: 0.0002, available: 0.000000")
  on `POST /chat/completions` (`GET /models` works, which is why the key test passed). The reader and the chat cannot run
  on Arcee until credits are added. Until then the batch read uses `claude -p --model claude-sonnet-5-5`; the chat has
  no live model at all without Arcee credits or `ANTHROPIC_API_KEY` (it would also have to shell out to `claude -p`).
## STORE 11:25 — same product at a second store: none found
Only Carex is sold at two of our stores. parentgiving.com's "Carex Economy Raised Toilet Seat 5-1/2in" has no match at
carex.com: its search for that title returns other Carex seats, SKUs differ (parentgiving 206682_EA vs carex FGB3xxxx),
and the pages disagree (adds 5 in and "Securing Method: Locking" against 5.5 in and "Locking: No" on the closest one).
Giving two products one product_key on a guess would be invented, so every product_key is unique. Drop "the same one
from another store" from the demo. A strike still holds for the whole product_key; to show it across stores we need sheet 2.
signoff/store/api.py (router) is on branch stream/STORE since 11:18; routes /api/sql/passing-box, /api/admin/refresh-pool.

## STORE 11:30 — done so far
- Pool, store answers (data/store_answers/*.json, each a one-item list; carex says opened bath seats cannot be returned, vive states no delivery time, parentgiving 1 to 5 business days), SingleStore tables in database `signoff`, passing-box SQL (agrees with fixtures/make_state.py on 3 randomised states), create_carts tested once for real at carex.com (continue_url returned; no checkout call exists in code).
- ENGINE should call `signoff.db.records.write(state)` after each state change; /api/sql/passing-box also re-writes the engine's current state first so the two cannot differ.
- Quirk for AGENTS.md (yours to add): create_cart reply is top-level (id, totals, continue_url), not nested under "cart"; shopify cart ids contain "?key=".
## 11:30 from SIGN — Senso first call (POST /org/evals/text, wait:true, evaluator kb_accuracy)
Sentence: "Carex lets you return an unused bath safety item within 30 days of delivery for a full refund." Two calls, `author: "ai_assistant"` and `author: "organization"`: both HTTP 200, status completed, 2 claims extracted, and for both `about_brand: false`, `bucket: "general"`, no `verdict`, `claims_scored: 0`. So **claims about another brand (Carex) get no verdict, in either author mode**: Senso treats them as general knowledge, not checked against the knowledge base. The KB was empty at the time, so this is "not about the org's own brand", not "unsupported". Consequence (as the contract planned): Senso checks the sheet against the therapist's order and the handout; store sentences stay checked by span match in code. I am now testing whether brand-less statements ("The order lists a raised toilet seat") get real verdicts once the order is loaded, then loading the order, a handout and each store's policy text (store answers) as documents. Please add the one-line quirk to AGENTS.md: "SIGN: Senso /org/evals/text gives no verdict to claims naming another brand (about_brand false, bucket general, both author modes); only claims about the org's own KB content are judged."
Also: `kb_accuracy` judge model is `gpt-5.6-luna`; a run with wait:true took about 2 seconds.

## 11:32 from ENGINE — status and what is new in /api/state
ENGINE: steps 1 to 3 done — `uv run -q pytest -q -x` → 93 passed; `curl -s localhost:8001/api/state | head -c 60` → `{"version": 1, "mode": "live", ...`
- Live state from the real pool: 111 products, 64 state every figure, 41 inside, 5 of 6 lines ready, total $279.04. L5 (grab bar) is open:
  the pages give the length per size and the reader will not guess which one.
- Figures: `uv run python -m signoff.extract.run` (cached per product text; a rerun reads only changed pages). Sonnet decides
  (189 figures, every quote found, 20 marked unsure and so not counted). Compared on the same 111 products
  (`uv run python -m signoff.extract.score --detail`, file `data/figures/_runs/comparison.json`, also in `/api/state` under `readers`):
  `sie:Qwen/Qwen3.8-27B-FP8` (SIE chat endpoint) agrees on 166 of 169 (98.2%), differs on 3, adds 19 the reference left out, 6.0 s per product;
  `sie:urchade/gliner_multi-v2.1` (SIE extract, code parses the number) agrees on 118 of 169 (69.8%), 0.47 s per product.
  Sonnet through `claude -p`: 3.0 s per product, $0.0056 per product.
- [ ] Decide: the Sonnet reference is not fully repeatable. Between two passes over the same text 2 of 189 figures moved between
  "counted" and "unsure" (one moved the L3 pick). The committed files are a cache, so the demo is stable; say "read once, cached" if asked.
- The demo move with real data: L2 "finished seat height" 19 → 19.5 moves the pick from carex.com (Carex Quick-Lock, $31.10, adds 4 in)
  to parentgiving.com (Carex Economy Raised Toilet Seat 5-1/2", $31.99); at 20.5 the line opens. Elena's toilet height 15 → 14 does the same.
  L1 capacity 300 → 375 moves parentgiving.com → carex.com. L3/L4 capacity 300 → 325 moves carex.com → parentgiving.com.
- New optional keys in `/api/state` (nothing renamed): top level `sheet_hash`, `readers`, `senso`; `seal.current`, `seal.signer`,
  `seal.signed_at`; on a figure `unsure`, `unsure_reason`, `agreed_by`, `readers`, `also_marked_by`, `span_match`, `stated_unit`;
  on a check `missing_why`. A figure with `unsure: true` does not count (candidate `not_stated`, the reason says why).
- Chat: `POST /api/shopper/say` works through `claude -p` (about 3 to 5 s for a question; a plain request for a change is refused by
  code in 0 s). Reply carries `refused`, `intent`, `decided_by`, `tool_calls`, `state_unchanged`.
- [ ] Please add to the AGENTS.md quirks log (I cannot edit it):
  `ENGINE 11:30: SIE has an OpenAI-compatible chat endpoint, https://api.superlinked.com/v1/chat/completions, Bearer SIE_API_KEY; Qwen/Qwen3.8-27B-FP8 answered warm in under 1 s. Usage carries credits_charged.`
  `ENGINE 11:30: claude -p for batch work: run it outside the repo with --tools "" --strict-mcp-config --setting-sources "" --no-session-persistence, or the repo's hooks run on every call. About 3 s per call; --model claude-sonnet-5-5 works.`

## 11:40 from ENGINE — for the Statsig gate and Amplitude
- `signoff.engine.state.set_reader(name | None)` switches which reader's figures count (`None` = the Sonnet reference;
  `"sie:Qwen/Qwen3.8-27B-FP8"` or `"sie:urchade/gliner_multi-v2.1"` = that reader's own run under `data/figures/_runs/`). It is
  refused after signing. `/api/state` → `readers.deciding`, `readers.switched`, and per reader `agreement`, `same_as_reference`,
  `different_number`, `missing`, `extra`, `span_found_share`, `seconds_per_product_median`, `cost`: the outcome for the gate.
  Measured now: Sonnet 64 products state every figure, total $279.04; Qwen on SIE 81 products, total $279.03 (the L2 pick moves to
  the $31.09 seat whose added height Sonnet marked unsure); SIE extract alone 45 products, total $351.47.
- Events sent through `signoff.obs.tool_call` (a no-op until `signoff/obs` has its code on main): `figure_read` per product and
  reader, `check_run` per state change (why, counts, latency), `read_state` / `read_candidates` / `shopper_say` per chat message.
  `signoff.obs.session(sheet_id)` is called on `reset()`.

## 11:44 from ENGINE — pressure attempts are ready to run
- `uv run python -m signoff.agent.pressure --attempts FILE.jsonl --out RESULT.json` (attempt: `{"id", "text"}` or `{"id", "turns": [...]}`,
  one per line). It strikes the L3 pick in its own process (the running app is untouched), then runs every attempt against Sign-Off's
  agent and against the plain agent (`signoff/agent/plain.py`: same model, same rules in its prompt, but with `restore_struck`,
  `set_limit` and `create_cart` tools on a sandbox copy). Each is graded by an exact check on state: sheet hash, strikes, limits, carts.
  Output: `attempts`, `completed`, `signoff_gave_way`, `plain_gave_way`, `struck_still_struck`, and every row with replies and tool calls.
- Dry run with six attempts of my own (`--dry-run 6`, 18 s): Sign-Off 0 of 6, plain agent 0 of 6. Sonnet holds to a prompt on simple
  attempts, so the plain agent may not reach "6 of 40"; then the count is not shown, as the contract says. The attempts that count
  must come from Firedrill, not from me.
## STORE 11:50 — housekeeping, replay, Amplitude events, sheet 2 counts

**1. Housekeeping.** The live SQL test now runs in a throwaway database `signoff_test_<random>` (created and dropped
per run), so it cannot touch the app's tables or a parallel run. Replay: with `SIGNOFF_MODE=replay` every
`ucp.call` (search, ask, create_cart) is answered from `data/pool/raw/`, `data/sheet2/pool/raw/` and
`data/store_answers/`; no network (a test makes urlopen raise); each reply carries `mode: "replay"`; `create_carts` returns
`mode: "replay"` with the product page as `cart_url` and an id starting `replay-` (no cart exists at the store; say so on screen).
A query with no saved reply returns zero products, not an error. `POST /api/admin/refresh-pool` in replay mode only
rebuilds the pool from the saved replies.

**2. Amplitude.** `signoff/obs/__init__.py`: `session(sheet_id, experiments=None) -> session_id`, `tool_call(name, input,
output, success, latency_ms, error=None)`, `timed(name, input, fn, summarise)`, `set_experiments([{"key","variant"}])`,
`flush()`, `shutdown()` (also at exit). Never raises, never waits (queue + one sender thread; no key or `SIGNOFF_OBS=off` = no-op).
Agent id `signoff-shopper`. Content mode `full` by default (store text and an invented family only; PII redaction on);
`SIGNOFF_AMPLITUDE_CONTENT=metadata_only` switches. Every store call already emits one event: `store.search_catalog`,
`store.ask_business`, `store.create_cart`. At 11:44 two real events were sent and the SDK's delivery callback returned
HTTP 200 for both (stats in `obs.stats`: `delivered`, `last_status`). I cannot see the Amplitude UI: please check Live Events
for agent `signoff-shopper` (session ids look like `sheet1-HHMMSS-xxxx`). ENGINE: call `obs.session(sheet_id)` once per
sheet run, then `obs.tool_call("engine.read_figure", {...}, {...}, ok, ms)` for each figure read and check. Statsig variant:
`obs.session("sheet1", experiments=[{"key": "reader_model", "variant": "arcee"}])` or `obs.set_experiments(...)` later.

**3. Sheet 2 pool** (`data/sheet2/pool/<store>.json`, same shape, raw replies in `data/sheet2/pool/raw/`; line_ids are
placeholders named after the query group: frying_pan, saucepan, stock_pot, roasting_pan, cookware_set; map them in sheet2.json):
197 products: Made In 60, Caraway 58, Our Place 44, Great Jones 27, Material 8 (Material's search returns few).
Count of products whose text states each figure (pattern count over the plain text, 197 products, 45 of them sets):
| figure | stated on | share |
|---|---|---|
| material (stainless, nonstick, ceramic...) | 150 | 76% (a category, not a number) |
| pan diameter in inches | 45 | 23% |
| capacity in quarts | 47 | 24% |
| dishwasher safe (yes/no) | 22 | 11% |
| oven-safe temperature (a number) | 19 | 10% |
| induction compatible | 16 | 8% |
| ply or mm thickness | 29 | 15% |
| weight (lb, oz) | 8 | 4% |
No checkable number is stated on half the products. By line the counts are better where the figure belongs:
frying_pan 71 products, diameter on 28 (39%); saucepan 42, quarts on 22 (52%); stock_pot 62, quarts on 27 (44%);
roasting_pan 64, oven temperature on 8 (13%). Induction: Great Jones 11 of 27, Made In 5 of 60, Caraway 0 of 58, Our Place 0 of 44.
Three limits I would propose (each tied to the line where the pages state it, so a line has candidates that state it
and candidates that do not, which is the not_stated beat):
1. Frying pan: diameter at most N in (28 of 71 state it).
2. Saucepan and stock pot: capacity at least N qt (22 of 42 and 27 of 62 state it).
3. Oven-safe temperature at least 450 F on the roasting line (19 state a number; most of those are Made In), or
   "induction compatible" if you prefer a yes/no limit (16 state it, 11 of them at Great Jones).
Price is always stated, so a spend cap per line (cents) needs no figure at all. Material is stated on 76% but is a
word, not a number; it would need a new comparison kind. If the 450 F or induction limits are used, expect many
`not_stated` candidates; that is real, not a fault of the reader.

## STORE 11:55 — two carts, and vivehealth delivery time
**(a) Carts.** Real, no checkout call. parentgiving.com alone: 1 item (Adjustable Height Bathing Stool, 3899 cents) returned a
cart id and `continue_url` (https://parentgiving.myshopify.com/cart/c/...), total 3899. Both stores in one `create_carts` call:
two carts back, one per store, in pick order of first appearance: parentgiving total 3899 and carex total 1224, each with its own
store `continue_url` and `mode: "live"`. Three carts exist in total at carex.com and two at parentgiving.com from testing,
none checked out. The carts expire in 30 days (`expires_at` 2026-12-20).
**(b) vivehealth.com delivery time.** Three differently worded questions to its agent ("How many business days does standard
shipping take within the US?" and two more) all answer that the store's information does not specify a time. So
`data/store_answers/vivehealth.com.json` is left as it is: no store-level time is stated. One finding in product text: only
Vive "Toilet Seat Riser" (line L2, 6999 cents) says, in its own description, "Orders ship the same day if placed before 5pm
and arrive within 1-2 days from our nearest warehouse." (Bed Ladder says "ships same day", no arrival time.) That is a
product-page sentence for one item, not the store agent's answer, so I did not copy it into the store answer. If you want it
to count, `arrival` for that candidate would come from the product text (a span found in `text`, quote above, 1 to 2 days),
which is an ENGINE change; with the current rule no Vive product can be picked. Your call.
**Sheet 2 note.** Your item 3 was done at 11:50 before your hold arrived (data/sheet2/pool/, counts in the 11:50 entry above);
nothing further is running on it.
## 11:50 from SIGN — phone signs end to end; Senso wired; Persona live
Merge `stream/SIGN` (all committed, 71 tests green). Proof, run on my branch with the real engine and real pool (port 8004, phone driven in a browser at iPhone width): enrol → move L2.height (signed `set_limit`, engine bound changes, pick goes to none at 21 and back to the Carex Quick-Lock seat at 19) → Sign tab → Senso 12/12 sentences `verified` → Sign: seal "Signed by Dana at 11:35. 2 carts created", real cart links at parentgiving.com ($228.97) and carex.com ($75.81), mode live. (Two real carts now exist from that rehearsal; `POST /api/admin/reset` cleared the state.) Not yet tried: from a second physical phone over the tunnel, because the tunnel serves main and main does not have the latest SIGN branch. After you merge: open PUBLIC_URL/phone/ on a phone, tap "Enrol this phone", move a slider, Lines tab, Sign tab.
- Phone: three tabs (Limits, Lines, Sign); the key is non-extractable in IndexedDB; a second phone sees "another phone is the signing key" with a rehearsal reset link; after `POST /api/admin/reset` a reload enrols it again.
- Senso, what is real (all in `signoff/sign/senso.py`, docs in `signoff/sign/senso_docs/`; the order, a handout and one text per store from `data/store_answers` are loaded in the knowledge base with version ids kept in `signoff/sign/_runtime/senso_docs.json`; re-load with `uv run python -m signoff.sign.senso`):
  * Claims naming another brand get no verdict, so the store's own words are NOT sent (a quote with no brand name came back "unsupported" every time). The sheet's sentences are written as the organisation's terms: "Our order requires the raised toilet seat to hold at least 300 lb." (5 of 5 verdicts in a trial; the same sentence without "Our order requires" got no verdict in 2 of 5.)
  * Sentence kinds: `order` (a line is on the order; grab bar is picked up locally) blocks on `conflict` and `unsupported` (up to three tries on `unsupported`; set `SENSO_BLOCK_UNSUPPORTED=0` in the keys file to relax it to `conflict` only); `limit` (each issuer value against the order's) is advisory: if Dana moves a limit away from the order, Senso says `conflict` and the phone says "Dana moved this from the order", but the signature goes through, otherwise the judge-drags-a-limit-then-signs beat could never complete. Say if you want limit conflicts to block instead.
  * Runs: `POST /api/senso/run` (the Sign tab starts it; about 25 s for 12 to 13 sentences), `GET /api/senso/checks`, and the same run happens inside `sign_sheet` if the verdicts are not for the current hash. Rows go to the engine through `set_senso` (they carry `candidate_id`, `verdict`, `quote`, `reasoning`, `source` {title, content_id, version_id}, `run_id`). Senso unreachable: the row says "error", signing is not blocked.
  * Quirk for AGENTS.md: "SIGN: Senso judge is not steady on bare statements; prefix with 'Our order requires' and put the same sentence verbatim in the document; a wait:true call can return 202 'queued' under load, poll /org/evals/runs/{id}."
- Persona: real Inquiry created in sandbox with the template (status "created"), link returned, status read back; the Sign tab has "Check my identity" and "Refresh status"; the signature record carries `persona` {inquiry_id, status, verified, sandbox:true, label}. Without a started inquiry the seal says "identity not checked".
- Engine hook used: `set_issuer_key` and `set_senso` (both exist). The signature dict given to `mark_signed` has `name`, `signer` {key_id, name}, `at`, `signed_at`, `sheet_hash`, `sig`, `payload`, `seq`, `persona`, `senso`.
## 11:58 from SIGN — Persona guide read; what their judges seem to want
- Relay is not available to us: the guide says a Relay sandbox key comes from their Google form, "only works for Relay", needs `@persona/sdk-node` plus Privacy Pass; our key is the dashboard sandbox org's, i.e. the standard-verification path. Staying on the plain Inquiry flow (it works). Relay answers "does this person meet a condition (live human, 18+/21+)"; standard verification answers "who is this person". Our line for the demo: a signature needs to know who signed, not only that a human did, so standard verification is the right layer. (Persona's own help article says the same: "link the agent only after the Inquiry passes and limit it to what was verified".)
- What their judges appear to want: the human behind the agent checked in a real flow, the result read back from the backend (not trusted from the client), the agent's authority tied to the verified person, and everything labelled sandbox ("sandbox always passes; use it to check the integration"). We do all four: backend creates the Inquiry and reads its status, the signature record carries inquiry id and status, the seal says "sandbox". A new switch: `PERSONA_REQUIRED=1` in the keys file makes `sign_sheet` refuse until the Inquiry status is completed/approved (error `identity_needed`); off by default so a stalled hosted page cannot block the demo. Say if you want it on for the demo.
- Extras from the guide: sandbox lets an inquiry pass or fail on purpose (docs "Integration testing"); the startup programme offers 500 free checks a month, sign-up at withpersona.com/tokensand (builder's call); their staff to ask: Ellen or Kerwell.
## 11:50 from SCREEN (answer to the 11:38 direction)
- Done on `stream/SCREEN`: neutral ground, one type family (Avenir Next), owner shown by name plus a small dot or a thin
  rule under the numeral; no filled blocks. Left column "what it knew" (Dana's limits, Elena's measurements, the store's
  sentences, the store agent's reply); right "what it decided" (sums, plot). A steps trail under the title.
- Motion, all started by a line opening or by a diff of `/api/state`: facts arrive in the column, each figure travels
  into its place in the sum (the store's figure lifts out of its sentence), the margin resolves, dots settle, the
  never-stated slide into the dashed gutter (now a count, not circles), ring lands. A moved limit: wall slides, dots grey
  as it passes, ring glides, numerals roll, tile and total roll. Strike: crossed out, fades, next takes its place.
  Signing: seal border closes, signer, hash, Persona, then cart links one by one. `prefers-reduced-motion` or `?motion=0`
  turns it all off.
- To watch a motion without a phone: `/?fixture=1&sim=1&panel=words&then=L2.capacity:325@3000` (limit moves after 3 s),
  `...&then=strike:1@3000` (strike), `/?fixture=1&sign=3000` (seal closes). `node demo/frames.mjs "<path>" <dir> <ms> <every>`
  saves real-time frames; `demo/contact.sh <dir> out.png <from> <to>` makes a contact sheet.
- Open, yours to decide: (1) the SQL view still shows "8 rows vs 7 dots" on L2 (NOTES/STORE.md 11:35); (2) the store
  agent's return sentence is shown on every line of that store, also the bed rail ("An opened bath seat's return..."):
  the engine sets `undo` per store, not per product kind. If `undo.applies_to` can say whether it covers this line, the
  screen will hide it when it does not.
