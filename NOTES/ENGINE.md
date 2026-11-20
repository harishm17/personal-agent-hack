
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
