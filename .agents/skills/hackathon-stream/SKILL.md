---
name: hackathon-stream
description: Use when working as one of several parallel agents in a hackathon kit repo, when a session was told "you are the <X> stream" or "you own <folder>", or when a needed change falls in a path another stream owns.
---

# Working as a hackathon stream

## Overview
You own a set of paths, build against fixtures, and talk to other streams only through NOTES/ and the integrator.
The kit enforces part of this: edits outside your paths are denied, and the Stop hook runs the checks before you
finish.

## Start of session
1. `./hk own <STREAM>` (skip if `./hk own --show` already names you).
2. Read CONTRACT.md, the AGENTS.md quirks log, and `streams/<STREAM>.md`.
3. Build the first slice against `fixtures/` before touching live APIs.

## Rules of the road
| Situation | Do |
|---|---|
| Change needed in another stream's path | Append to `NOTES/<OWNER>.md`: time, file:line, exact change, why. Tell the human in one line. Keep going with a stub. |
| Interface needs a new or changed field | Request it in `NOTES/INTEGRATOR.md`. Implement only additive, optional fields, behind a flag, until the amendment lands in CONTRACT.md. |
| Human explicitly reassigns a path to you | They run `./hk own <STREAM> --add '<path>'`; then edit it. |
| Gate blocks your stop | Fix the root cause and rerun. Never weaken, skip or delete a check. If the failure is in another stream's path, note it for them and say so. |
| Non-obvious setup or API quirk | Add a 1–3 line entry, prefixed `[<STREAM>]`, to the AGENTS.md quirks log. |
| Clock line says feature freeze passed | Only fixes and demo-path polish from now on. |

## Commits
Commit small and often on your branch, staging only your own paths: `git add <your paths> NOTES/`.
At each sync point run `git merge main` into your branch (or let the integrator merge) and rerun `./hk check`.

## Report at sync points
One line, then proof: `<STREAM>: <done | blocked on X> — <command> → <key output>`.

## Common mistakes
- Making a "quick" fix in another stream's file over the shell. The hook only guards the edit tools; the rule still applies.
- Building against a guessed data shape instead of the fixture, which then breaks at the first end-to-end run.
- Saving all work for one big commit at the sync point; the cross-checker and integrator can't see the work until then.
