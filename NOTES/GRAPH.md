
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
