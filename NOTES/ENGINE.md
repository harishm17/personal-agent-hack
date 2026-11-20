
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

## 12:25 from SIGN — carts in the seal can now be `pending` or `failed`
`mark_signed(signature, carts)` is called with cart entries that may have `mode: "pending"` (the store had not answered within 5 s; `cart_url` is None; SIGN calls `mark_signed` again with the same signature when the store answers) or `mode: "failed"` (`note` says why). Seal text "N carts created" should count only entries with a `cart_url`, and `c["action"]` on a candidate should only be `cart_created` for those. `signature["senso"]` is now `{status: "complete" | "pending" | "not_connected", for_hash, checks, label}` (was a list). A second `mark_signed` with the same signature must keep the same `signed_at`.
