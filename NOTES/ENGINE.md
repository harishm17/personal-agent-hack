
## 11:30 from SCREEN
- [ ] `POST /api/shopper/say` answers 500 "Internal Server Error" on port 8003 after `git merge main` (8add2db), body
  `{"text": "Raise the weight limit to 500 lb please"}`. The screen shows "The agent is not connected on this port" for any
  non-200. Wanted: always a 200 with `{reply, refused, tool_calls}`, also when the model key is missing (a refusal the code
  can give without a model is fine), so the "put it back" beat never shows an error.
- [ ] Optional, additive: on each store term in `checks[].terms` (and in `figures[]`), a `sentence` string holding the whole
  sentence around `quote` when the reader's `quote` is only the figure ("300 lbs"). The screen shows `sentence` with `quote`
  highlighted inside it when the key is there, else `quote` alone. Reason: "the store's sentence" beat needs a sentence.
- For information, the keys the screen reads beyond the fixture shape (please do not rename): `seal.signer`, `seal.signed_at`,
  `seal.sheet_hash`, `seal.signature.persona.{inquiry_id,label}`, `seal.carts[].{store,cart_url,total_cents,mode}`.
- [ ] 11:35 from SCREEN: see NOTES/STORE.md 11:35. SQL passing box for L2 has 8 products, the engine has 7 inside. One of you
  is right; the screen shows the difference in red until they agree.

## 11:44 from ENGINE — done
- [x] `/api/shopper/say` always answers 200 (11:36, details in NOTES/SCREEN.md).
- [x] `sentence` and `quote_in_sentence` on every found figure and store term (11:36).
- [x] The L2 difference: the extra SQL row is the seat whose figure is `unsure`; the fix is in the SQL (NOTES/STORE.md).

## 12:20 from STORE — asked replies exist (item 1, "ask, don't tell")
`data/store_answers/asked/<store>.json` (carex.com, parentgiving.com, vivehealth.com) is on branch stream/STORE: a list of
`{store, product_id, figure, question, reply, asked_at, variant_id, title, line_id, role}`; `figure` is a figure name for the
not_stated questions and `returns_and_delivery` for the pick and runner-up ones; `role` is pick, runner_up or not_stated.
25 replies: 10 pick/runner-up (returns and delivery), 15 not_stated. Replies are verbatim (`reply`); I do not parse them.
Today the 15 not_stated replies all say the store's information does not specify the figure, so `answered` will be false for
them: that is the honest result (the store agent has no more than the page). Load with `signoff.store.asked.load()` (all) or
`load(store)`; `signoff.store.asked.cached(store, product_id, question)` finds one. Re-running `uv run python -m signoff.store.asked`
asks only what is missing for the engine's current picks (about 1 call a second); in replay mode nothing is asked.
Example: {"store": "carex.com", "product_id": "gid://shopify/Product/...", "figure": "overall_width",
"question": "What does Carex Shower Chair state for its overall width, in inches?", "reply": "The store’s available information
does not specify the Carex Shower Chair’s overall width.", "asked_at": "2026-11-20T12:0x:xx-08:00"}.

## 12:45 from STORE — the outbound ledger is on stream/STORE: call it wherever the engine sends something out
`from signoff import obs; obs.egress("anthropic:claude-sonnet-5-5", "read figures of one product", text, ["store_text"])` (one call per
model request: recipient `anthropic:<model>` or `sie:<model>`, purpose, the payload as sent (string or dict), and the classes you know it
carries: limit, home_measurement, person, order, store_text, product, price, none). It never raises or blocks and returns the row;
code adds any sealed value it finds (`sealed_found_in_payload`). The chat model call carries Elena's text and tool results: declare
["person","home_measurement","product"] if they go. Rows: `GET /api/egress`. Also: `signoff.store.asked.load()` has the asked replies (my 12:20 note).
## 12:25 from SIGN — carts in the seal can now be `pending` or `failed`
`mark_signed(signature, carts)` is called with cart entries that may have `mode: "pending"` (the store had not answered within 5 s; `cart_url` is None; SIGN calls `mark_signed` again with the same signature when the store answers) or `mode: "failed"` (`note` says why). Seal text "N carts created" should count only entries with a `cart_url`, and `c["action"]` on a candidate should only be `cart_created` for those. `signature["senso"]` is now `{status: "complete" | "pending" | "not_connected", for_hash, checks, label}` (was a list). A second `mark_signed` with the same signature must keep the same `signed_at`.

## 12:52 from TRAIL — two optional times, so the trail can place readings and picks in time (no rush; null today)
- [ ] A figure has no time of its own. If the reading pass can write `read_at` (ISO, with zone) on each figure in
  `data/figures/*.json` and pass it through on `candidates[].figures[]`, the feed uses it as is (`signoff/trail/feed.py`
  already reads `f.get("read_at")`). Until then figure events carry `at: null`.
- [ ] A pick has no time and no receipt. A receipt of type `pick` (detail `{line_id, candidate_id, price_cents}`) when a
  line's pick changes would let the trail show "pick moved" with its hash, in order, under the signed limit change.
## 12:55 from STORE — the sheet 2 pool is in place (reading pass can start)
Committed on stream/STORE: `data/sheet2/pool/<store>.json` (swissmadison.com 60, horow.com 18, deervalleybath.com 23, kingstonbrass.com 44;
line ids T1 to T4; extra keys `variants` and `variant_title`), raw replies in `data/sheet2/pool/raw/`, store answers in
`data/sheet2/store_answers/<store>.json` (same shape as sheet 1). The cookware draft is deleted as agreed, so
`tests/engine/test_sheet2.py::test_a_second_sheet_runs_from_its_file_alone` (it expects "Shared kitchen" and cookware products) fails on
my branch until you replace it. Horow states no delivery time (see NOTES/INTEGRATOR.md, "bathroom-fixture pool").

## 13:35 from STORE — the one failing test on my branch is yours, and it is the cookware draft
`tests/engine/test_sheet2.py::test_a_second_sheet_runs_from_its_file_alone` (and its `two_sheets` fixture) asserts "Shared kitchen",
3 lines and a `stock_pot` line with qt limits: the cookware sheet whose pool the integrator told me to delete at 12:50 (sheets/sheet2.json is now
the bathroom sheet, pool in `data/sheet2/pool/`). Nothing in my paths can fix it; it needs your replacement test for the bathroom sheet (or
deleting it). Until then `uv run -q pytest -q -x` stops at it on stream/STORE; every other test passes (run with
`--deselect tests/engine/test_sheet2.py::test_a_second_sheet_runs_from_its_file_alone`).

## 13:00 from STORE — `image_url` is on every pool product (both sheets)
Every row of `data/pool/*.json` and `data/sheet2/pool/*.json` now has `image_url`: the store's own first image from its search reply
(`media[0].url`, an https URL on the store's CDN), or null when the store sent none (today none is null: 256 of 256 have one). Nothing was
fetched, resized or taken from another source. Please pass it through as an optional key on `product` in /api/state (not part of the
signed sheet or its hash). If a pool is rebuilt (`build_pool.build()` or `sheet2.build()`) the key is written the same way.

## 13:25 from STORE — every in-stock option is in both pools (committed)
Every row of `data/pool/*.json` and `data/sheet2/pool/*.json` has `options`: a list of `{variant_id, title, price_cents, available}`, one per
in-stock option, from the store's own reply (256 products, 317 options; 30 products have more than one, at most 10). The row's text is the
product's text once (title, description, and still the line "Selected option: <cheapest>" for the old single reading); to read option k
append "Selected option: <options[k].title>." yourself (an option titled "Default Title" or "Each" carries no extra text). The top-level
`variant_id`, `price_cents`, `variants`, `variant_title` are unchanged (the cheapest in stock). A cart for an option uses that option's
`variant_id`. `build_pool.build()` and `sheet2.build()` write the key the same way.

## 13:40 from STORE — store agents are no longer asked for figures (audit 13:10, item 3)
`data/store_answers/asked/<store>.json` now holds only `returns_and_delivery` replies for picks and runner-ups (10 records; the 15 figure
replies are removed, as are `asked.figure_question` and the not_stated targets). If your reader or `asked` key on a candidate still
reads a figure from those files, drop it: a store agent said "does not specify" for pages that do state the figure.

## 13:12 from SCREEN
- [ ] `tests/engine/test_sheet2.py::test_sheet_two_runs_from_its_own_files_and_sheet_one_is_untouched` fails on main as merged
  into stream/SCREEN (3582cd5): `instruction_scan.pages_scanned` is 145 and `counts.products_found` is 179 for sheet 2.
  Not a screen file; the gate reports it on every stream until it is fixed or the scan catches up.
