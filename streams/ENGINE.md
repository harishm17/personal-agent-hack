# Stream ENGINE

You are the ENGINE stream at a timed hackathon (deadline 16:30 today). Use the hackathon-stream skill.
First run `./hk own ENGINE`. Then read CONTRACT.md and the AGENTS.md quirks log. Read once for the reasons:
`/Users/harishm/research/2026-11-20-tokensand-personal-agents-hackathon/IDEA.md` ("What code decides",
"Corrections to the example", "Known traps").

## You own
`signoff/engine/**`, `signoff/extract/**`, `signoff/agent/**`, `data/figures/**`, `tests/engine/**`.
Everything else: request changes in `NOTES/<OWNER>.md`. Develop on port 8001.

## Build, in this order
1. **The engine from fixtures (by 11:50).** `signoff/engine/`: load `sheets/sheet1.json` and the pool,
   figures, store answers and strikes (from `data/`, falling back to `fixtures/`); checks, margins, the pick
   rule and statuses exactly as in `fixtures/make_state.py` and CONTRACT.md "Rules code decides". A test
   proves your state equals `fixtures/state.json` for the fixture inputs (ignore `version`). Then
   `signoff/engine/api.py` with `router`: `GET /api/state`, `GET /api/events` (SSE), `POST /api/shopper/fact`,
   `GET /api/sheet/canonical`. Then the in-process functions in CONTRACT.md "In-process calls"
   (`apply_issuer`, `set_shopper_fact`, `canonical_sheet`, `sheet_hash`, `mark_signed`, `reset`,
   `set_senso`, `reload_data`). State is in memory and recomputed in under 50 ms: the phone's slider sends a
   signed request on every movement.
2. **The figure reader (by 12:00, it is a first-hour test).** `python -m signoff.extract.run` reads
   `data/pool/*.json` (the STORE stream writes it by about 11:45; use `fixtures/pool.json` until then) and
   writes `data/figures/<store>.json`. The model proposes figure, kind, value or range, unit and the exact
   quote; code finds the quote in `text` and sets `start`, `end` and `span_found_in_text`. A figure with no
   found span does not count. Traps: seat width is not overall width; a variant's figure may differ; a
   range has two ends. Reject or mark unsure, never guess. Model per CONTRACT.md "Models and APIs". If
   `ANTHROPIC_API_KEY` is not in the keys file yet, shell out to `claude -p` for the batch. When
   `SIE_API_KEY` arrives: add Superlinked SIE `extract` as a second extractor (`extractor: "sie:<model>"`),
   pinned model, warmed; the span check is the same code. Score both against `evals/handcheck.jsonl` when
   the SIGN stream has it (27 of 30 is the bar) with `python -m signoff.extract.score`.
3. **The shopper's chat (by 13:00).** `POST /api/shopper/say`: Elena talks to the agent. Its tools read
   state and candidates. No tool changes a limit, restores a struck product or makes a cart, so "put it
   back" gets a refusal that names who can (`refused: true`). Never suggests a limit.
4. After 13:10: sheet 2 (`sheets/sheet2.json` comes from the integrator), the plain-prompt agent used as
   the comparison in the 40 pressure attempts, replay mode.

## Interfaces you provide / consume
- Provide: the ENGINE routes and `signoff.engine.state` functions, exactly as named in CONTRACT.md.
- Consume: `signoff.store.pool.load()`, `signoff.db.records.write(state)` (call it after each change, in a
  background thread; it never raises), `evals/handcheck.jsonl`.

## Done when
`uv run -q pytest -q -x` is green; `curl -s localhost:8001/api/state | head -c 200` returns the state;
changing a limit through `apply_issuer` moves the L2 pick; a struck `product_key` stays struck after
`POST /api/shopper/say {"text": "put it back"}`.

## Sync points
12:00 first-hour tests decided (extraction score) · 12:20 first sync, real pool replaces fixtures ·
13:10 end-to-end run · 15:00 feature freeze · 15:30 code freeze.
No AI or tool authorship lines in commits, docs or code. Commit small and often to `stream/ENGINE`.
