// Motion helpers. Every animation here is started by a real change in /api/state (or a line being opened);
// prefers-reduced-motion or ?motion=0 turns all of it off.
const params = new URLSearchParams(location.search);
export const MOTION = params.get("motion") !== "0" && !matchMedia("(prefers-reduced-motion: reduce)").matches;
export const EASE = "cubic-bezier(.3, .1, .2, 1)";

const stage = () => document.getElementById("stage");

/** An element's box in the 960 x 540 canvas's own pixels (the canvas is scaled to the window). */
export function box(el) {
  const s = stage().getBoundingClientRect(), r = el.getBoundingClientRect(), k = s.width / 960;
  return { x: (r.left - s.left) / k, y: (r.top - s.top) / k, w: r.width / k, h: r.height / k };
}

/** Fade and rise into place after `delay` ms. Before the delay the element is not visible. */
export function arrive(el, delay = 0, duration = 260, rise = 4) {
  if (!MOTION || !el) return;
  el.animate([{ opacity: 0, transform: `translateY(${rise}px)` }, { opacity: 1, transform: "none" }],
    { duration, delay, easing: EASE, fill: "backwards" });
}

/** Opacity only (for SVG and for things that must not shift). */
export function appear(el, delay = 0, duration = 240, from = 0) {
  if (!MOTION || !el) return;
  el.animate([{ opacity: from }, { opacity: 1 }], { duration, delay, easing: "ease-out", fill: "backwards" });
}

/** A copy of `src` travels to `dst` and grows to its size; `dst` shows as it lands. */
export function fly(src, dst, delay = 0, duration = 420) {
  if (!MOTION || !src || !dst) return;
  const a = box(src), b = box(dst), layer = document.getElementById("fly");
  if (!a.w || !b.w) return;
  const ghost = document.createElement("span");
  ghost.className = "flyer";
  ghost.textContent = src.textContent;
  const cs = getComputedStyle(src);
  Object.assign(ghost.style, { left: a.x + "px", top: a.y + "px", fontFamily: cs.fontFamily, fontSize: cs.fontSize,
    fontWeight: cs.fontWeight, letterSpacing: cs.letterSpacing, color: cs.color, lineHeight: a.h + "px" });
  layer.appendChild(ghost);
  const scale = b.h / a.h, end = `translate(${b.x - a.x}px, ${b.y - a.y}px) scale(${scale})`;
  ghost.animate([{ transform: "none", opacity: 0 }, { transform: "none", opacity: 1, offset: 0.12 },
    { transform: end, opacity: 1, offset: 0.86 }, { transform: end, opacity: 0 }],
    { duration, delay, easing: EASE, fill: "both" }).finished.then(() => ghost.remove(), () => ghost.remove());
  dst.animate([{ opacity: 0 }, { opacity: 0, offset: 0.8 }, { opacity: 1 }], { duration, delay, fill: "backwards" });
}

/** A number rolls from its old value to its new one. Text that is not a number fades instead. */
export function roll(el, before, after, duration = 320) {
  if (!MOTION || before === after) return;
  const parse = (s) => /^(\D*?)(-?\d+(?:\.\d+)?)(.*)$/s.exec(s);
  const a = parse(before), b = parse(after);
  if (!a || !b || a[1] !== b[1] || a[3] !== b[3]) return appear(el, 0, 260, 0.2);
  const from = parseFloat(a[2]), to = parseFloat(b[2]), places = (b[2].split(".")[1] || "").length;
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration), e = 1 - (1 - t) ** 3;
    el.textContent = b[1] + (from + (to - from) * e).toFixed(places) + b[3];
    if (t < 1 && el.isConnected) requestAnimationFrame(step); else if (el.isConnected) el.textContent = after;
  };
  requestAnimationFrame(step);
}
