// Real-time frames of the big screen, to look at motion: node demo/frames.mjs "<path-and-query>" <outdir> [ms] [every]
// Starts headless Chrome with a debugging port, loads the page and saves a PNG every `every` ms for `ms` ms.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";

const [pathq = "/", outdir = "demo/shots/frames", total = "6000", every = "200"] = process.argv.slice(2);
const base = process.env.SCREEN_URL || "http://localhost:8003";
const port = 9333 + Math.floor(Math.random() * 500);
const sep = pathq.includes("?") ? "&" : "?";
const [path, hash = ""] = pathq.split("#");
const url = `${base}${path}${sep}live=0${hash ? "#" + hash : ""}`;
mkdirSync(outdir, { recursive: true });
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", ["--headless=new", "--disable-gpu",
  "--hide-scrollbars", "--window-size=1920,1080", `--remote-debugging-port=${port}`, `--user-data-dir=/tmp/signoff-frames-${port}`, "about:blank"],
  { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200);
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((t) => t.type === "page"); } catch { /* not up yet */ }
  }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r));
  let id = 0;
  const waiting = new Map();
  ws.addEventListener("message", (m) => { const d = JSON.parse(m.data); if (waiting.has(d.id)) { waiting.get(d.id)(d.result); waiting.delete(d.id); } });
  const send = (method, params = {}) => new Promise((r) => { waiting.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
  await send("Page.enable");
  await send("Page.navigate", { url });
  const start = Date.now();
  let n = 0;
  while (Date.now() - start < +total) {
    const at = Date.now() - start;
    const shot = await send("Page.captureScreenshot", { format: "png" });
    if (shot && shot.data) { writeFileSync(`${outdir}/f${String(at).padStart(5, "0")}.png`, Buffer.from(shot.data, "base64")); n++; }
    await sleep(Math.max(0, +every - (Date.now() - start - at)));
  }
  console.log(`${n} frames in ${outdir}`);
  ws.close();
} finally {
  chrome.kill();
}
