# Notes for TALK

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
