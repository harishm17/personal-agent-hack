// JSON in on stdin, JSON out on stdout. Ops: create, issue, claim. The key arrives in the environment, never printed.
import * as sdk from "@persona/sdk-node";

const Persona = sdk.Persona ?? sdk.default?.Persona ?? sdk.default;
const CLAIM_TYPE = "live_human_presence";

async function readJson() {
  let data = "";
  for await (const chunk of process.stdin) data += chunk;
  return data ? JSON.parse(data) : {};
}

function fail(error) {
  const detail = error?.response?.data ?? error?.body ?? undefined;
  return { ok: false, status: error?.status ?? error?.statusCode ?? null, message: String(error?.message ?? error).slice(0, 300), detail };
}

const input = await readJson();
const persona = new Persona({ apiKey: process.env.PERSONA_API_KEY });
let out;
try {
  if (input.op === "create") {
    const s = await persona.relays.create({ claimType: CLAIM_TYPE, encryptionKeyJwk: null, sandbox: true });
    out = { ok: true, relayToken: s.relayToken, relaySecret: s.relaySecret, relaySessionAccessToken: s.relaySessionAccessToken };
  } else if (input.op === "issue") {
    const p = await persona.relays.issuePrivacyPass({ claimType: CLAIM_TYPE });
    out = { ok: true, privacyPassToken: p.privacyPassToken };
  } else if (input.op === "claim") {
    const c = await persona.relays.generateClaim({ privacyPassToken: input.privacyPassToken, relayToken: input.relayToken, relaySecret: input.relaySecret });
    out = { ok: true, claimPayload: c.claimPayload, tokenConsumed: c.tokenConsumed };
  } else {
    out = { ok: false, message: "unknown op" };
  }
} catch (error) {
  out = fail(error);
}
process.stdout.write(JSON.stringify(out));
