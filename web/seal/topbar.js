// The one top bar, as the decision screen prints it (web/screen/ladder.js renderTop): the sheet, the five views, where
// the data is from, the signed pill and the total, all from GET /api/state. Used by /seal/ and /talk/.
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const TABS = [["/", "Decision"], ["/trail/", "Trail"], ["/graph/", "Memory"], ["/talk/", "Conversations"], ["/seal/", "Signature"]];

export async function topBar(el, current) {
  let state = null;
  try { const r = await fetch("/api/state"); state = r.ok ? await r.json() : null; } catch (e) { state = null; }
  const tabs = `<nav class="tabs" aria-label="Views">${TABS.map(([href, label]) => `<a href="${href}"${href === current ? ' aria-current="page"' : ""}>${label}</a>`).join("")}</nav>`;
  if (!state) { el.innerHTML = `<span class="brand">Sign-Off</span>${tabs}`; return null; }
  const { sheet, seal } = state;
  const mode = state.mode === "fixture" ? "fixture data" : state.mode === "replay" ? "replay of cached store data" : "";
  const meta = [sheet.invented ? "invented people" + (state.mode === "fixture" ? "" : ", real stores") : `${state.lines.length} items`, mode].filter(Boolean).join(" · ");
  el.innerHTML = `<span class="brand">Sign-Off</span>
    <span class="sheet">${esc(sheet.title || sheet.id)}</span>
    ${tabs}
    <span class="meta">${esc(meta)}</span>
    <span class="grow"></span>
    <a class="pill ${seal.signed ? "signed" : ""}" href="/seal/">${seal.signed ? "Signed" : "Not signed"}</a>
    <span class="total"><span class="tl">Total</span> <span>$${(state.total_cents / 100).toFixed(2)}</span></span>`;
  return state;
}
