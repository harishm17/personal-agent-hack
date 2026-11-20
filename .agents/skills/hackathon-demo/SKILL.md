---
name: hackathon-demo
description: Use at hackathon feature freeze or in the final hours, when preparing the live demo or pitch, writing answers to judges' questions, recording the demo video, writing the README or submission form, or making the repo public.
---

# Demo, pitch, video and submission

## Overview
Judges see a short live demo, a video and a README, and sponsor judges look for their own tool. Read the
format from CONTRACT.md "Format" (live minutes, video cap) and size everything to it. Reserve the last 60–90
minutes (or the last day of a week-long event) for this; it takes longer than anyone expects.

## Live demo and pitch
- Fill DEMO.md: the one sentence, the story stretched to the live slot, inputs, fallback. Hardcode the demo
  path's inputs; cache anything flaky and label the cached part on screen.
- Shape of the slot: the one sentence and the person (about 10%), the running product (about 50%: real input,
  the action, the check catching a real error), the measured number and how it was measured (about 20%),
  what each sponsor tool did (about 10%), the sentence again (10%). No slides unless the event requires them.
- Say each sponsor tool's name at the moment it does its job, and fill "Tools named out loud" in DEMO.md.
- Rehearse with a timer three times and log each run in DEMO.md; cut until the run ends 15 seconds early.
  Rehearse once with the network off, using the fixture replay.
- Ten minutes before going up: warm slow services, sign in everywhere, raise the browser zoom.

## Questions
Fill the "Questions and answers" table in DEMO.md with short, true answers: what is real and what is mocked,
what happens when the agent is wrong, how the number was measured and what the ground truth is, why each
sponsor tool, who uses it and who pays, what was cut, what was built today. If an honest answer is weak,
fix the product or the claim, not the wording.

## Video
Length comes from the rules; never run past the cap, and put what it is and proof that it runs in the first
30 seconds. Two ways to make it:
- **Narrated screen recording of the rehearsed run** (fastest in a one-day event): the user records the
  screen and their own voice once the pitch is rehearsed. The pitch and the video are then the same script.
- **`./hk record`** (repeatable, no voice needed):
  1. Copy `demo/shots.example.json` to `demo/shots.json`. Write one scene per story beat: a caption, the
     actions (goto, click, fill, upload, waitFor, wait, press, scroll), and a `hold` time.
  2. Start the app, then run `./hk record`. Output goes to `demo/out/`: a .webm with burned-in captions, an
     .srt, and an .mp4 when ffmpeg is available.
  3. Narration (optional): set `HK_TTS_CMD` to a command that reads text on stdin and writes audio to
     `$HK_TTS_OUT`. Add `say` text to scenes; each scene is held as long as its line.
  4. For a polished launch film, install the `video-remotion` or `video-hyperframes` skill pack.
Beats, as shares of the length: the person and the problem 15%, real input going in 25%, the check catching
something 25%, the result and one measured number 25%, the repo URL 10%.
Upload as unlisted or public, never private, and open the link in a private window.

## README
Fill the template: the problem, what it does, how it works, **Tools and what each one does here**, **Measured**
(from `evals/report.md` and logged runs), how to run it, the offline demo, and **Built today vs pre-existing**.
No AI or tool authorship lines. If the event requires disclosing AI tools, ask the user how to word it.

## Judge pass
Use the `judge` subagent (fresh context) on the README, DEMO.md and the running app's screenshots against the
CONTRACT.md rubric and prize table. Fix the top three issues it finds, not all of them.

## Submission
1. Fill SUBMISSION.md (the form's own fields and limits, copied at kickoff). Use the rubric's and each
   sponsor's wording, cite the measured number, and list every sponsor tool used.
2. `./hk check --all` green on main; `git tag submission`; push.
3. **Ask the user before making the repo public or submitting the form** (both are outward-facing).
4. `./hk submit` until it prints "ready": limits, links that open while logged out, HEAD pushed, no secrets.
5. The user pastes the answers into the form. If the form can be edited later, submit a first version 20–30
   minutes before the deadline and update it; a late form is worth nothing.
6. After submitting: teammates added, license file present, repo description set, the README links the video
   at the top.
