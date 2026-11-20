# Stream STORE

You are the STORE stream at a timed hackathon (deadline 16:30 today). Use the hackathon-stream skill.
First run `./hk own STORE`. Then read CONTRACT.md ("Calling the stores" first) and the AGENTS.md quirks log.
Working reference scripts (read, do not copy blindly):
`/Users/harishm/research/2026-11-20-tokensand-personal-agents-hackathon/research/ucp-probe/probe2.py` and
`cart.py`.

## You own
`signoff/store/**`, `signoff/db/**`, `data/pool/**`, `data/store_answers/**`, `profile/**`, `tests/store/**`.
Everything else: request changes in `NOTES/<OWNER>.md`. Develop on port 8002.

## Build, in this order
1. **The store client and the pool (by 11:45; two other streams wait on it).** `signoff/store/ucp.py`:
   discover each store's endpoint, `search_catalog`, `ask_business`, `create_cart`. The profile address is
   `config.public_url() + "/profile/agent-v1.json"`; the integrator starts the tunnel and writes
   `PUBLIC_URL` to the keys file. If it is empty, say so in `NOTES/INTEGRATOR.md` and build against saved
   responses meanwhile. Fetch every query of every line in `sheets/sheet1.json` from carex.com,
   vivehealth.com and parentgiving.com, once, and write `data/pool/<store>.json` in the CONTRACT.md pool
   shape (`text` is the plain product text with tags stripped; `product_key` is maker and model
   lower-cased; `line_ids` from the queries that found it; drop accessories and parts that are plainly not
   the needed thing). Keep the raw responses in `data/pool/raw/` for replay mode. Commit the pool as soon
   as it exists and tell the integrator in `NOTES/INTEGRATOR.md`: how many products per line and per store,
   and whether any `product_key` appears at two stores.
2. **Store answers.** Ask each store's agent once about delivery time and returns of an opened bath seat;
   write `data/store_answers/<store>.json` (shape of `fixtures/store_answers.json`, the reply verbatim, the
   delivery quote must be a substring of the reply). `signoff.store.pool.load()` and
   `signoff.store.ask.ask()`.
3. **SingleStore (by 12:20).** `signoff/db/`: database `signoff`, tables for the pool, the figures and
   the decision records (one row per candidate per state version); `signoff.db.records.write(state)` never
   raises and never blocks a request. `GET /api/sql/passing-box?line_id=` runs one SQL statement that
   returns the candidates inside all limits of that line and returns `{sql, rows}`; it must agree with the
   engine's `inside` set. Connection values are in the keys file (`SINGLESTORE_HOST`, `_USER`, `_PASSWORD`,
   `_PORT`); the connection was tested at 11:00.
4. **Carts (by 13:00).** `signoff.store.cart.create_carts(picks)`: one real cart per store, returning the
   store's own `continue_url`. Called only by the SIGN stream after a verified signature. Test it once with
   one product. **Never call a checkout tool, in any code path.**
5. After 13:10: replay mode from `data/pool/raw/`, `POST /api/admin/refresh-pool`, the cookware stores for
   sheet 2 (Made In, Caraway, Great Jones, Our Place, Material).

## Interfaces you provide / consume
- Provide: `signoff.store.pool.load`, `signoff.store.ask.ask`, `signoff.store.cart.create_carts`,
  `signoff.db.records.write`, the STORE routes, `signoff/store/api.py` exporting `router`.
- Consume: `sheets/sheet1.json`, the engine's state shape (`fixtures/state.json`).

## Done when
`uv run -q pytest -q -x` is green; `data/pool/*.json` holds real products for all six lines;
`create_carts` returned one real cart link; the passing-box SQL returns the same products as the engine.

## Sync points
11:45 pool committed · 12:20 first sync · 13:10 end-to-end run · 15:00 feature freeze · 15:30 code freeze.
No AI or tool authorship lines in commits, docs or code. Commit small and often to `stream/STORE`.
