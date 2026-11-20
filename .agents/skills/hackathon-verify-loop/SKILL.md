---
name: hackathon-verify-loop
description: Use when designing how a hackathon product checks model output, when the rubric rewards a "real verification loop" or self-correction, when building an eval set or measured numbers for the README, or when an LLM is grading its own work.
---

# Verification loop and evals

## Overview
The model proposes; code decides. Every placed project at the Gemini 4 Argon hackathon had deterministic code
judging the model's output, and the demo showed that check catching a real error.

## Pick the deterministic check
| Domain | Code that decides |
|---|---|
| Physical / spatial | simulator or tracer (MuJoCo, ray or beam tracing, collision, geometry clearance) |
| Claims about documents or video | quotes must appear in the source text or captions near the cited time; citations resolve |
| Numbers | computed by code from data (never by the model); units checked |
| Generated code or config | it compiles, loads and passes tests the model did not write |
| Structured output | JSON Schema validation; enums; cross-field invariants |
| UI or visual output | render it, screenshot it, compare to a reference or an explicit checklist |

## Loop shape
generate → render or run → deterministic checks → model critic (looks at the rendered result, returns structured
issues with locations) → route each issue to the part or file that owns it → regenerate only that part → repeat.
Cap the rounds and give the loop a deadline. Save every iteration with its scores so the UI can replay how
quality improved; that replay is a strong demo beat.

## Guard against cheating
A model that writes both the thing and its checks will make the checks pass. Keep the checks in code the
generating model cannot edit. Review generated diffs for disabled collisions, hardcoded expected values, or
skipped assertions. `./hk crosscheck` looks for exactly this.

## Eval set with ground truth
By the first end-to-end run, write 10–20 cases in `evals/cases.jsonl` with known answers (real inputs; include
cases that should fail). Set `eval.cmd` in `.hk/config.json`, then run `./hk eval`. Paste the summary line into the
README "Measured" table. Rerun after every prompt change; a domain knowledge file or a prompt change that moves
the pass rate is a better pitch than any adjective.

## Offline fallback
Cache the outputs of real runs in `fixtures/` and add a replay mode, so the demo survives venue Wi-Fi.
Label replayed output as replayed.
