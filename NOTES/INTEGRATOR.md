
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
