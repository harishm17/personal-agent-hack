
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
