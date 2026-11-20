
## 11:32 from ENGINE
- After `POST /api/admin/refresh-pool` rewrites `data/pool/`, the figures for changed pages are stale. Call
  `signoff.extract.run.refresh()` (reads only products whose text changed, then calls `signoff.engine.state.reload_data()`); it returns
  the run summary. If you would rather not wait for it, call `signoff.engine.state.reload_data()` alone and the new products show as
  "never stated on the page" until the reader has run.
- Each figure in `data/figures/<store>.json` may carry `unsure: true`; such a figure does not count. If your SQL loads figures, filter
  on `span_found_in_text = true AND unsure IS NOT true` to match the engine.
