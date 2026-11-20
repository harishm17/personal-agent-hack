// Runs web/seal/verify.js (the file the page loads) on a saved proof. Prints one JSON object.
import { readFileSync } from "node:fs";
const [, , modulePath, proofPath] = process.argv;
const v = await import(modulePath);
const proof = JSON.parse(readFileSync(proofPath, "utf8"));
const real = await v.check(proof, proof.canonical);
const tree = v.scan(proof.canonical);
const bound = tree.items.lines.items[0].items.limits.items[0].items.bound;
const same = v.splice(proof.canonical, []) === proof.canonical;
const oneChar = await v.check(proof, v.splice(proof.canonical, [{ start: bound.start, end: bound.start + 1, raw: "2" }]));
// change 300 to 250 and back, as the page does it: the typed value becomes an edit or, when it is the value already there, none
const to250 = v.rawFor(bound, "num", "250"), back = [v.rawFor(bound, "num", "300"), v.rawFor(bound, "num", "300.0"), v.rawFor(bound, "num", " 300 ")];
const changed = await v.check(proof, v.splice(proof.canonical, [{ start: bound.start, end: bound.end, raw: to250 }]));
const restored = await v.check(proof, v.splice(proof.canonical, back[0] === null ? [] : [{ start: bound.start, end: bound.end, raw: back[0] }]));
const strip = ({ bytes, ...rest }) => rest;
console.log(JSON.stringify({ real: strip(real), oneChar: strip(oneChar), firstBound: bound.raw, same, to250, back,
  changed: strip(changed), restored: strip(restored), keyId: await v.keyId(proof.public_key.jwk),
  roundTrip: JSON.stringify(JSON.parse(proof.canonical)) === proof.canonical,
  quote: v.jsonString("1–5 days \"x\"") }));
