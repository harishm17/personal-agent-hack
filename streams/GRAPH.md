# Stream GRAPH

You are the GRAPH stream at a timed hackathon (deadline 16:30 today; feature freeze 15:00). Use the
hackathon-stream skill. First run `./hk own GRAPH`. Then read CONTRACT.md (skim the body; read the
amendments from 13:10 on), OPEN.md (your items are H1 to H3), streams/MEMORY.md (the MEMORY stream is
building the store you draw from) and the AGENTS.md quirks log.
**Time box: H1 and H3 on your branch by 14:25, H2 by 14:40. Anything later is cut.** Say in
NOTES/INTEGRATOR.md by 14:10 if that will not hold and what the smallest honest version is.

## Why this stream exists
The builder, at 13:55: "We use a knowledge graph for memory? I want this implemented." The product
("Sign-Off") shops real stores to another person's written order; the lead example is sheet 4, a
therapist's equipment order shopped by the patient's daughter. Its knowledge is already a graph in
substance: people own facts, facts decide limits, limits test figures that stores state about products,
the approver strikes and signs. Nothing shows it as one, and nothing holds it between runs as one.

## What to build
1. **The graph, from real records only (H1).** `signoff/graph/`: nodes and edges built from what exists:
   the active sheet (people, items, limits, home facts), the order document's quoted sentences
   (`from_order`), the candidates in `GET /api/state` (products, their stores, the figures stated with
   their quotes, the outcome), the receipt chain (`GET /api/receipts`: who set, struck and signed what),
   the stores' answers, and the MEMORY stream's rows when they exist (`GET /api/memory`). Node kinds:
   person, home fact, order item, limit, product, store, statement (a quoted figure), strike, purchase.
   Edge kinds in plain verbs: wrote, measured, requires, states, sold by, passes, fails, struck, signed.
   Every node and edge carries its owner and its source (a file and offset, or a receipt hash). Invent
   nothing: no node without a source.
2. **Cognee holds it (H2).** Cognee is a sponsor's graph memory with permissions per dataset, and a key is
   in the keys file (`COGNEE_API_URL`, `COGNEE_API_KEY`, `COGNEE_TENANT_ID`; headers `X-Api-Key` and
   `X-Tenant-Id`; `GET /api/v1/datasets` works; read its docs first, https://docs.cognee.ai, every page has
   a text form). Put each owner's knowledge in its own dataset (the issuer's, the shopper's, one per
   store), build the graph there, and answer one question from it for an item ("what do we know that
   decides this item, and from whom?"). Show the permission doing work: a write to the issuer's dataset
   attempted with the shopper's identity is refused, and that refusal is recorded. Ingestion is said to be
   slow: start it early, and measure it. **If Cognee cannot hold the graph in your time box, the graph in
   H1 is served from your own nodes and edges and every reply says which backend answered; you then write
   exactly what Cognee did and did not do, and Cognee is not claimed.** No silent switch.
3. **The route and the picture (H3).** `GET /api/graph?line_id=` returns the nodes and edges for one item
   (the item, its limits and their order sentences, the home facts they use, the pick and the nearest
   rejected products with the statements that decided them, the stores, any strike), with `backend`.
   `web/graph/index.html`, served at `/graph/`: a small, quiet drawing of that graph, laid out left to
   right by kind (who, what they said, the rule, the product's own words, the outcome), labels of two or
   three words, the owner shown by a small mark, the full quote and its source on click. Use the decision
   screen's visual system exactly (`web/screen/style.css` and its top bar; ask SCREEN in NOTES/SCREEN.md for
   a "Memory" tab that MEMORY and you share). The builder rejected a screen of unexplained dots today:
   every node must say what it is in words, and there must be few enough to read (fold the rest into a
   count). Screenshots at 1440 x 810, looked at.

## You own
`signoff/graph/**`, `tests/graph/**`, `data/graph/**`, `web/graph/**`. Everything else: `NOTES/<OWNER>.md`.
Develop on port 8009; main is 8800 (GET only there).

## Rules
You only read the product's records; you never write engine state. No special cases, no silent fallbacks.
Tests that call Cognee get `@pytest.mark.live`. No AI or tool authorship lines in commits, docs or code.
Close each item with `DONE H<n>: <proof>` or `WONTDO H<n>: <reason>` in NOTES/INTEGRATOR.md. Commit small
and often to `stream/GRAPH`. Do the work yourself; start no new threads.
