# streams/<STREAM>.md template

Copy this into `streams/<STREAM>.md` and fill every <field>. Keep it under 60 lines; CONTRACT.md holds the shared parts.

```markdown
# Stream <STREAM>

You are the <STREAM> stream at a timed hackathon. Use the hackathon-stream skill.
First run `./hk own <STREAM>`. Then read CONTRACT.md and the AGENTS.md quirks log.

## You own
<globs, e.g. server/**, tests/server/**>. Everything else: request changes in NOTES/<OWNER>.md.

## Build, in this order
1. <thinnest slice that runs against fixtures/...>
2. <next>
3. <stretch, only after the first end-to-end run passes>

## Interfaces you provide / consume
- Provide: <endpoint / file / event, exactly as named in CONTRACT.md>
- Consume: <fixture or another stream's output>

## Done when
<observable check: command + expected output, e.g. `./hk check` green and `curl localhost:8000/api/runs` returns the fixture run>

## Sync points
<copy the timetable rows that matter for this stream>
```
