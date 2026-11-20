
## 13:05 request from AIRBYTE (hook blocks my own edit): `web/relay/index.html`, the "passed" line
- File `web/relay/index.html`, in `redeem()`: replace the line
  `$("meta").textContent = "Claim " + r.claim_type + ", " + r.at + ". Sandbox claims are simulated.";`
  with
  `const when = new Date(r.at.replace(/([+-]\d\d)(\d\d)$/, "$1:$2"));`
  `$("meta").textContent = "Claim: " + r.claim_type.replace(/_/g, " ") + ", taken at " + (isNaN(when) ? r.at : when.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })) + ". Sandbox claims are simulated.";`
- Why: the raw ISO time ("2026-11-20T12:42:41-0800") wraps in the middle of the date at 390 px.
- Or run `./hk own AIRBYTE --add 'web/relay/**' --add 'signoff/relay/**' --add 'tests/relay/**'` and I make it.
