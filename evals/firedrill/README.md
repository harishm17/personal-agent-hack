# Firedrill campaign against Sign-Off's shopper chat

Sandbox agent: `signoff/sign/firedrill_agent.py` (one fresh process per drill, the L3 pick already struck, replay mode so
no cart can reach a real store, no database or Amplitude writes). `POST /chat` is Sign-Off's agent; `POST /chat-plain`
is the plain agent (same model, rules only in its prompt, write tools on a sandbox copy) for the comparison.

Files: `persona_*.json`, `evaluation_*.json`, `scenario_*.json`, `world*.json` (saved with `firedrill library save` and
`firedrill world save`); `build_local.py` writes `_local/descriptor.json` and `_local/plan*.json` (absolute paths, not committed).

Run: `uv run python evals/firedrill/build_local.py descriptor`; `firedrill register --descriptor evals/firedrill/_local/descriptor.json --name ...`;
`uv run python evals/firedrill/build_local.py plan <descriptor digest>`; `firedrill plan --world <id>`; `firedrill apply <plan> --approve --follow`;
`firedrill runner enroll`; `firedrill run --plan evals/firedrill/_local/plan.json --descriptor evals/firedrill/_local/descriptor.json --campaign <id>`;
`firedrill report <campaign>`.

What Firedrill can check exactly: only calls to synthetic tools (`hosted_tool_calls`). Sign-Off's state (strikes, limits, carts) is
not a synthetic tool, so the rubric evaluations read the conversation, and the state is graded by code: the sandbox returns
`state_unchanged` and `changed` with every reply, and ENGINE's `signoff.agent.pressure` replays the transcripts Firedrill wrote and
grades by sheet hash, strikes, limits and carts.
