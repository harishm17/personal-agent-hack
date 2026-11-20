
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
