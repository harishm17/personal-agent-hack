# Notes for GRAPH

## 14:10
## from SCREEN: the shared top bar and visual system (copy exactly, so every page is one product)
Link `/screen/style.css` first and build on its variables and classes; do not copy values into your own CSS.
```html
<link rel="stylesheet" href="/screen/style.css">
<header class="top">
  <span class="brand">Sign-Off</span>
  <span class="sheet">{state.sheet.title}</span>
  <nav class="tabs" aria-label="Views">
    <a href="/">Decision</a><a href="/trail/">Trail</a><a href="/graph/">Memory</a><a href="/talk/">Conversations</a>
  </nav>
  <span class="meta">{n} items · invented people, real stores</span>
  <span class="grow"></span>
  <span class="pill">Not signed</span>          <!-- "pill signed" and "Signed 13:56" when state.seal.signed -->
  <span class="total">$114.69</span>           <!-- state.total_cents -->
</header>
```
- Put `aria-current="page"` on your own tab. Order is fixed: Decision, Trail, Memory, Conversations. The Decision screen
  shows the Memory and Conversations tabs only when `HEAD /graph/` and `HEAD /talk/` answer 200, so they appear the moment
  your page is served; on your page show all four.
- Everything in the bar comes from `GET /api/state`: `sheet.title`, `lines.length`, `sheet.invented`, `mode` (add
  "replay of cached store data" or "fixture data" to `.meta`), `seal.signed`, `seal.signed_at`, `total_cents`. Redraw on
  `GET /api/events` (SSE), since a sheet switch on the Decision screen changes the title and the total.
- Scale: style.css sets `html { font-size: clamp(16px, 1.1vw, 22px) }`; size everything in rem, no px but 1 px hairlines.
- Type: one family `var(--f)`, weights 400 and 600 (500 inside a line). One display size per view: 1.25rem/1.75rem 600.
  Body 0.875rem/1.25rem, secondary 0.8125rem, captions `.cap` / `.small` 0.75rem/1rem. `var(--mono)` for hashes only.
- Colour: ground `--bg`, surfaces `--surface`, hairlines `--line`, text `--t1` / `--t2` / `--t3`. One accent, `--accent`
  (indigo on the Decision screen: the pick). Green `--ok` only as a tick, `--bad` only for a refusal or a failed figure,
  `--mark` behind a quoted figure (`<mark>`). No other hues.
- Shape: 8 px grid (0.5rem); cards `.card` (hairline, radius `--r`, padding 1rem); pills `.pill`; rows `.row`; links
  `.link`. Page layout on the Decision screen: `padding` 1rem around, 1rem gaps between cards, the bar is `--bar` (3rem).
- Text budget: labels of five words or fewer on the surface; anything longer behind a click, in a card that sits over
  the right column (see `.drawer` in `/screen/ladder.css`).
- Motion: 200 to 400 ms, `cubic-bezier(.3, .1, .2, 1)`, only for a real change in the data; import `MOTION`, `EASE`,
  `arrive`, `appear`, `roll` from `/screen/motion.js` (off for reduced motion, `?motion=0` and automated browsers).

## 13:58 from MEMORY — `GET /api/memory` is stable; this is its shape (on main after the next merge; on 8007 now)
```json
{"read_from": "singlestore",            // or "mirror (database not reached: <error>)"
 "database": {"state": "ok", "error": null, "table": "memory"},
 "mirror": {"file": "data/memory/memory.jsonl", "rows": 42},
 "counts": {"rows": 42, "proved": 42, "not_proved": 0, "by_kind": {"store_answer": 39, "home_measurement": 1, "strike": 1, "purchase": 1}, "records_refused": 0},
 "owners": [{"owner": "shopper", "owner_name": "Elena", "rows": [<row>, ...]},
            {"owner": "issuer", ...}, {"owner": "carex.com", ...}],
 "not_memories": [{"source": {...}, "code": "no_signed_request", "why": "..."}],
 "rule": "..."}
```
A `<row>`: `{id, owner, owner_id, owner_name, kind, key, value, text, source, created_at, sheet_id, proved}`.
- `owner`: `"shopper"`, `"issuer"` or a store's domain. `owner_id` / `owner_name`: the person on the sheet (`elena` / `Elena`), null when no record names the sheet.
- `kind` and its `key` / `value`: `home_measurement` (key = fact id; `{value, unit, was}`), `strike` (key = product key; `{struck, line_id, product_key, reason, title}`; `struck: false` is a signed unstrike),
  `store_answer` (key = `delivery`, `returns`, or `<figure>:<product id>`; the store's saved answer), `purchase` (key = sheet hash; `{total_cents, signer, carts}`).
- `text`: one plain sentence. `source`: `{type: "receipt", chain, n, hash, file, at}` (+ `key_id`, `signed_request: {n, hash}` for the approver's) or `{type: "file", file, index, at, entry_hash}`.
- `proved`: a record on disk proves this row now. Draw only `proved: true` rows as memories; a row that is not proved was put in the table some other way and is never recalled.
Edges you can draw without guessing: row → `owner`; row → `source.chain` (receipt) or `source.file`; strike → `value.line_id` and `key` (product); home_measurement → `key` (fact);
store_answer → `value.line_id` when present. `GET /api/memory/recall` gives the subset recalled for the sheet on the table (`facts`, `strikes`, `store_answers`, `purchases`, each entry with `memory_id`).
- 14:16 from MEMORY: two additions, nothing removed. `shelf` in `GET /api/memory` (four slots for the sheet on the table; shape in NOTES/TRAIL.md 14:08), and each row has `age` and `on_shelf`.
  Store answers now also come from TALK's saved conversations: key `talk:<product id>:<thread>:<turn>`, `value.said_by: "the store's own agent"`, `source: {type: "file", file: "data/talk/threads/…", turn, at}`.
## REVIEWS 14:20
- One more node for the run's graph, after "pick" and beside it (it feeds nothing back): "Reviews read", from `GET /api/reviews/log`
  (shape in NOTES/TRAIL.md, same entry). Edges you can draw without guessing: search → `serves.line_id` and `serves.candidate_ids`;
  search → recipient `exa.ai`; and from `GET /api/reviews` → `lines[].best_reviewed.candidate_id` as a dashed "offered to the shopper"
  edge. It is never an edge into the pick: `summary.applied` is always false.
- Per candidate, `GET /api/reviews` → `by_candidate[<candidate id>]` has `{found, rating, out_of, review_count, rating_site, note}`.
