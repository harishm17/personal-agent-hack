# Stream AIRBYTE

You are the AIRBYTE stream at a timed hackathon (deadline 16:30 today). Use the hackathon-stream skill.
First run `./hk own AIRBYTE`. Then read CONTRACT.md (all amendments) and the AGENTS.md quirks log.
Time box: a first working sync by 12:15. If no sync has run by 12:30, write what blocked it in
`NOTES/INTEGRATOR.md` and stop; the product does not depend on this stream.

## What exists
A local Airbyte Core 2.5.0 (installed with `abctl local install --port 8900`, Docker through Colima) at
`http://localhost:8900`, health `GET /api/v1/health`. Login and API client values are in the keys file:
`AIRBYTE_URL`, `AIRBYTE_EMAIL`, `AIRBYTE_PASSWORD`, `AIRBYTE_CLIENT_ID`, `AIRBYTE_CLIENT_SECRET`
(`config.env("NAME")`; never print them). Drive it through its API, not by clicking. Airbyte's staff said
today that the prize is for using Airbyte locally (their cloud has an outage). Docs: https://docs.airbyte.com
(every page has a Markdown form), API reference https://reference.airbyte.com.

## The job (it must be real, not decoration)
The therapist's order is the source of every limit on the sheet. Today it is a file in the repo. Make it
arrive the way such an order really would: as an export from her system that Airbyte syncs, on this Mac,
into the app's database, where the app reads it as limits that are "proposed, from the order" until Dana
confirms them on her phone.

## You own
`signoff/airbyte/**`, `data/order/**`, `tests/airbyte/**`. Everything else: `NOTES/<OWNER>.md`.

## Build, in this order
1. **The order export.** `data/order/order.csv` (or JSON lines): one row per limit, written from
   `sheets/sheet1.json` by a small script (line id, need, limit id, name, op, value, unit, issuer, issued
   at), plus a header note that the order is invented. The main app serves the repo over the tunnel only
   for `/profile`; ask the integrator in `NOTES/INTEGRATOR.md` if you need `/order` served too, or serve
   the file from a tiny local server of your own on port 8005 (Airbyte runs inside Docker: reach the Mac at
   `host.docker.internal`, or use the tunnel address `config.public_url()`).
2. **One sync that runs.** Source: Airbyte's File source (CSV or JSON over HTTPS) or another source that
   needs no personal account. Destination, in order of preference: SingleStore (database `signoff`, values
   `SINGLESTORE_HOST`, `_PORT`, `_USER`, `_PASSWORD` in the keys file; check whether this Airbyte version
   lists a SingleStore destination, or whether the MySQL-compatible one works against it); otherwise a
   local destination Airbyte supports out of the box, from which a small loader of yours copies the rows
   into SingleStore table `order_limits` and says so. Create source, destination and connection through
   the API, trigger the sync, wait for it, and record the job id, row count and duration.
3. **The app reads it.** `signoff.airbyte.order.load() -> dict`: the limits as synced (from the SingleStore
   table), with `{"via": "airbyte", "job_id", "synced_at", "rows", "connection_id"}`; never raises; returns
   `None` when the table is missing. `python -m signoff.airbyte.sync` re-runs the sync on demand.
   `signoff/airbyte/api.py` exporting `router`: `GET /api/airbyte/status` (last job, rows, when) and
   `POST /api/airbyte/sync`. Tell the integrator when this works; the integrator wires "proposed until
   confirmed" with the ENGINE, SIGN and SCREEN streams.
4. Only then, if time is left: a second source that shows why a pipeline is needed, for example each
   store's policy text (from `data/store_answers/`) synced beside the order.

## Done when
`uv run -q pytest -q -x` is green; `curl -s localhost:8800/api/airbyte/status` (after merge) shows a
finished job with a row count equal to the number of limits in the sheet; the rows are in SingleStore.

## Rules
Tests that call Airbyte or SingleStore get `@pytest.mark.live`. Do not stop or reinstall Colima or Airbyte
without asking in `NOTES/INTEGRATOR.md`. No AI or tool authorship lines in commits, docs or code. Commit
small and often to `stream/AIRBYTE`. Do the work yourself; start no new threads.
