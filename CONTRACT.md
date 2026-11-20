# CONTRACT — <project name>

<!-- Filled by the hackathon-kickoff skill in the first 20–30 minutes. Keep it under ~250 lines.
     Frozen at the "contract freeze" time below. Later changes: integrator only, appended as
     "## Amendment HH:MM — <what>" so every agent sees what changed. -->

## What we are building
<One paragraph: the product, the specific person it is for, the one moment the demo must show.>

## Judging (drives every decision)
| Weight | Criterion | How we score on it |
|---|---|---|
|  |  |  |

Format: <live demo minutes, video cap, who judges, how finalists are chosen; "not published" if unknown>
Submission requirements: <repo public, video length, deadline>; the form's fields are in SUBMISSION.md

## Prizes (two to four; each tool must do a job in the demo path)
| Prize | What the sponsor wants to see | Our use of the tool | Owner | Demo beat | First real call works |
|---|---|---|---|---|---|
|  |  |  |  |  |  |
Answers from sponsor staff (what wins, known traps, limits): <notes>

## Demo (<N> minutes live, real inputs)
One sentence a judge can repeat: <sentence>
1. <beat 1>
2. <beat 2: the verification catching something real>
3. <beat 3>
Offline fallback: <recorded run / fixtures replay key>

## Models and APIs (exact IDs, do not substitute from memory)
| Role | Model / API | Notes (limits, params, traps) |
|---|---|---|
|  |  |  |
Vendor skills installed: <e.g. gemini-api-dev, pinned in skills-lock.json>

## Interfaces
<Shared types, file formats, HTTP endpoints, event shapes. Link JSON Schemas in schemas/ when they exist.>

## Ownership
| Stream | Owns | Reads | Done when |
|---|---|---|---|
|  |  |  |  |
Integrator owns CONTRACT.md, schemas/ and merges to main. Requests go in NOTES/<STREAM>.md.

## Verification
- Deterministic gate (code, not a model, decides): <what is checked>
- Eval set: evals/cases.jsonl (<N> cases with ground truth); `./hk eval` writes the measured numbers.
- Checks per path: see .hk/config.json "checks".

## Timetable
<!-- ./hk timeline --start HH:MM --write prints this table -->
| Time | Milestone |
|---|---|
|  | contract frozen, fixtures committed, streams launched |
|  | first sync: real outputs replace fixtures |
|  | first end-to-end run with real inputs; record a backup clip |
|  | feature freeze |
|  | code freeze: record video, pitch rehearsal |
|  | first version of the form submitted (`./hk submit` passes) |
|  | deadline |

## Non-goals
<What we will not build today.>
