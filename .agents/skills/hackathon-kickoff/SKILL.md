---
name: hackathon-kickoff
description: Use when starting a timed hackathon build in a kit repo (CONTRACT.md still has placeholders), when the user pastes an event brief, rules, rubric or prize list, or says how many hours are left before submission.
---

# Hackathon kickoff

## Overview
Turn the brief into a frozen contract, owned parallel streams, a visible clock and a check gate, then get out of
the way. Winners had streams building against fixtures within 30 minutes of the start; the rest of the day is building.

## Time box
| Event length | Kickoff budget (brief → streams launched) |
|---|---|
| 4–8 hours | 30 min |
| 24 hours | 60 min |
| 1 week | 1 day |
At the budget's end, launch with what you have and keep refining the contract as integrator.

## Before the clock starts (the user's part; see the kit's PLAYBOOK.md)
Keys for the tools you may use are in `.env`, the idea is chosen or down to three, and the brief is in one file.
With those three, this kickoff fits its budget; without them, steps 2 and 5 eat it.

## Steps (each one writes a file)
1. **Brief → CONTRACT.md "Judging" + `.hk/config.json` + SUBMISSION.md.** Copy the rubric weights, prize list
   and submission rules verbatim. Write the format (live demo minutes, video cap, who judges, anything said on
   stage at the opening) on the "Format" line. No published rubric: leave `rubric` as `[]`, say so on that line,
   and the judge agent uses its default. Copy the form's real fields and character limits into SUBMISSION.md and
   ask the user now for teammates' names and emails. Timeline: `./hk timeline --start HH:MM --break "13:30 lunch"
   --write` works out the milestones from the build start and the deadline and stores them; paste its table
   into CONTRACT.md "Timetable". The hooks show the timeline to every agent on every prompt.
2. **Idea, if it is not chosen yet (10 minutes, no longer).** Score at most three candidates on seven points,
   0–2 each: one sentence a judge can repeat; a named person with a pain backed by a number; real input and a
   real action; code has the last word and can be shown catching a real model error; ground truth for one
   measured number exists today; two to four sponsor tools each do a needed job; end to end by the 40% mark
   with every demo beat cacheable. Take the highest and stop discussing.
3. **Prizes → CONTRACT.md "Prizes".** One row per prize you target, two to four in total: what the sponsor
   wants to see, what the tool does in the demo path, the owning stream, the demo beat. A tool that does no
   job in the story is a bolt-on; sponsor engineers judge their own prize and see through it. Record what
   sponsor staff told the user (what wins, traps, limits).
4. **Riskiest dependency first.** Name the one outside thing the demo cannot work without (a sign-in flow, an
   account approval, a data source). The user tests it by hand now, while you write the rest. CONTRACT.md
   states the fallback and the clock time at which the fallback is taken.
5. **Tools: one real call each, ten minutes in total.** For every tool in the Prizes table whose key is in
   `.env`, make one real smoke call, tick "First real call works", and write the exact model IDs, request
   shape and limits into CONTRACT.md "Models and APIs". A tool with no key yet, or not reached in ten minutes,
   keeps "no" in that column and its smoke call becomes the first task in the owning stream's prompt. Vendor
   skills: `./hk skills list` shows the kit's packs (`./hk skills add <pack>`); sponsor tools seldom have one,
   so put the sponsor's docs URL from the brief in "Models and APIs" instead. Start anything asynchronous or
   slow now (ingestion, index builds, cold models) and give it a warm-up line in DEMO.md. Traps go in the
   AGENTS.md quirks log.
6. **DEMO.md story and the one screen, before interfaces.** Write the one sentence, then the story sized to
   the event's live slot; the verification beat must catch something real. Name the single screen the audience
   watches and what moves on it. Anything not in the story is a non-goal.
7. **Interfaces and fixtures.** Shared types, file formats, endpoints and event shapes go in CONTRACT.md
   (JSON Schemas in `schemas/` if useful). Commit one real-format fixture per interface in `fixtures/`,
   including one complete recorded run that drives the screen from step 6, so the UI stream builds the real
   screen from its first minute. Real data that is a download is fetched now into `data/`.
8. **Ownership, skeleton and checks.** Use 3–5 streams split by folder (2–3 when one person steers them all or
   the build window is under six hours); every path has exactly one owner. The integrator (this session) owns
   the shared files: CONTRACT.md, DEMO.md, SUBMISSION.md, README.md, `.gitignore`, `.env.example`,
   package.json, pyproject.toml, lockfiles, `schemas/`, `fixtures/`, `streams/`. `demo/` goes with the UI
   stream and `data/` with the stream that loads it. No stack given: Python with `uv` and FastAPI for server
   and agent code (`uv init --bare`, `uv add fastapi uvicorn pytest`), one page served by it or a Vite + React
   app when the screen needs it, server-sent events for anything shown live, files or SQLite for state.
   Write `ownership` (stream → globs) and `checks` in `.hk/config.json`: a `checks` key is a path prefix and
   its command runs when files under it changed; `default` runs every time. Keep each check under 60 seconds:
   typecheck, lint, the verifier's unit tests. The Stop hook runs them before any agent finishes.
   **Every check must pass on the skeleton before you commit**: run `./hk check --all`. A check that fails at
   kickoff blocks every stream's first stop. Call interpreters the way this machine has them (`python3`,
   `.venv/bin/python`, `uv run`). Give each stream one passing smoke test with its own file name
   (`test_<stream>_smoke.py`; same-named test files in different folders collide, and pytest exits 5 when it
   collects nothing). If a stream has nothing to check yet, leave its key out and add it when the code exists.
9. **Stream prompts.** Write one `streams/<STREAM>.md` per stream from [stream-prompt.md](stream-prompt.md).
   Interface detail stays in CONTRACT.md; the prompt names the sections to read.
10. **Freeze and launch.** Commit "Contract v1" on main. Then launch one agent per stream, each in its own worktree:
   - T3 Code: `t3_thread_launch` with `workspaceStrategy` `{"type":"worktree","baseRef":"main","branch":"stream/<name>","startFromOrigin":false}`
     and message `Run ./hk own <STREAM>, then follow streams/<STREAM>.md`.
   - Terminal: `./hk stream <STREAM>`, then start `claude` (or `codex`) in the printed directory with the same message.
   - Claude Code agent teams: 3–5 teammates, one per stream, each told its `streams/<STREAM>.md`. Use in-process
     mode, because split panes don't work in Ghostty.
   The stream that builds the screen and the stream with the hardest logic get the strongest model the user
   allows; glue and data streams can run Sonnet. Ask the user once which models to use.
11. **Second reviewer.** Right after launch, start `./hk crosscheck watch --until <deadline>` in the background.
   It reviews every commit against CONTRACT.md with Codex when installed (a different model family),
   otherwise a fresh Sonnet session.

## Quick reference
| Need | Command |
|---|---|
| See clock, streams, gate | `./hk status` |
| Work out the day's milestones | `./hk timeline --start HH:MM --write` |
| Bind this checkout to a stream | `./hk own <STREAM>` |
| Run checks now | `./hk check --all` |
| Turn the gate off for a spike | `./hk gate off` (turn it back on) |

## Common mistakes
- Planning past the budget. A contract that's 80% right at minute 25 beats a perfect one at minute 90; amend it later.
- Launching streams before fixtures exist: each stream invents its own data shape, and integration breaks at the first end-to-end run.
- Slow checks. The gate runs on every stop, so a 4-minute test suite stalls every agent. Gate on fast checks and run the slow ones at sync points.
- Ownership by feature instead of by path. Two streams editing one file is the main failure of parallel agents.
- Leaving prize tracks out of the contract. A track worth $5k ("best use of X") needs a named owner and a demo beat.
- Chasing every sponsor prize. Each extra tool costs integration time; past winners wired three or four into
  one working loop, and none after the first end-to-end run.
- Leaving the form for the last ten minutes. Its limits, required links and teammate emails go into
  SUBMISSION.md at kickoff, and `./hk submit` checks them.
- Writing many files through one long shell command. Command guards on some machines block long heredocs
  and `rm -rf`; write files with the edit tool and delete by explicit path.
