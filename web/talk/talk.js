// Conversations: draws GET /api/talk/threads. Every string from a store is untrusted text: it is escaped, never run.
const q = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hhmm = (at) => (at ? new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "");
const ui = { data: null, id: new URLSearchParams(location.search).get("id"), open: new Set(), key: "" };
if (new URLSearchParams(location.search).get("open")) ui.open.add(ui.id + ":" + new URLSearchParams(location.search).get("open"));

// text with some character ranges wrapped in a tag: the answering words of a reply, the removed words of a draft
function marked(text, spans, tag) {
  let out = "", at = 0;
  for (const s of [...spans].sort((a, b) => a.start - b.start)) {
    if (s.start < at) continue;
    out += esc(text.slice(at, s.start)) + `<${tag}${s.mark ? ` title="${esc(s.mark)}"` : ""}>${esc(text.slice(s.start, s.end))}</${tag}>`;
    at = s.end;
  }
  return out + esc(text.slice(at));
}

const withheld = (t) => t.turns.reduce((n, turn) => n + turn.removed.length, 0);
const notSent = (t) => t.turns.filter((turn) => !turn.sent).length;

function renderTop() {
  const d = ui.data;
  const n = d.threads.length, cut = d.threads.reduce((a, t) => a + withheld(t), 0);
  q("#top").innerHTML = `<span class="brand">Sign-Off</span>
    <span class="sheet">${esc(d.title || d.sheet)}</span>
    <nav class="tabs" aria-label="Views"><a href="/">Decision</a><a href="/trail/">Trail</a><a href="/talk/" aria-current="page">Conversations</a></nav>
    <span class="meta">${n} with the stores' own agents</span>
    <span class="grow"></span>
    <span class="pill">${cut} withheld</span>`;
  const mark = (k) => esc(d.marks[k] || k);
  q("#band").innerHTML = `<span class="cap">A store's agent may receive</span>${d.rule.may.map((k) => `<span class="pill">${mark(k)}</span>`).join("")}
    <span class="cap">never</span>${d.rule.sealed.map((k) => `<span class="pill sealed">${mark(k)}</span>`).join("")}`;
}

function renderList() {
  const group = (origin, cap) => {
    const rows = ui.data.threads.filter((t) => t.origin === origin).reverse();
    if (!rows.length) return "";
    return `<div class="cap">${cap}</div>` + rows.map((t) => {
      const w = withheld(t), bad = notSent(t) && !t.turns.some((turn) => turn.sent);
      return `<button class="item" data-id="${esc(t.id)}" aria-current="${t.id === ui.id}">
        <span><b><i class="od store"></i>${esc(t.store)}</b><span class="muted small">${esc(t.title || "")}</span></span>
        <span class="n ${bad ? "bad" : ""}">${bad ? "not sent" : w ? w + " withheld" : hhmm(t.asked_at)}</span></button>`;
    }).join("");
  };
  q("#list").innerHTML = group("shopper", "The shopper asked") + group("agent", "The agent asked");
}

function turnHtml(t, turn, prev) {
  const key = t.id + ":" + turn.n, open = ui.open.has(key);
  const counts = {};
  for (const s of turn.removed) counts[s.mark] = (counts[s.mark] || 0) + 1;
  const marks = Object.entries(counts).map(([m, n]) => `<span class="pill">${esc(m)}${n > 1 ? `<i>${n}</i>` : ""}</span>`).join("");
  let ours;
  if (turn.sent) {
    const lead = prev && prev.sent ? `Earlier I asked: "${prev.sent}" ` : "";
    const body = lead && turn.sent.startsWith(lead)
      ? `<span class="carried" title="${esc(lead)}">${esc(lead)}</span>${esc(turn.sent.slice(lead.length))}` : esc(turn.sent);
    ours = `<div class="who ours-who">Sent ${hhmm(turn.reply_at)}</div><div class="msg ours">${body}</div>`;
  } else {
    ours = `<div class="who ours-who"><span class="bad">Not sent</span></div><div class="msg ours refused">${esc(turn.why || "")}</div>`;
  }
  const row = turn.removed.length ? `<button class="wh" data-open="${esc(key)}" aria-expanded="${open}">Withheld ${marks}<span class="caret">${open ? "▴" : "▾"}</span></button>` : "";
  const behind = open ? `<div class="behind">${turn.n === 1 && t.origin === "shopper" ? `<span class="cap">The shopper's words</span>${esc(t.purpose)}` : ""}
      <span class="cap">The agent's draft</span>${marked(turn.draft, turn.removed, "s")}
      ${turn.still.length ? `<span class="cap">Rewritten once, still not clean</span>${marked(turn.rewritten || "", turn.still, "s")}` : ""}</div>` : "";
  const reply = turn.reply ? `<div class="who">${esc(t.store)}'s agent</div><div class="msg theirs">${marked(turn.reply, turn.answers || [], "mark")}</div>` : "";
  return `<div class="turn">${ours}${row}${behind}${reply}</div>`;
}

function renderThread() {
  const t = ui.data.threads.find((x) => x.id === ui.id);
  if (!t) { q("#thread").innerHTML = `<div class="empty">No conversation yet</div>`; return; }
  q("#thread").innerHTML = `<div class="row"><h1>${esc(t.title || t.store)}</h1><span class="cap"><i class="od store"></i>${esc(t.store)} · ${hhmm(t.asked_at)}</span></div>
    ${t.error ? `<div class="msg refused">${esc(t.error)}</div>` : ""}
    ${t.turns.map((turn, i) => turnHtml(t, turn, t.turns[i - 1])).join("")}`;
}

function render() { renderTop(); renderList(); renderThread(); }

async function load() {
  const r = await fetch("/api/talk/threads" + (new URLSearchParams(location.search).get("sheet") ? "?sheet=" + encodeURIComponent(new URLSearchParams(location.search).get("sheet")) : ""));
  if (!r.ok) return;
  const text = await r.text();
  if (text === ui.key) return;
  ui.key = text;
  ui.data = JSON.parse(text);
  if (!ui.data.threads.some((t) => t.id === ui.id)) {  // open the newest conversation in which something was withheld and sent
    const ts = [...ui.data.threads].reverse();
    ui.id = (ts.find((t) => withheld(t) && t.turns.some((turn) => turn.sent)) || ts[0] || {}).id;
  }
  render();
}

document.addEventListener("click", (e) => {
  const item = e.target.closest(".item"), wh = e.target.closest(".wh");
  if (item) { ui.id = item.dataset.id; render(); }
  if (wh) { ui.open.has(wh.dataset.open) ? ui.open.delete(wh.dataset.open) : ui.open.add(wh.dataset.open); renderThread(); }
});
load();
setInterval(load, 5000);
