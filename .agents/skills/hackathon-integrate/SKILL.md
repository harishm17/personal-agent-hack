---
name: hackathon-integrate
description: Use when acting as the hackathon integrator or lead, at a sync point or freeze in the CONTRACT.md timetable, when merging stream branches, when NOTES/ requests pile up, or when an interface must change after the contract freeze.
---

# Integrating a hackathon build

## Overview
The integrator owns main, CONTRACT.md and shared files. At every sync point it merges, proves the whole thing
runs end to end on real inputs, routes requests, and keeps every stream on the same contract.

## At each sync point
1. `./hk status`: the clock, each stream's last commit, gate state, and open cross-check items.
2. Merge streams into main one at a time (`git merge --no-ff stream/<name>`), running `./hk check --all` after each
   merge. A conflict in a file that two streams both edited means the ownership was wrong. Fix the ownership in
   `.hk/config.json` and CONTRACT.md, not just the merge.
3. Run the end-to-end flow with real inputs. Record the time it takes in DEMO.md's rehearsal log.
4. Work through `NOTES/*.md` and `NOTES/crosscheck.md`. Route each item to its owner, and check off what's done.
5. Tell each stream what changed. In T3, send a message to each stream thread; otherwise give the human one line
   per stream to relay.

## Changing the contract after the freeze
Append `## Amendment HH:MM — <what>` to CONTRACT.md: the field or endpoint, its old and new shape, and who must
act. Prefer additive, optional changes. Commit it alone ("Contract amendment: ..."), then notify the affected streams.

## Freezes
| Milestone | Integrator action |
|---|---|
| Feature freeze | Tell every stream: fixes and demo-path polish only. Move the hackathon-demo work to the front. |
| Code freeze | `git tag code-freeze`; only demo-blocking fixes after this, each one rechecked. |
| Submit | Follow the hackathon-demo skill's Submission steps; `./hk submit` must print "ready". |

## Rebalancing
A stream that's idle or blocked gets reassigned paths: edit `ownership` in `.hk/config.json`, append a contract
amendment, and have that checkout run `./hk own <STREAM>` again. Cut scope before adding streams late. A new
stream needs a contract slice and fixtures first.

## Common mistakes
- Merging all streams at once just before the deadline. Integrate at every sync point, even when the parts are half done.
- Silent contract edits. Every change after the freeze is an appended amendment that streams can see in the diff.
- Treating cross-check HIGH findings as optional. They are cheap and usually real: route them right away.
