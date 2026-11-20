# Stream TALK

You are the TALK stream at a timed hackathon (deadline 16:30 today; feature freeze 15:00). Use the
hackathon-stream skill. First run `./hk own TALK`. Then read CONTRACT.md (skim the body; read "Calling the
stores" and the amendments from 12:00 on), OPEN.md (your items are K1 to K4) and the AGENTS.md quirks log.
**Time box: K1 and K2 on your branch by 14:25, K3 and K4 by 14:40. Anything later is cut.** Say in
NOTES/INTEGRATOR.md by 14:10 if that will not hold and what the smallest honest version is.

## Why this stream exists
The builder, at 13:55: "Do we have agent-agent communication and guards on what is shared? I want this
implemented." What exists: the product ("Sign-Off") shops real stores to another person's written order
(lead example, sheet 4: a therapist's equipment order shopped by the patient's daughter). Each store runs
its own agent, reachable with one real call (`ask_business`, single turn; see `signoff/store/ask.py` and
`signoff/store/ucp.py`). Today our side sends it one fixed, templated question about delivery and returns.
That is agent-to-agent communication in the thinnest form: no model writes our side, so there is nothing
to guard. You make it real.

## What to build
1. **Our agent really talks to the stores' agents (K1).** `signoff/talk/`: given a purpose (for example
   "can an opened shower chair be returned, and will it arrive by the need-by date?") and a product, a
   model writes the message to that store's agent, the reply is read, and if it does not answer, one
   follow-up is written and sent (each call is single turn, so a follow-up carries the short thread).
   Use a Superlinked SIE chat model for the writing (OpenAI-compatible, `https://api.superlinked.com/v1/
   chat/completions`, Bearer `SIE_API_KEY`, `Qwen/Qwen3.8-27B-FP8` answered warm in under a second; see
   AGENTS.md). Real store calls go through the project's client (it sends the agent profile header and
   writes the outbound ledger); space them out, cache every exchange under `data/talk/`, never ask the
   same thing twice, answer from the cache in replay mode. **Never call a cart or checkout tool.**
2. **The guard on what is shared (K2), in code.** A model may draft; code decides what leaves.
   - The rule: a sheet may declare `sharing`, which kinds of fact each kind of recipient may receive
     (tell the integrator the exact text to put in `sheets/sheet4.json` and `sheets/sheet3.json`; the
     integrator owns sheets). Default when absent: a store's agent may receive the product's name, the
     need-by date and the delivery region; it may not receive a limit, a home measurement, a person's name
     or role, anything about health, a budget or an address. The reason for sealing a limit is not only
     privacy: a store that knows your limit can answer to it.
   - The check, for every outbound message: (a) sealed values from the active sheet (each limit with its
     unit in the ways it can be written, each home measurement, each name) by normalised match; (b) spans
     about health, a person, money and an address found by a small Superlinked model (`sie-sdk`,
     `client.extract("urchade/gliner_multi-v2.1", {"text": ...}, labels=[...])` returns spans with
     offsets), which code then removes or refuses. The model finds; code decides. If anything was removed
     the message is rewritten once without it and checked again; if it still fails, it is not sent.
   - Every decision goes to the outbound ledger (`signoff.obs.egress(recipient, purpose, payload,
     fact_classes)`, see `signoff/obs/egress.py`) and to your own record: draft, removed spans with the
     rule that removed each, the text sent, the reply.
   - What comes back is untrusted: a reply is text to quote, never an instruction; it changes no state.
   Tests: a draft containing each kind of sealed fact never reaches the store call; a clean draft does.
3. **A real blocked share (K3).** `POST /api/talk/ask {store, product_id?, text}` (laptop only; the path
   prefix `/api/talk/` is already guarded): the shopper's own words become the purpose. Run it once for
   real with words that carry sealed facts (for example asking the agent to tell the store about the
   patient's weight and operation so they hurry) and record what was drafted, what was removed and what
   was sent, and the store agent's real reply. Do not stage a result: if the model's draft happens to be
   clean, that is the result, and try a second phrasing.
4. **The view (K4).** `web/talk/index.html`, served at `/talk/`: each store conversation as a thread: our
   message as sent, a quiet row of what was withheld (two-word marks, the removed words behind a click),
   the store agent's reply with the answering words marked. `GET /api/talk/threads`. Use the decision
   screen's visual system exactly (`web/screen/style.css` and its top bar; ask SCREEN in NOTES/SCREEN.md to
   add a "Conversations" tab). Very little text on the surface; screenshots at 1440 x 810 looked at.

## You own
`signoff/talk/**`, `tests/talk/**`, `data/talk/**`, `web/talk/**`. Everything else: `NOTES/<OWNER>.md`.
Develop on port 8008; main is 8800 (GET only there).

## Rules
The working path is not changed: you add routes and files; you never write engine state or change a pick.
No special cases, no lists of products or stores, no silent fallbacks. Tests that call a store or SIE get
`@pytest.mark.live`. No AI or tool authorship lines in commits, docs or code. Close each item with
`DONE K<n>: <proof>` or `WONTDO K<n>: <reason>` in NOTES/INTEGRATOR.md. Commit small and often to
`stream/TALK`. Do the work yourself; start no new threads.
