// What left, and what never did: each class of fact the agent holds against each outside party.
// Drawn from GET /api/trail/left (the outbound ledger and the guard's records); the page decides nothing.
// One line of totals; click it for the matrix; click a cell for the records behind it.
const params = new URLSearchParams(location.search);
const MOTION = params.get("motion") === "1"
  || (params.get("motion") !== "0" && !matchMedia("(prefers-reduced-motion: reduce)").matches && !navigator.webdriver);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const dot = (owner) => `<i class="od ${owner || ""}"></i>`;
const clock = (at) => (at ? String(at).slice(11, 19) : "");

let root = null, data = null, drawn = "", open = location.hash === "#left", sel = null;

/** The totals, as the records have them. Nothing else in prose. */
function line(t) {
  const sealed = t.carried ? `<b class="${t.carried_to_stores ? "bad" : ""}">${t.carried}</b> carried a limit, a measurement or a name${t.carried_to_stores ? `, <b class="bad">${t.carried_to_stores}</b> to a store` : ", none to a store"}`
    : "<b>0</b> carried a limit, a measurement or a name";
  const guard = t.messages ? `<b>${t.spans_stopped}</b> stopped at the guard` : "";
  const undeclared = t.undeclared ? `<b class="bad">${t.undeclared}</b> held one the sender did not declare` : "";
  return [`<b>${t.payloads}</b> payloads to <b>${t.recipients}</b> recipients`, sealed, undeclared, guard].filter(Boolean).join('<span class="sep">·</span>');
}

function cellHtml(row, col, c) {
  const id = `${row.id}|${col.id}`, on = sel === id ? " sel" : "";
  const parts = [];
  if (c.stopped) parts.push(`<span class="lv stopped" data-part="stopped">stopped <i>${c.stopped}</i></span>`);
  if (c.found) parts.push(`<span class="lv found" data-part="found">found <i>${c.found}</i></span>`);
  if (c.sent) parts.push(`<span class="lv sent" data-part="sent">sent <i>${c.sent}</i></span>`);
  if (!parts.length) parts.push(c.state === "never" ? `<span class="lv never">never</span>` : `<span class="lv unknown">not recorded</span>`);
  return `<button class="lc${on}" data-cell="${esc(id)}">${parts.join("")}</button>`;
}

function detail() {
  if (!sel) return "";
  const [rid, cid] = sel.split("|"), row = data.rows.find((r) => r.id === rid), col = data.columns.find((c) => c.id === cid);
  if (!row || !col) return "";
  const c = data.cells[rid][cid];
  const ledger = (it) => `<div class="li"><span>${clock(it.at)}</span><span>${esc(it.purpose || "")}${it.match ? ` <b class="bad">${esc(it.match)}</b>` : ""}</span><code title="SHA-256 of the payload">${esc(String(it.hash || "").slice(0, 16))}</code></div>`;
  const guard = (it) => `<div class="li"><span>${clock(it.at)}</span><span>${it.words.map((w) => `<s>${esc(w)}</s>`).join(" ")} <i>${esc(it.to || "")} · ${esc(it.decision || "")}</i></span><span></span></div>`;
  const head = `${dot(row.owner)}${esc(row.label)} <span class="faint">to</span> ${esc(col.label)}`;
  let body = "";
  if (c.stopped) body += `<div class="cap">stopped by the guard · ${c.stopped} of ${c.checked} messages</div>${c.stopped_items.map(guard).join("")}`;
  if (c.found) body += `<div class="cap bad">found by the ledger's search, not declared by the sender · ${c.found} of ${c.checked} payloads</div>${c.found_items.map(ledger).join("")}`;
  if (c.sent) body += `<div class="cap">sent · ${c.sent} of ${c.checked} ${cid === "agents" ? "messages" : "payloads"}</div>${c.sent_items.map(ledger).join("")}`;
  if (!c.stopped && !c.found && !c.sent) {
    body = c.state === "never" ? `<div class="cap">${c.checked} ${cid === "agents" ? "messages checked by the guard" : "payloads checked by the ledger's search"} · none held it</div>`
      : `<div class="cap">no record can tell: ${cid === "agents" ? "the guard does not look for this class" : "the ledger's search cannot find this class and the sender did not declare it"}</div>`;
  }
  return `<div class="ld"><div class="lh">${head}<button class="x" data-cell="" aria-label="Close">×</button></div>${body}</div>`;
}

function html() {
  const t = data.totals;
  const head = `<button class="ll" data-left-toggle aria-expanded="${open}"><span class="lt">What left, and what never did</span><span class="lline">${line(t)}</span><span class="chev">›</span></button>`;
  if (!open) return head;
  if (!data.rows.length || !data.columns.length) return head + `<div class="lm"><span class="faint">no outbound records</span></div>`;
  const cols = `grid-template-columns: minmax(17rem, 1.6fr) repeat(${data.columns.length}, minmax(6rem, 1fr));`;
  const header = `<div class="lr hd" style="${cols}"><span></span>${data.columns.map((c) => `<span class="lcol" title="${esc(c.members.join(", "))}"><b>${esc(c.label)}</b><i>${esc(c.kind)} · ${c.payloads}</i></span>`).join("")}</div>`;
  const rows = data.rows.map((r) => `<div class="lr" style="${cols}"><span class="lrow" title="${esc(r.travel || "")}">${dot(r.owner)}<b>${esc(r.label)}</b><i>${esc(r.example)}</i></span>${data.columns.map((c) => cellHtml(r, c, data.cells[r.id][c.id])).join("")}</div>`).join("");
  return `${head}<div class="lm">${header}${rows}</div>${detail()}`;
}

function render(move) {
  root.innerHTML = html();
  if (move && MOTION && open) {          // the panel opens: rows arrive in turn, and what was stopped is struck through
    [...root.querySelectorAll(".lr")].forEach((n, i) => n.animate([{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }],
      { duration: 300, delay: i * 40, easing: "cubic-bezier(.2, .7, .2, 1)", fill: "backwards" }));
    [...root.querySelectorAll(".lv.stopped")].forEach((n, i) => n.animate([{ backgroundSize: "0% 1px" }, { backgroundSize: "100% 1px" }],
      { duration: 600, delay: 500 + i * 80, easing: "cubic-bezier(.4, 0, .2, 1)", fill: "backwards" }));
  }
}

/** Draws the panel into `el`. Redraws only when the records behind it changed. */
export function update(el, next) {
  root = el;
  const now = JSON.stringify(next || null);
  if (now === drawn) return;
  drawn = now;
  data = next;
  el.hidden = !next;
  if (next) render(false);
}

document.addEventListener("click", (ev) => {
  if (!root || !data) return;
  const toggle = ev.target.closest("[data-left-toggle]"), cell = ev.target.closest("#left [data-cell]");
  if (toggle) {
    open = !open;
    sel = null;
    render(true);
    if (open) root.scrollIntoView({ block: "nearest", behavior: MOTION ? "smooth" : "auto" });
  } else if (cell) {
    sel = sel === cell.dataset.cell || !cell.dataset.cell ? null : cell.dataset.cell;
    render(false);
  }
});
