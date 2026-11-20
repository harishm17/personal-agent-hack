// Signature: draws GET /api/seal/proof and checks the signature here, in this browser (verify.js, WebCrypto).
// Nothing on this page writes anything: an edit changes a copy of the canonical text held in the page.
import { check, scan, splice, jsonString } from "/seal/verify.js";

const q = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clock = (at) => (at ? new Date(at).toLocaleTimeString("en-GB") : "");
const short = (h) => (h || "").slice(0, 12).replace(/(.{4})(?=.)/g, "$1 ");
const money = (cents) => "$" + (cents / 100).toFixed(2);
const P = new URLSearchParams(location.search);
const ui = { key: "", proof: null, groups: [], nodes: new Map(), edits: new Map(), real: null, now: null, editing: null, cartOnly: P.get("view") === "cart", played: P.has("still") };  // ?still: no arrival motion
const LANE = { phone: 2, agent: 3, stores: 4 };
const OPS = { ">=": "≥", "<=": "≤", "==": "=", ">": ">", "<": "<" };
const ICON = {
  key: '<svg viewBox="0 0 12 12"><circle cx="3.5" cy="8.5" r="2"/><path d="M5 7l5-5M8 4l1.5 1.5"/></svg>',
  phone: '<svg viewBox="0 0 10 16"><rect x="1" y="1" width="8" height="14" rx="1.5"/></svg>',
};

// ---------- the rows under the signature, built from the canonical text itself ----------
function build(proof) {
  const t = scan(proof.canonical), groups = [];
  ui.nodes = new Map();
  const part = (node, kind) => { ui.nodes.set(node.start, { node, kind }); return { id: node.start, kind }; };
  const her = proof.approver.name || "the approver", home = proof.shopper.name || "the shopper";
  for (const ln of t.items.lines.items) {
    const L = ln.items, rows = [];
    for (const m of L.limits.items) {
      const it = m.items, issuer = it.set_by.value === "issuer";
      const what = String((it.terms.items[0] || {}).value || "").replace(/_/g, " ");
      rows.push({ owner: issuer ? "issuer" : "shopper", label: issuer ? `${her}'s rule` : `${home} measured`, lead: `${what} ${OPS[it.op.value] || it.op.value}`,
        parts: [part(it.bound, "num")], unit: it.unit.value });
    }
    if (L.struck.items.length) rows.push({ owner: "issuer", label: "struck", text: `${L.struck.items.length} products` });
    if (L.pick.type === "object") {
      const p = L.pick.items;
      for (const quote of p.quotes.items) rows.push({ owner: "store", label: "store's words", parts: [part(quote, "text")] });
      rows.push({ owner: "store", label: "pick", cart: true, tail: p.store.value,
        parts: [part(p.product_key, "text"), ...(p.variant_title.type === "string" ? [part(p.variant_title, "text")] : [])] });
      rows.push({ owner: "store", label: "price", cart: true, parts: [part(p.price_cents, "money")], lead2: "×", parts2: [part(p.quantity, "num")] });
      rows.push(p.delivery.items.quote.type === "string"
        ? { owner: "store", label: "delivery", parts: [part(p.delivery.items.quote, "text")] }
        : { owner: "store", label: "delivery", text: "not stated" });
    } else rows.push({ owner: "none", label: "pick", text: "none" });
    groups.push({ title: L.need.value, rows });
  }
  groups[groups.length - 1].rows.push(
    { owner: "shopper", label: "ordering", parts: [part(t.items.pick_rule.items.label, "text")] },
    { owner: "none", label: "total", cart: true, parts: [part(t.items.total_cents, "money")] });
  return groups;
}

const shown = (id) => {
  const { node, kind } = ui.nodes.get(id), e = ui.edits.get(id);
  const raw = e ? e.raw : node.raw ?? null;
  if (kind === "money") return money(Number(e ? e.raw : node.raw));
  if (kind === "num") return raw;
  return e ? e.value : node.value;
};
const original = (id) => { const { node, kind } = ui.nodes.get(id); return kind === "money" ? money(node.value) : kind === "num" ? node.raw : node.value; };

function partHtml(p) {
  if (ui.editing === p.id) return `<input data-id="${p.id}" value="${esc(String(shown(p.id)).replace(/^\$/, ""))}" aria-label="New value">`;
  return `<button class="val" data-id="${p.id}" title="Change this in the copy">${esc(shown(p.id))}</button>${ui.edits.has(p.id) ? `<s>${esc(original(p.id))}</s>` : ""}`;
}

function renderRows() {
  const all = ui.groups.flatMap((g) => g.rows);
  q("#rows").className = "cols" + (ui.cartOnly ? " cartonly" : "");
  q("#rows").innerHTML = `<div class="cap">What the signature covers</div>` + ui.groups.map((g) => `<div class="grp"><h2>${esc(g.title)}</h2>${g.rows.map((r) => {
    const ids = [...(r.parts || []), ...(r.parts2 || [])].map((p) => p.id);
    const body = r.text ? `<span class="muted">${esc(r.text)}</span>` : `${r.lead ? esc(r.lead) + " " : ""}${(r.parts || []).map(partHtml).join(" · ")}${r.unit ? " " + esc(r.unit) : ""}${r.parts2 ? ` ${esc(r.lead2)} ${r.parts2.map(partHtml).join("")}` : ""}`;
    return `<div class="rw ${r.cart ? "cart" : ""} ${ids.some((id) => ui.edits.has(id)) ? "changed" : ""}"><i class="od ${r.owner}"></i><span class="lb">${esc(r.label)}</span><span class="vs">${body}${r.tail ? `<span class="tail">${esc(r.tail)}</span>` : ""}</span></div>`;
  }).join("")}</div>`).join("");
  const input = q("#rows input");
  if (input) { input.focus(); input.select(); }
  const strip = (lit) => `<span class="strip">${all.map((r) => `<i class="${lit(r) ? "on" : ""}"></i>`).join("")}</span>`;
  const cart = all.filter((r) => r.cart).length;
  q("#cover").innerHTML = `<button class="cv" id="cartview" aria-pressed="${ui.cartOnly}"><span>A signature over the cart covers</span><b>${cart} of ${all.length} rows</b>${strip((r) => r.cart)}</button>
    <div class="cv"><span>This signature covers</span><b>${all.length} of ${all.length} rows</b>${strip(() => true)}</div>`;
}

// ---------- the fingerprint and the check ----------
function paint(bytes) {
  const pat = q("#pat");
  if (!pat.children.length) pat.innerHTML = "<i></i>".repeat(256);
  [...pat.children].forEach((cell, i) => cell.classList.toggle("on", !!(bytes[i >> 3] & (128 >> (i & 7)))));
}

function renderCheck() {
  const p = ui.proof, r = ui.now, real = ui.real, edited = ui.edits.size > 0, who = p.approver.name || "the approver";
  paint(r.bytes);
  const onPhone = real.signedFingerprint || real.fingerprint;  // the phone computes it from the same canonical text
  const same = r.fingerprint === onPhone;
  q("#codes").innerHTML = `<span class="code ${same ? "" : "off"}" title="${esc(r.fingerprint)}">${esc(short(r.fingerprint))}</span>
    <span class="sum">${esc(p.summary.text)}</span>
    <span class="phone">${ICON.phone}<span>${esc(who)}'s phone ${p.signed ? "showed" : "shows"} ${same ? "the same code" : `<code>${esc(short(onPhone))}</code>`}</span></span>`;
  const restore = edited ? `<button class="link" id="restore">Restore</button>` : "";
  let html;
  if (!p.signature || !p.public_key) {
    html = `<div class="verdict none">Nothing is signed yet: no cart can exist</div>
      <div class="steps"><span>${edited ? "the fingerprint changed with your edit" : "change a value: the fingerprint follows"}</span></div>${restore}`;
  } else if (r.valid) {
    html = `<div class="verdict"><span class="tickmark">✓</span>Verified in this browser with ${esc(who)}'s public key</div>
      <div class="steps"><span class="ok">SHA-256 recomputed</span><span class="ok">ECDSA P-256 signature</span><span>seq ${esc(p.signature.seq)}</span></div>`;
  } else if (edited) {
    html = `<div class="verdict bad">Not what ${esc(who)} signed</div>
      <div class="steps"><span class="no">fingerprint differs</span><span class="${r.coversThis ? "ok" : "no"}">signature over this copy</span></div>${restore}`;
  } else {
    html = `<div class="verdict bad">${real.messageVerifies ? `The sheet is no longer what ${esc(who)} signed` : "The signature does not verify with this key"}</div>
      <div class="steps"><span class="${real.fingerprint === real.signedFingerprint ? "ok" : "no"}">fingerprint</span><span class="${real.messageVerifies ? "ok" : "no"}">signature</span></div>`;
  }
  q("#status").innerHTML = html;
}

async function recompute() {
  const edits = [...ui.edits].map(([id, e]) => ({ start: ui.nodes.get(id).node.start, end: ui.nodes.get(id).node.end, raw: e.raw }));
  ui.now = await check(ui.proof, splice(ui.proof.canonical, edits));
  renderRows();
  renderCheck();
}

function commit(id, text) {
  const { node, kind } = ui.nodes.get(id);
  ui.editing = null;
  let raw = null, value = text;
  if (kind === "text") raw = jsonString(text);
  else if (/^\s*-?\d+(\.\d+)?\s*$/.test(text)) raw = kind === "money" ? String(Math.round(Number(text) * 100)) : text.trim();
  if (raw === null || raw === (node.raw ?? jsonString(node.value))) ui.edits.delete(id);  // not a number, or unchanged
  else ui.edits.set(id, { raw, value });
  recompute();
}

// ---------- 1. who holds what ----------
function renderLanes() {
  const p = ui.proof, who = p.approver.name || "the approver", carts = p.carts.length;
  const holds = (cls, icon, text) => `<span class="holds ${cls}">${icon}${esc(text)}</span>`;
  const events = p.events.map((e, i) => {
    const a = LANE[e.from], b = LANE[e.to], t = `<time>${clock(e.at)}</time>`;
    if (a === b) return `<div class="lg ev ${ui.played ? "" : "play"}" style="--i:${i};--a:${a}">${t}<span class="at ${e.bad ? "bad" : ""}"><i class="dot"></i>${esc(e.text)}</span></div>`;
    return `<div class="lg ev ${ui.played ? "" : "play"}" style="--i:${i};--a:${Math.min(a, b)};--n:${Math.abs(a - b) + 1}">${t}<span class="go ${b > a ? "r" : "l"} ${e.bad ? "bad" : ""}"><i></i><span>${esc(e.text)}</span></span></div>`;
  });
  if (!p.signed) events.push(`<div class="lg ev gate ${ui.played ? "" : "play"}" style="--i:${p.events.length};--a:4"><time></time><span class="at"><i class="dot"></i>cart gate closed: no signature</span></div>`);
  q("#lanes").innerHTML = `<div class="cap">Who holds what</div>
    <div class="lg head"><span></span>
      <div class="lane"><b>${esc(who)}'s phone</b>${p.public_key ? holds("priv", ICON.key, "private key") : holds("none", ICON.key, "no key yet")}<span class="cap">made on the phone, never leaves it</span></div>
      <div class="lane"><b>Sign-Off, the agent</b>${p.public_key ? holds("", ICON.key, "public key " + p.public_key.key_id.slice(0, 8)) : holds("none", ICON.key, "no public key")}<span class="cap">can check a signature, cannot make one</span></div>
      <div class="lane"><b>The stores</b>${carts ? holds("", "", carts + (carts === 1 ? " cart" : " carts")) : holds("none", "", "no cart")}<span class="cap">${carts ? "made after the check, from the signed picks" : "none until a signature verifies"}</span></div>
    </div><div class="evs">${events.join("") || `<div class="lg ev" style="--a:2"><time></time><span class="at empty">Nothing has happened in this run yet</span></div>`}</div>`;
  ui.played = true;
}

function renderTop() {
  const p = ui.proof;
  const at = p.signature && p.signature.at ? new Date(p.signature.at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "";
  q("#top").innerHTML = `<span class="brand">Sign-Off</span>
    <span class="sheet">${esc(p.sheet.title || p.sheet.id)}</span>
    <nav class="tabs" aria-label="Views"><a href="/">Decision</a><a href="/trail/">Trail</a><a href="/graph/">Memory</a><a href="/talk/">Conversations</a><a href="/seal/" aria-current="page">Signature</a></nav>
    <span class="meta">${[p.sheet.invented ? "invented people" : "", p.mode === "replay" ? "replay of cached store data" : p.mode === "fixture" ? "fixture data" : ""].filter(Boolean).join(" · ")}</span>
    <span class="grow"></span>
    <span class="pill ${p.signed ? "signed" : ""}">${p.signed ? "Signed " + at : "Not signed"}</span>`;
}

async function load() {
  const r = await fetch("/api/seal/proof");
  if (!r.ok) return;
  const text = await r.text();
  if (text === ui.key) return;
  const proof = JSON.parse(text);
  if (!ui.proof || proof.canonical !== ui.proof.canonical) { ui.edits.clear(); ui.editing = null; }  // a new sheet: the copy starts again
  if (ui.proof && proof.events.length !== ui.proof.events.length) ui.played = false;
  ui.key = text;
  ui.proof = proof;
  ui.groups = build(proof);
  ui.real = await check(proof, proof.canonical);
  const preset = P.get("edit");  // ?edit=300~250 changes the first value shown as 300 to 250 (for a link or a screenshot)
  if (preset && !ui.preset) {
    ui.preset = true;
    const [from, to] = preset.split("~");
    const hit = [...ui.nodes.keys()].find((id) => String(original(id)) === from);
    if (hit !== undefined) { commit(hit, to); renderTop(); renderLanes(); return; }
  }
  renderTop();
  renderLanes();
  await recompute();
}

document.addEventListener("click", (e) => {
  const val = e.target.closest(".val");
  if (val) { ui.editing = Number(val.dataset.id); renderRows(); }
  if (e.target.closest("#restore")) { ui.edits.clear(); ui.editing = null; recompute(); }
  if (e.target.closest("#cartview")) { ui.cartOnly = !ui.cartOnly; renderRows(); }
});
document.addEventListener("keydown", (e) => {
  if (!e.target.matches("#rows input")) return;
  if (e.key === "Enter") commit(Number(e.target.dataset.id), e.target.value);
  if (e.key === "Escape") { ui.editing = null; renderRows(); }
});
document.addEventListener("focusout", (e) => {
  if (e.target.matches("#rows input") && ui.editing === Number(e.target.dataset.id)) commit(Number(e.target.dataset.id), e.target.value);
});
load();
setInterval(() => { if (ui.editing === null) load(); }, 5000);
