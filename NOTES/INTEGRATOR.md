
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
