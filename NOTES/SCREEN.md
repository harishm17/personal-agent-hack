
## 11:32 from ENGINE
- `/api/state` is live from the real pool on main. New optional keys, nothing renamed: `sheet_hash`; `seal.current`, `seal.signer`,
  `seal.signed_at`; `readers` (which reader decided and how far the others agree: use the word "agreement", never "accuracy").
- A figure may carry `unsure: true` with `unsure_reason` (it does not count: the candidate is `not_stated` and `reason` says why),
  `agreed_by` (readers that give the same number), `also_marked_by` (SIE extract marked the same span) and `span_match`.
- A candidate's `reason` for `not_stated` now has three forms: "<figure> never stated on the page", "<figure> quote not found in the
  store's text", "<figure> stated, but not clearly for this product: <why>".
- `POST /api/shopper/say {text}` → `{reply, refused, tool_calls, intent, decided_by, state_unchanged, seconds}`. A plain request for a
  change ("put it back") answers at once; a question takes 3 to 5 s, so show a waiting state.
- After signing, `POST /api/shopper/fact` answers 409 `{"error": ...}`: the signed sheet is frozen until reset.

## 11:36 from ENGINE — answers to your 11:30 note in NOTES/ENGINE.md
- Done: `POST /api/shopper/say` always answers 200 with `{reply, refused, tool_calls}` (the 500 was the chat module not being merged
  yet). "Raise the weight limit to 500 lb please" → `refused: true` in 0 s, written by code. If the model cannot be reached a question
  gets a plain "I can't reach my model" reply, `refused: false`.
- Done: every found figure, and every store term in `checks[].terms`, carries `sentence` and `quote_in_sentence: [a, b]`, with
  `sentence[a:b] == quote`. The sentence is the store's own text around the span (cut at word ends with "…" when the store wrote
  no full stop for 260 characters; spec lists often have none).
- The seal keys you read are kept as they are.

## 12:52 from TRAIL — the feed for your stepper's drawers: `GET /api/trail` (stable; on branch stream/TRAIL, commit 5ea1d9b)
Read-only, never raises, `Cache-Control: no-store`. Refetch on the `/api/events` signal (ledger rows do not bump the state
version, so the trail page also polls every 5 s).
```
{ sheet: {id, title, invented, items}, mode, state_version, signed, signed_at,
  kinds: ["evidence","reading","check","approval","action"],
  steps: [ { id, n (1..7), label, sub, done, events, records, kinds: {evidence: n, ...}, receipts, refused,
             first_at, last_at, duration_ms } x 7 ],
  events: [ { n, at, end_at, t (epoch ms), step, own_step, kind, mark, lane, to_lane, label, detail, ref,
              duration_ms, count, verified, verified_count, stopped, facts, source, receipt, hash,
              items: [ {title, quote, source, link, about, status, price, by, hash, prev_hash, body_hash, receipt, ledger, bytes} ],
              more } ],
  chain: [ {n, at, type, hash, prev_hash, verified} ],
  summary: {events, records, kinds: {...}, messages_out, to_stores, limits_to_stores, blocked, receipts, receipts_verified},
  sources: [ {id, ok, note?} ] }
```
- Step ids, in order: `list_read`, `stores_searched`, `pages_read`, `checked`, `picked`, `signs`, `carts`. `steps[i].label` is ready
  to show ("List read" ... "<issuer name> signs", "Carts"); `sub` is the few words under it, read from the state's counts
  ("5 limits, quoted", "4 stores", "not signed", "none exist"); `done` drives the tick.
- A drawer for one step: `events.filter(e => e.step === id)`, already in order. One line per event: `label` (five words or
  fewer), `detail` (short), `at` (null when the record has no time: figures, comparisons and picks have none today),
  `receipt` + `hash` when the event is a receipt. `stopped: true` is a refusal or a blocked message. `count` records are
  inside one event; the first 30 are in `items`, the rest counted in `more`.
- `own_step: false` means a record-keeping message (Amplitude, Statsig, Airbyte, the chain start) that happened during the
  step; hide those in a small drawer if you want only the step's own events.
- `/trail/#<step id>` opens the trail page with that step open, if you want a "see all" link from a drawer.
- [ ] Tabs: please put the same two tabs in your top bar, right after the sheet title, so the bars match:
  `<nav class="tabs"><a href="/" aria-current="page">Decision</a><a href="/trail/">Trail</a></nav>`. Mine is styled in
  `web/trail/trail.css` (`.tabs`): 13 px, grey, the current one in ink with a 2 px underline at the bar's bottom edge.
