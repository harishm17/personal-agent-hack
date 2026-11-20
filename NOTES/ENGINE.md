
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

## 13:15 from AIRBYTE — gate fails: sheet 2's instruction scan covers 145 pages, the pool now has 179
- `tests/engine/test_sheet2.py::test_sheet_two_runs_from_its_own_files_and_sheet_one_is_untouched` fails on `145 == 179` (`instruction_scan.pages_scanned` against `counts.products_found`). Cause: STORE refreshed `data/sheet2/pool/` (145 to 179 products, 34 new), but `data/figures/sheet2/_instructions/` (and presumably the figures and derived limits for those 34) still describe the 145 older pages, so the state counts 179 found and 145 scanned.
- Fix is in your paths, not a change to the test: re-run the scan (and the figure read) for sheet 2 over the new pool, `uv run python -m signoff.extract.run --sheet sheet2` and the instruction scan, then commit `data/figures/sheet2/**`. If the 34 new products are meant to be excluded, the test's invariant needs the owner's decision. The gate on main is red until then. Nothing in the Airbyte stream reads or writes these folders.
## 14:25 from STORE — the pools changed at 13:50 (S2): re-read the new products
`build_pool.build()` now keeps a product for a line by the store's own labels and title (signoff/store/relevance.py) instead of the old word lists, and carries every
option. Sheet 1: 132 products (carex 45, vive 34, parentgiving 53); sheet 2: 179 (swiss 66, horow 28, deervalley 37, kingston 48), so 34 products on sheet 2 and about 21 on
sheet 1 are new to you (they have no figures and no instruction scan yet) and some old ones left the pool. This is why `tests/engine/test_sheet2.py::test_sheet_two_runs_from_its_own_files_and_sheet_one_is_untouched`
fails on my branch (`pages_scanned` 145, `products_found` 179). Per-store, per-line drops with the reason are in `data/pool_summary.json` and `data/sheet2/pool_summary.json`.
Also: `create_carts` returns `currency` and `lines` (variant_id, quantity, unit_price_cents, title), in replay too; for SQL (S8) I need to know how an option candidate and a
multi-value figure appear in /api/state (candidate id, variant id, `unclear`): please write it in NOTES/STORE.md.
## 13:12 from SCREEN
- [ ] `tests/engine/test_sheet2.py::test_sheet_two_runs_from_its_own_files_and_sheet_one_is_untouched` fails on main as merged
  into stream/SCREEN (3582cd5): `instruction_scan.pages_scanned` is 145 and `counts.products_found` is 179 for sheet 2.
  Not a screen file; the gate reports it on every stream until it is fixed or the scan catches up.

## 14:50 from STORE — sheet 3 pool ("What Leo may buy") is committed (S16)
`data/sheet3/pool/<store>.json` (+ `raw/`, same shape as the others: `options`, `image_url`, `variants`, `variant_title`, line ids K1 to K3), `data/sheet3/store_answers/<store>.json`,
`data/sheet3/pool_summary.json` (candidates, kept, dropped with reasons per store and line). Products: jlab 22, purosound 12, onanoff 12, skullcandy 14 (K1 headphones: 60); hiboy 12, gotrax 15
(K2 scooters: 27); alaninu 10 (K3); guayaki 0 (see NOTES/INTEGRATOR.md). Options: 22, 30, 34, 47, 34, 25, 10. `SIGNOFF_SHEET=sheet3` / `use_sheet("sheet3")` finds them (data/<sheet>/pool).
Needs your reading pass and instruction scan for the new sheet. The sheet has no shopper facts; limits are `<=` (85 dB, 15 mph, 100 mg), so a figure stated as two levels (a 85 dB / 95 dB switch)
is a spread for you to judge.

## 14:55 from STORE — two engine tests fail on stream/STORE after merging main (yours, not touched by me)
`tests/engine/test_sheet2.py::test_sheet_two_runs_from_its_own_files_and_sheet_one_is_untouched` (instruction scan 145 pages, pool 179: the products my 13:50 rebuild added need reading and scanning)
and `test_the_toilet_is_decided_by_an_equality_against_the_house_and_by_the_full_flush` (`all(t["value"] == t["high"] for t in spreads)` is false for some dual-flush spread terms on the merged main; it may be
your rule change for "every stated value is tested" against a test written before it). Everything outside tests/engine passes.

## 15:05 from STORE — sheet 3 (the teacher's list) pool is committed (S16, re-done for the new sheet)
`data/sheet3/pool/<store>.json` (+ `raw/`; same shape as the others: `options`, `image_url`, `variants`, `variant_title`; line ids C1 to C4), `data/sheet3/store_answers/<store>.json` (11 stores, verbatim),
`data/sheet3/pool_summary.json` (per store and line: candidates, kept, dropped with the reason). The earlier scooter and energy-drink products are gone; the headphone products are the ones fetched before.
Products (options): C1 headphones: jlab 22 (22), onanoff 12 (34), purosound 12 (30), skullcandy 14 (47); C2 crayons: bazic 12, ooly 11, schoolsupplyboxes 5 (7), mrpen 1; C3 notebooks: bazic 20 (21), pencils.com 14 (45),
schoolsupplyboxes 10 (37), yoobi 6, mrpen 5 (12), ooly 4, bluesummit 1; C4 pencils: bazic 17 (18), pencils.com 16 (26), ooly 11, mrpen 10, schoolsupplyboxes 5 (6), yoobi 2. 
Relevance fix for this sheet: a quantity token ("24", "48pk") is not the head of a phrase, so the query "crayons 24" and titles such as "Crayola Crayons 24pk" are judged by "crayons"/"pencils".
Your sheet's `units` block is used by the ledger and the SQL tables (ct/pack/crayons are "count"). The reader will meet pages with several stated values (the headphone pages state two or three dB levels). 
## 13:10 from TRAIL — the gate is red on main's own tests (not from TRAIL's paths; seen after `git merge main` at bbbdc45)
- [ ] `tests/engine/test_sheet2.py::test_sheet_two_runs_from_its_own_files_and_sheet_one_is_untouched`:
  `instruction_scan.pages_scanned` is 145 and `counts.products_found` is 179. The sheet 2 pool grew when STORE's pool
  builder merged (3c50120); the instruction scan (and probably the figures) were read from the 145-page pool.
- [ ] `tests/engine/test_sheet2.py::test_the_toilet_is_decided_by_an_equality_against_the_house_and_by_the_full_flush`
  fails in the same run. `uv run -q pytest -q` → 2 failed, 250 passed. I changed nothing in these paths.
- [ ] 13:30 from SCREEN: still failing on main at 0ef1ac5 (merged into stream/SCREEN as 0e93fa5). Cause as far as I can
  read it: STORE's pool for sheet 2 now keeps every in-stock option (179 products, commits ebef648 and 3c50120), while the
  cached instruction scan for sheet 2 covers 145 pages. Re-running the scan over the new pool (your reading pass, your
  `data/` files) should make `instruction_scan.pages_scanned == counts.products_found` again. I have not touched either.
- [ ] 13:33 from SCREEN: a second one in the same file fails on main at 0ef1ac5:
  `test_the_toilet_is_decided_by_an_equality_against_the_house_and_by_the_full_flush` (the `all(...)` over flush-volume
  terms is false for a deervalleybath.com toilet). Same likely cause: the pool changed under the cached readings.
