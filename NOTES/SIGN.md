
## 11:32 from ENGINE
- `signoff.engine.state.set_issuer_key(info: dict)` exists (merged into `{"enrolled": False, "key_id": None, "persona": None}`).
- `apply_issuer` takes `set_limit`, `strike`, `unstrike`. Given `sign_sheet` it only checks the hash and returns the state; the seal is
  set by `mark_signed(signature, carts)`. `mark_signed` reads `signature["name"]` and `signature["at"]` for the seal text.
- A refusal is `state.EngineError` (a `ValueError`) with `.status`: 400 bad value, 404 unknown limit, line or product, 409 after signing.
  After `mark_signed` the sheet is frozen: every later `apply_issuer` and shopper fact is refused with 409 until `reset()`.
- `set_senso(checks)`: the list is put in `/api/state` as `senso`. A check that has `candidate_id` (the candidate's `id`) or `store` and
  `product_id` is also attached to that candidate as `senso: {"claims": [...]}`. Any other keys pass through untouched.
- `/api/state` now carries `sheet_hash` (the current one), so the phone need not call `/api/sheet/canonical` before signing.
