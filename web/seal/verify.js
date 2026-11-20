// The check itself, with no page around it: the same file runs in the browser and in the test (node).
// What is checked is what the phone did (web/phone/index.html): the fingerprint is the SHA-256 of the canonical
// sheet's UTF-8 bytes, and the signature is ECDSA P-256 / SHA-256 over the UTF-8 bytes of a JSON message that
// names that fingerprint as `sheet_hash`, with `seq`. Raw r||s, base64url.
const utf8 = new TextEncoder();

export async function sha256(text) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", utf8.encode(text)));
}

export const hex = (bytes) => [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");

export function fromBase64url(text) {
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (text.length % 4)) % 4);
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

export async function verifyMessage(jwk, message, sig) {
  const key = await crypto.subtle.importKey("jwk", { kty: jwk.kty, crv: jwk.crv, x: jwk.x, y: jwk.y, ext: true },
    { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
  return crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, key, fromBase64url(sig), utf8.encode(message));
}

// One check of a canonical text (the real one or an edited copy) against the proof.
//   fingerprint       hex SHA-256 of `canonical`, computed here
//   signedFingerprint the fingerprint the signed message names (null when nothing is signed)
//   messageVerifies   the signature verifies over the message as it was signed
//   coversThis        the signature verifies over the message that names THIS text's fingerprint
//   valid             this text is what was signed: coversThis and the fingerprints are equal
export async function check(proof, canonical) {
  const bytes = await sha256(canonical);
  const out = { fingerprint: hex(bytes), bytes, signedFingerprint: null, messageVerifies: null, coversThis: null, valid: false };
  const s = proof.signature, k = proof.public_key;
  if (!s || !k) return out;
  out.signedFingerprint = JSON.parse(s.payload).sheet_hash;
  out.messageVerifies = await verifyMessage(k.jwk, s.payload, s.sig);
  // the message the phone would have had to sign for this text: the same message, naming this fingerprint
  const message = s.payload.split(out.signedFingerprint).join(out.fingerprint);
  out.coversThis = out.fingerprint === out.signedFingerprint ? out.messageVerifies : await verifyMessage(k.jwk, message, s.sig);
  out.valid = out.coversThis && out.fingerprint === out.signedFingerprint;
  return out;
}

// A JSON text as a tree that remembers where each value sits in the text, so one value can be replaced and every
// other byte stays exactly as the server wrote it (a re-serialised copy would not be byte-identical: 16.0, –).
export function scan(text) {
  let i = 0;
  const ws = () => { while (i < text.length && " \n\t\r".includes(text[i])) i++; };
  const value = () => {
    ws();
    const start = i, c = text[i];
    if (c === "{" || c === "[") {
      const list = c === "[", items = list ? [] : {};
      i++; ws();
      if (text[i] === (list ? "]" : "}")) { i++; return { type: list ? "list" : "object", items, start, end: i }; }
      for (;;) {
        if (list) items.push(value());
        else { const k = value(); ws(); i++; items[k.value] = value(); }
        ws();
        if (text[i++] !== ",") break;
      }
      return { type: list ? "list" : "object", items, start, end: i };
    }
    if (c === '"') {
      i++;
      while (text[i] !== '"') i += text[i] === "\\" ? 2 : 1;
      i++;
      return { type: "string", value: JSON.parse(text.slice(start, i)), start, end: i };
    }
    while (i < text.length && !",]} \n\t\r".includes(text[i])) i++;
    const raw = text.slice(start, i);
    return { type: raw === "null" ? "null" : raw === "true" || raw === "false" ? "bool" : "number", value: JSON.parse(raw), raw, start, end: i };
  };
  return value();
}

// A string as the server writes it in the canonical form: JSON with every non-ASCII character escaped.
export const jsonString = (s) => JSON.stringify(s).replace(/[\u0080-￿]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));

// The text with some values replaced: edits is [{start, end, raw}], positions in the original text.
export function splice(text, edits) {
  let out = text;
  for (const e of [...edits].sort((a, b) => b.start - a.start)) out = out.slice(0, e.start) + e.raw + out.slice(e.end);
  return out;
}
