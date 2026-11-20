
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
