# Stream TRAIL

You are the TRAIL stream at a timed hackathon (deadline 16:30 today; feature freeze 15:00; anything not on
main and seen working by 14:30 is cut). Use the hackathon-stream skill. First run `./hk own TRAIL`. Then read
CONTRACT.md (the body once, every amendment from 12:00 on carefully) and the AGENTS.md quirks log.

## Why this stream exists
The builder's words today: "I want more work done on the audit trail, on how we show context, on how we show
the observability part, in a beautiful way. Check every button, placement, spacing, image, graph, animation."
And earlier: "not colourful; neat, with nice animations showing context", "too much text, need it neat and
more professional". The challenge itself asks for "a shopping agent with an audit trail ... show the
information and steps behind what it did". The decision screen (`/`, the SCREEN stream's) shows one item's
decision. Nothing yet shows the run: who told whom what, in what order, and what was recorded. You build that.

## You own
`signoff/trail/**`, `web/trail/**`, `tests/trail/**`. Everything else: `NOTES/<OWNER>.md`. Develop on port
8006 (`uv run uvicorn signoff.app:app --port 8006`); main is 8800 (GET only there; never POST to it).

## What to build
1. **One feed** (`signoff/trail/api.py` exporting `router`, optional in the app): `GET /api/trail` returns
   the run as ordered events, merged from what already exists and is real: the receipt chain
   (`signoff/engine/receipts.py`, `GET /api/receipts`: signed requests accepted and refused, limit changes,
   picks, signing, carts), the outbound ledger (`GET /api/egress`: every message that left, to whom, what
   kinds of fact, no payloads), the reader gate's history (`GET /api/gate/status`), the store questions
   (`asked` on candidates in `/api/state`), the pool's fetch times, Senso runs (`/api/senso/checks`), the
   Persona and Relay results, Airbyte jobs (`/api/airbyte/status`). Each event: `{n, at, lane, to_lane,
   kind, label (five words or fewer), detail (short), ref (receipt number or ledger number), duration_ms,
   count, verified}`. Lanes: Order, Agent, Reading model, Stores, Approver's phone, Checks (Senso, Persona),
   Records (the database, Amplitude). Invent nothing: an event exists only if a real record does; if a
   source has no timing, leave `duration_ms` null. Never raise; a missing source is an empty list. Ask the
   owning stream in `NOTES/<OWNER>.md` for a field you need rather than guessing it.
2. **The trail view** (`web/trail/index.html`, served at `/trail/`): the run as a picture. A sequence
   diagram with one quiet vertical lane per actor and one row per event, drawn in SVG: an arrow from the
   sender's lane to the receiver's, a five-word label, and a small mark for what kind of fact travelled
   (order sentence, page text, figure, limit, signature, cart). Refusals are visible as arrows that stop.
   Above it a slim summary: events, messages out, limits sent to stores (it should read 0), receipts
   verified N of N. Beside or under it a step waterfall (search, read, check, ask, sign, cart) with real
   counts and durations where they exist. Click an event: a side sheet with the quote, the hash, the
   receipt before and after it. New events arrive live (`GET /api/events` signals a change; refetch) and
   draw themselves in, one arrow at a time, about 250 ms each; with motion off the final state is complete.
3. **Fit the product.** Use the decision screen's visual system exactly (read `web/screen/style.css` and
   reuse its variables, type scale, spacing, hairlines, radius; one accent; three greys; 14 px body; no
   sentence on the surface longer than five words; long text behind a click). The top bar must match the
   decision screen's, with two tabs, "Decision" (`/`) and "Trail" (`/trail/`); ask SCREEN in
   `NOTES/SCREEN.md` to add the tab on its side. Design for 1440 x 810; it must also read at browser zoom
   150%.
4. **Polish as part of the work, not after it.** Before each commit take a screenshot of `/trail/` (headless
   Chrome, see `demo/shot.sh`) and look at it: alignment to an 8 px grid, equal gutters, no clipped or
   overlapping label, consistent arrowheads and stroke widths, nothing that jumps when data arrives.

## Done when
`uv run -q pytest -q -x` is green; `/trail/` on your port shows the real run from a reset through a signed
sheet (use `SIGNOFF_MODE=replay` on your own port to sign without touching real stores) with every arrow
traceable to a receipt or a ledger row; a screenshot you have looked at is committed under `web/trail/shots/`.

## Rules
The working path is not changed: you only read. Tests that call an outside service get `@pytest.mark.live`.
No AI or tool authorship lines in commits, docs or code. Avoid special cases and silent fallbacks: if a
source is missing, the view says so in two words. Commit small and often to `stream/TRAIL`; the integrator
merges every 15 to 20 minutes. Do the work yourself; start no new threads.
