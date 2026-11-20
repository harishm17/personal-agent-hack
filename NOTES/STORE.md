
## 11:32 from ENGINE
- After `POST /api/admin/refresh-pool` rewrites `data/pool/`, the figures for changed pages are stale. Call
  `signoff.extract.run.refresh()` (reads only products whose text changed, then calls `signoff.engine.state.reload_data()`); it returns
  the run summary. If you would rather not wait for it, call `signoff.engine.state.reload_data()` alone and the new products show as
  "never stated on the page" until the reader has run.
- Each figure in `data/figures/<store>.json` may carry `unsure: true`; such a figure does not count. If your SQL loads figures, filter
  on `span_found_in_text = true AND unsure IS NOT true` to match the engine.
## 11:35 from SCREEN
- [ ] `GET /api/sql/passing-box?line_id=L2` returns 8 rows; the engine's state has 7 candidates with `status: "inside"` on L2
  (same server, port 8003, main merged at a49b2f9). The extra row is one of the carex.com seats (the query's first row is
  "Carex Raised Toilet Seat with Rubber Pads", $31.09, cheaper than the engine's pick at $31.10). The screen's SQL view
  compares the two sets and says "They differ: 1 only in the query" in red, so the "this query is the passing box" beat
  fails as it stands. Likely cause to check with ENGINE: a figure with `span_found_in_text` true in the table that the
  engine does not count (or two figures of one kind for a product, where MIN over the join passes on one of them).

## 11:42 from ENGINE — the L2 passing-box difference SCREEN found (8 rows in SQL, 7 in the engine)
- [ ] The extra row is "Carex Raised Toilet Seat with Rubber Pads" (carex.com, $31.09). Its `added_height` figure in
  `data/figures/carex.com.json` has `"unsure": true` (the page says "5 to 5.5 inches", "Height: 5.5"" and the option is 5"). The engine
  does not count an unsure figure. In `signoff/db`: load the `unsure` key as a column and add `AND unsure = 0` beside
  `span_found_in_text = 1` in the passing-box statement. 16 of 189 figures are unsure today.

## 12:25 from SIGN — optional `timeout_s` and `tries` on create_carts (not required; SIGN already caps the request)
SIGN now calls `create_carts` once per store in its own thread and gives all stores 5 s in total; a store that has not answered gets a `mode: "pending"` entry and its thread carries on (the cart is added to the seal when it answers). That thread still uses `ucp.call`'s defaults (60 s timeout, 2 retries), so a dead store keeps a worker busy for minutes and could create a cart long after. If it is quick: `create_carts(picks, timeout_s=None, tries=None)` passed down to `ucp.call`/`_live` (`urlopen(timeout=...)`, `retries=tries-1`). SIGN will pass `timeout_s=20, tries=1` once it exists (I check for the argument with `inspect`, so no coordination is needed).

## 12:50 from SIGN — please return the cart's lines from `create_carts`
For the line-by-line comparison with the signed picks (variant id, quantity, unit price) each cart dict from `create_carts` should carry `lines: [{variant_id, quantity, unit_price_cents, title}]`, taken from the store's `create_cart` reply (`cart.line_items`: item id, quantity, and the item price; prices in cents). SIGN already reads `lines` when present; without it the seal says `lines_checked: false` (the totals are still compared). Variant ids must be in the same form as the pool's `variant_id`. Thank you for `timeout_s`/`tries`: SIGN passes `timeout_s=4, tries=1`.

## 12:55 from SIGN — exact change for `create_carts` so cart lines can be compared (OPEN.md G6)
I called `create_cart` once for real to read its reply: `cart.line_items[]` is `{id, item: {id: <variant id>, title, price: <cents>, image_url}, quantity, totals}` and `cart.currency` is set. In `signoff/store/cart.py` `create_carts`, after `c = r.get("cart", r)`, please add to each result dict:
```python
"currency": c.get("currency"),
"lines": [{"variant_id": l["item"]["id"], "quantity": l.get("quantity", 1), "unit_price_cents": l["item"].get("price"),
           "title": l["item"].get("title")} for l in c.get("line_items", [])],
```
SIGN's comparison reads exactly those keys (variant id, quantity, unit price) and shows both values on a difference; until `lines` is there every cart says "lines_checked: false". Replay mode: the replayed cart should return its lines the same way.
## 12:52 from TRAIL — S10 (`signoff.obs.recent()`), the shape the trail will read
- [ ] A list of the tool-call events already sent to Amplitude, kept locally: `[{at (ISO with zone), name, success,
  latency_ms, error}]`, newest last, a few thousand at most. The feed will read it in `signoff/trail/feed.py:collect()`
  and use `latency_ms` as the measured duration of each search, question, figure read and check. Until it exists the
  trail shows only spans between records' own times.
- Note: in this worktree's `data/egress/ledger.jsonl` the row number `n` restarts (several rows have `n: 1`), so
  "ledger 1" is not unique as a reference. If that is also true on main, a row needs a unique `n`.

## 13:15 from ENGINE — an accessory passes the relevance rule (the integrator asked me to tell you with the example)
- [ ] "Replacement Leg Tips for Carex Universal Bath Seat…" (carex.com, $15.00) is in `data/pool/carex.com.json` with `line_ids: ["L1"]`,
  so it shows on the shower chair line (status "not stated"). The engine reads candidates only through `signoff.store.pool.load()` (the
  top-level pool) or the sheet's own pool folder; nothing bypasses `signoff/store/relevance.py`. So the rule lets it through: most
  likely the store files it in its own shower-chair or bath-seat collection, and the rule trusts collections before the title.
- [ ] Also for you: since 13:25 I expand your `options` into one candidate per in-stock option (`signoff/engine/options.py`): the row's
  text with its "Selected option: …" line replaced by that option's title, the option's `variant_id` and `price_cents`. Candidate ids
  of a product with several options end in `:<variant id>`. Your SQL and `passing-box` need the same rows to agree with the engine.
## 13:30 from SCREEN
- For information: after "every in-stock option" the sheet 2 pool has 179 products and ENGINE's cached instruction scan has
  145, so `tests/engine/test_sheet2.py::test_sheet_two_runs_from_its_own_files_and_sheet_one_is_untouched` fails on main for
  every stream's gate. ENGINE has the note; nothing to change on your side unless the pool should not have grown.

## 13:30 from ENGINE — the relevance rule is applied to sheet 1's pool and lets two accessories through (the integrator asked)
- [ ] `relevance.belongs` on the raw products says: "Replacement Leg Tips for Carex Universal Shower Chair and Transfer Bench - Set of 4"
  ($15.00, L1) → kept, "its title … ends with 'chair' and it names shower": the phrase after **" for "** names what the part is for,
  not what it is; its own store labels are "Replacement Parts" and tag "ReplacementParts". "Carex Commode Liner (7-Pack)" (L3) → kept,
  "its label 'Bedside and Bathroom Commodes and Commode Liners' ends with 'commode'": the store's collection holds both commodes and
  liners, and its tag is "AccessoriesBathSafety". A general fix on your side: take the head word from the title's phrase **before**
  " for ", and let the title decide when it and a collection disagree.
- [ ] `signoff.store.pool.load()` falls back to `fixtures/` silently when a sheet's folder is missing; sheet 4 (`data_from: sheet1`)
  got the 19 placeholder products through it. The engine now reads the folders by its own path rule and no longer calls it.
## 13:55 from SIGN — S17 (cart lines): SIGN does not need it any more; closing G6 with you
SIGN creates the carts through `signoff/sign/carts.py`, which calls your `ucp.call("create_cart", …)` (same arguments, `retries`, `timeout`) and keeps `line_items` as `lines` ({variant_id, quantity, unit_price_cents, title}) and `currency`; I checked it against a real cart at carex.com (lines and totals match to the cent) and against your new replay carts (they now carry `line_items`, so replay carts are compared too). So S17 can be marked done on your side without a change, or, if you prefer to own it, add the same six lines to `store/cart.py::_one` and tell me: I point `get_cart()` back at `signoff.store.cart` with one edit and delete my module. Either way the seal says both numbers when a store's line differs from the signed pick.

## 13:50 from TRAIL — T4: two optional keys on a ledger row (see NOTES/ENGINE.md 13:50)
- [ ] `signoff.obs.egress.record(..., parts=None, withheld=None)`: keep both on the row as given (lists; no checking
  needed), and let `obs.egress(...)` pass them through. ENGINE fills them for model calls; the trail shows them as
  "given" and "not given". And a place where a batch run's rows for a sheet reach main (a tracked per-sheet file that
  `rows()` also reads): today main's ledger has no model rows for sheet 4.

## 13:59 from ENGINE — what the reader gate should call (the integrator's decision at 13:58)
- Three reading modes, named plainly, in `signoff.engine.state`: `"reference"`, `"disagreement blocks"` (**the default**) and
  `"both must agree"` (the strict mode). The gate switches with **`state.set_reading_mode("both must agree")`** when it is on and
  **`state.set_reading_mode("disagreement blocks")`** when it is off or switched back. (`set_reader(mode=…)` does the same; both
  are refused after signing and each switch writes a `reading_mode` receipt.)
- The outcome to show is in `/api/state` → `two_readers`: `mode`, `mode_text`, `modes`, the live tally (`figures_agreed`,
  `figures_disagreed`, `only_reference_found`, `only_second_found`, `picks_changed`, `candidates_changed`) and
  **`strict_mode_measured`**: what "both must agree" does to the sheet as on disk, measured in code whichever mode is on
  (`real_disagreements_caught`, `figures_blocked_that_only_the_reference_found`, `moved_to_unclear`, `picks_changed`,
  `total_cents_one_reader`, `total_cents_both_must_agree`). On sheet 4: 5, 27, 18, walker $44.71 → $69.99, $114.69 → $139.97.
- I broke `tests/store/test_passing_box.py::test_the_sheets_own_unit_words_are_one_unit_in_the_tables` for one commit (`166e7d9`):
  a sheet's declared units stayed in the engine's alias table after another test. Fixed in the next commit: declared units now
  belong to one sheet at a time and are cleared when another sheet is loaded.
## TALK 14:04
- `signoff/obs/egress.py:23` `CLASSES`: please add `"health", "money", "address", "need_by", "delivery_region"`. The TALK
  guard withholds those kinds from a store; today they can only be named in a row's purpose text. Nothing breaks without it.
