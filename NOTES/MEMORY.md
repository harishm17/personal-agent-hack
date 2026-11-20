
## 13:50 from ENGINE — the hook is in; here is the shape it accepts (say if you need another)
- On `reset()` and `use_sheet()` the engine calls **`signoff.memory.recall(sheet: dict) -> dict | None`** once (never on a limit or
  measurement change), with a copy of the sheet file's content. It never raises into the engine: if your call raises, the sheet starts
  as on disk and `/api/state` → `degraded` says "what was remembered could not be read (…)". Return `None` or `{}` for nothing.
- Return:
  ```json
  {"facts":   [{"fact_id": "tub_inside_width", "value": 21.5, "measured_by": "Elena", "measured_at": "2026-11-18T09:00:00-08:00"}],
   "strikes": [{"line_id": "L5", "product_key": "…", "reason": "…", "by": "issuer", "at": "…"}]}
  ```
- What the engine does with it, and nothing else: a fact whose `fact_id` is one of the sheet's `shopper_facts` and whose value is a
  number inside that fact's `min`..`max` takes the value and gains `remembered: true`, `measured_by`, `measured_at`. A strike whose
  `product_key` is in the pool on that line (`line_id` optional: without it, every line of the sheet the product is on) is loaded with
  `from_memory: true`; it is under the hash like any strike and is undone only by a signed `unstrike`. Anything else is ignored and
  listed.
- `/api/state` → `memory`: `{facts: [...applied], strikes: [...applied], ignored: [{…, why}]}`.
- Test: `tests/engine/test_state.py::test_what_memory_recalls_is_applied_at_the_start_of_a_run_and_nowhere_else`.
