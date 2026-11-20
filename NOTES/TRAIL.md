# Notes for TRAIL

## 12:55 from SCREEN: the visual system to match
Link `/screen/style.css` and use its variables and classes; do not copy values. It is the shared system for `/` and `/trail/`.
- **Scale.** Everything is in rem. `html { font-size: clamp(16px, 1.1vw, 22px) }` is set in style.css: 16 px at 1440 wide,
  about 21 px on a 1920 projector, never under 16 px so browser zoom still works. No px sizes except 1 px hairlines.
- **Type.** One family (`var(--f)`), weights 400 and 600 (500 for emphasis inside a line). Display 1.25rem/1.75rem 600, one
  per view. Body 0.875rem/1.25rem. Secondary 0.8125rem. Caption `.cap`, `.small` 0.75rem/1rem. Tabular numerals are on
  for the whole body. `var(--mono)` only for hashes and codes.
- **Colour.** Ground `--bg`, surfaces `--surface`, hairlines `--line`. Text `--t1` / `--t2` / `--t3`. Marks `--dot`,
  `--dot-out`, `--accent` (near-black: the pick, the active thing). Green `--ok` only as a small tick; `--bad` only for
  a refusal or a failed check; `--mark` behind a quoted figure (`<mark>`). `--issuer` / `--shopper` / `--store` only as
  6 px dots (`<i class="od store"></i>`), never as text colour.
- **Spacing and shape.** 8 px grid (0.5rem); cards `.card` (1 px `--line`, radius `--r` = 0.5rem, padding 1rem, gap
  0.75rem); pills `.pill` fully round, 1.25rem tall. No shadows except the side sheet's; no dashed boxes.
- **Text budget.** Labels of five words or fewer on the surface; anything longer behind a click.
- **Top bar** (copy this markup; `.top` is 3rem tall, `--bar`):
  ```html
  <header class="top">
    <span class="brand">Sign-Off</span>
    <nav class="tabs" aria-label="Views"><a href="/">Decision</a><a href="/trail/" aria-current="page">Trail</a></nav>
    <span class="sheet">{sheet.title}</span><span class="meta">{n} items · invented</span>
    <span class="grow"></span>
    <span class="pill">Not signed</span>   <!-- class "pill signed" and "Signed 11:46" after signing -->
    <span class="total">$279.04</span>
  </header>
  ```
  The Decision screen already links to `/trail/` in its tabs. Title, item count, `invented`, the signed time and the
  total all come from `/api/state` (`sheet.title`, `lines.length`, `sheet.invented`, `seal.signed`, `seal.signed_at`,
  `total_cents`); when `mode` is `fixture` or `replay` add "fixture data" or "replay of cached store data" to `.meta`.
- **Motion.** 200 to 400 ms, `cubic-bezier(.3, .1, .2, 1)`, only for a real change in the data; off for
  `prefers-reduced-motion`, `?motion=0` and automated browsers. `web/screen/motion.js` exports `MOTION`, `EASE`,
  `arrive`, `appear`, `roll`; import it rather than writing new helpers.
- The Decision screen is being redesigned now (products as a list with requirement cells); style.css stays the base.

## 13:58 from MEMORY — the memory routes are stable (shape of a row and of `GET /api/memory`: NOTES/GRAPH.md, 13:58)
- `GET /api/memory/recall` → what a new run of the sheet on the table starts with: `{sheet_id, facts: [{fact_id, value, unit, measured_by, measured_at, used_by: [limit ids], age: {seconds, text}, memory_id, source, text}],
  strikes: [{line_id, product_key, title, reason, by: "issuer", by_name, at, age, memory_id, source, text}], store_answers: [{store, key, line_id, asked_at, age, memory_id, source, text}],
  purchases: [{signed_at, total_cents, carts, sheet_hash, ...}], counts: {recalled, of}, read_from, error}`.
- `GET /api/memory/recall?line_id=L5` → `{line_id, need, recalled: [{kind, owner, why, text, age, memory_id, source, ...}], counts: {recalled, of}}`: what bears on one item and why.
- What the engine applied is already in `/api/state` → `memory` and on the fact (`remembered`, `measured_by`, `measured_at`) and the strike (`from_memory: true`). A short line is enough: "remembered · Elena · 13:57", "struck before · <reason>", "asked 2 h 43 min ago".
