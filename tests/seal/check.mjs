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
const strip = ({ bytes, ...rest }) => rest;
console.log(JSON.stringify({ real: strip(real), oneChar: strip(oneChar), firstBound: bound.raw, same,
  roundTrip: JSON.stringify(JSON.parse(proof.canonical)) === proof.canonical,
  quote: v.jsonString("1–5 days \"x\"") }));
