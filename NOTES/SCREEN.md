
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
