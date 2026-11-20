// Record the demo from a shot list: real browser, burned-in captions, SRT, optional narration.
//
//   ./hk record [demo/shots.json] [--headed]
//
// Shot list (see demo/shots.example.json):
//   { "baseUrl": "http://localhost:5173", "viewport": {"width": 1920, "height": 1080},
//     "scenes": [ { "caption": "...", "say": "optional narration", "hold": 2500,
//                   "actions": [ {"goto": "/"}, {"click": "text=Analyze"}, {"waitFor": "text=Done", "timeout": 60000} ] } ] }
// Actions: goto, click, hover, fill [sel, text], type [sel, text, delayMs], press key, upload [sel, [files]],
//          waitFor sel, wait ms, scroll px, eval "js".
// Narration: set HK_TTS_CMD to a shell command that reads text on stdin and writes audio to $HK_TTS_OUT
// (any TTS: sponsor API, `say`, piper, espeak). Scenes are held at least as long as their narration.
// Output: demo/out/demo-<stamp>.webm and .srt; .mp4 with narration when an ffmpeg with libx264 is found
// (HK_FFMPEG, ffmpeg on PATH, or uvx imageio-ffmpeg).
import { chromium } from "playwright";
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const root = execFileSync("git", ["rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
const args = process.argv.slice(2);
const shotsPath = path.resolve(root, args.find((a) => !a.startsWith("--")) || "demo/shots.json");
const headed = args.includes("--headed");
const shots = JSON.parse(fs.readFileSync(shotsPath, "utf8"));
const viewport = shots.viewport || { width: 1920, height: 1080 };
const outDir = path.join(root, "demo", "out");
fs.mkdirSync(outDir, { recursive: true });
const d = new Date();
const pad = (n) => String(n).padStart(2, "0");
const stamp = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
const base = path.join(outDir, `demo-${stamp}`);

function findFfmpeg() {
  const candidates = [process.env.HK_FFMPEG, "ffmpeg"].filter(Boolean);
  for (const c of candidates) {
    const r = spawnSync(c, ["-hide_banner", "-encoders"], { encoding: "utf8" });
    if (r.status === 0 && r.stdout.includes("libx264")) return c;
  }
  const r = spawnSync("uvx", ["--quiet", "--with", "imageio-ffmpeg", "python", "-c",
    "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"], { encoding: "utf8" });
  const exe = (r.stdout || "").trim().split("\n").pop();
  return r.status === 0 && exe && fs.existsSync(exe) ? exe : null;
}

function audioSeconds(ffmpeg, file) {
  const r = spawnSync(ffmpeg, ["-hide_banner", "-i", file], { encoding: "utf8" });
  const m = /Duration: (\d+):(\d+):([\d.]+)/.exec(r.stderr || "");
  return m ? +m[1] * 3600 + +m[2] * 60 + +m[3] : 0;
}

const ffmpeg = findFfmpeg();
const tts = process.env.HK_TTS_CMD;
const narration = [];
if (tts) {
  if (!ffmpeg) console.warn("[hk] HK_TTS_CMD set but no ffmpeg with libx264; narration skipped");
  shots.scenes.forEach((scene, i) => {
    if (!scene.say || !ffmpeg) return;
    const out = `${base}-say${i}.wav`;
    const r = spawnSync("bash", ["-lc", tts], { input: scene.say, env: { ...process.env, HK_TTS_OUT: out } });
    if (r.status !== 0 || !fs.existsSync(out)) {
      console.warn(`[hk] TTS failed for scene ${i}: ${(r.stderr || "").toString().slice(-200)}`);
      return;
    }
    narration[i] = { file: out, seconds: audioSeconds(ffmpeg, out) };
  });
}

async function setCaption(page, text) {
  await page.evaluate((t) => {
    let el = document.getElementById("__hk_caption");
    if (!el) {
      el = document.createElement("div");
      el.id = "__hk_caption";
      el.style.cssText = "position:fixed;left:50%;bottom:48px;transform:translateX(-50%);max-width:80%;" +
        "padding:14px 26px;border-radius:12px;background:rgba(10,12,16,.82);color:#fff;z-index:2147483647;" +
        "font:600 30px/1.3 system-ui,-apple-system,Segoe UI,sans-serif;text-align:center;pointer-events:none;";
      document.body.appendChild(el);
    }
    el.textContent = t || "";
    el.style.display = t ? "block" : "none";
  }, text).catch(() => {});
}

async function act(page, a, caption) {
  const [kind] = Object.keys(a).filter((k) => k !== "timeout");
  const v = a[kind];
  const timeout = a.timeout || 30000;
  if (kind === "goto") await page.goto(new URL(v, shots.baseUrl).toString(), { waitUntil: "networkidle", timeout });
  else if (kind === "click") await page.click(v, { timeout });
  else if (kind === "hover") await page.hover(v, { timeout });
  else if (kind === "fill") await page.fill(v[0], v[1], { timeout });
  else if (kind === "type") await page.locator(v[0]).pressSequentially(v[1], { delay: v[2] ?? 40, timeout });
  else if (kind === "press") await page.keyboard.press(v);
  else if (kind === "upload") await page.setInputFiles(v[0], v[1].map((f) => path.resolve(root, f)), { timeout });
  else if (kind === "waitFor") await page.waitForSelector(v, { timeout });
  else if (kind === "wait") await page.waitForTimeout(v);
  else if (kind === "scroll") await page.mouse.wheel(0, v);
  else if (kind === "eval") await page.evaluate(v);
  else throw new Error(`unknown action ${JSON.stringify(a)}`);
  await setCaption(page, caption);
}

const browser = await chromium.launch({ headless: !headed });
const context = await browser.newContext({ viewport, recordVideo: { dir: outDir, size: viewport } });
const page = await context.newPage();
const t0 = Date.now();
const timings = [];
try {
  for (const [i, scene] of shots.scenes.entries()) {
    const start = (Date.now() - t0) / 1000;
    await setCaption(page, scene.caption);
    for (const a of scene.actions || []) await act(page, a, scene.caption);
    const minEnd = start + Math.max((scene.hold ?? 2000) / 1000, narration[i]?.seconds ? narration[i].seconds + 0.4 : 0);
    const now = (Date.now() - t0) / 1000;
    if (now < minEnd) await page.waitForTimeout((minEnd - now) * 1000);
    timings.push({ start, end: (Date.now() - t0) / 1000, caption: scene.caption || "" });
    console.log(`[hk] scene ${i + 1}/${shots.scenes.length} ${timings.at(-1).start.toFixed(1)}-${timings.at(-1).end.toFixed(1)}s ${scene.caption || ""}`);
  }
} finally {
  await setCaption(page, "");
  await context.close();
  await browser.close();
}

const video = await page.video().path();
fs.renameSync(video, `${base}.webm`);
const ts = (s) => new Date(s * 1000).toISOString().slice(11, 23).replace(".", ",");
fs.writeFileSync(`${base}.srt`, timings.filter((t) => t.caption)
  .map((t, i) => `${i + 1}\n${ts(t.start)} --> ${ts(t.end)}\n${t.caption}\n`).join("\n"));
console.log(`[hk] video ${base}.webm (${timings.at(-1)?.end.toFixed(1)}s), captions ${base}.srt`);

if (ffmpeg) {
  const inputs = ["-y", "-hide_banner", "-loglevel", "error", "-i", `${base}.webm`];
  const voiced = timings.map((t, i) => (narration[i] ? { ...narration[i], at: t.start } : null)).filter(Boolean);
  voiced.forEach((n) => inputs.push("-i", n.file));
  const filter = voiced.length
    ? ["-filter_complex", voiced.map((n, k) => `[${k + 1}:a]adelay=${Math.round(n.at * 1000)}:all=1[a${k}]`).join(";") +
       ";" + voiced.map((_, k) => `[a${k}]`).join("") + `amix=inputs=${voiced.length}:normalize=0[aout]`,
       "-map", "0:v", "-map", "[aout]", "-c:a", "aac"]
    : [];
  const r = spawnSync(ffmpeg, [...inputs, ...filter, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", `${base}.mp4`], { encoding: "utf8" });
  if (r.status === 0) {
    console.log(`[hk] mp4 ${base}.mp4${voiced.length ? ` with ${voiced.length} narration clip(s)` : ""}`);
    voiced.forEach((n) => fs.rmSync(n.file, { force: true }));
  } else console.warn(`[hk] mp4 conversion failed: ${(r.stderr || "").slice(-300)}`);
} else {
  console.log("[hk] no ffmpeg with libx264 found: kept .webm (set HK_FFMPEG to convert to mp4)");
}
