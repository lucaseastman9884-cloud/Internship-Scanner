// DOM helpers shared by every view. Untrusted text (listings, company names) only ever becomes a
// text node: nothing here sets innerHTML, and links are made only from http(s) URLs.
import { safeUrl, humanize } from "./lib.js";

const SVG_NS = "http://www.w3.org/2000/svg";

function fill(node, attrs, children) {
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.setAttribute("class", v);
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    node.append(typeof c === "object" && "nodeType" in c ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function el(tag, attrs = {}, ...children) {
  return fill(document.createElement(tag), attrs, children);
}

export function svg(tag, attrs = {}, ...children) {
  return fill(document.createElementNS(SVG_NS, tag), attrs, children);
}

// Off-site links: http(s) only, new tab, no opener and no referrer. Anything else → null.
export function extLink(url, text, attrs = {}) {
  const safe = safeUrl(url);
  if (!safe) return null;
  return el("a", { ...attrs, href: safe, target: "_blank", rel: "noopener noreferrer" }, text);
}

// In-app links are built from route parts we encode ourselves, never from a listing's URL.
export function appLink(hash, text, attrs = {}) {
  return el("a", { ...attrs, href: hash }, text);
}

export function formatDate(ymd) {
  if (typeof ymd !== "string" || !/^\d{4}-\d{2}-\d{2}/.test(ymd)) return null;
  const [y, m, d] = ymd.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function formatTime(iso) {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : new Date(t).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

// ---------- score gauge ----------
const R = 18;
const CIRC = 2 * Math.PI * R; // 113.1

// An SVG ring filled to the score (0–100; negative scores show empty). The number is real text, and
// screen readers get "Score 85 of 100" from the label. `animate` runs the fill-in once.
export function gauge(score, { size = "sm", animate = false } = {}) {
  const has = Number.isFinite(score);
  const frac = has ? Math.max(0, Math.min(100, score)) / 100 : 0;
  const label = has ? `Score ${score} of 100` : "No score";
  return el("span", { class: `gauge gauge-${size}${animate ? " gauge-animate" : ""}`, role: "img", "aria-label": label },
    svg("svg", { viewBox: "0 0 44 44", "aria-hidden": "true", focusable: "false" },
      svg("circle", { class: "gauge-track", cx: "22", cy: "22", r: String(R) }),
      svg("circle", {
        class: "gauge-value", cx: "22", cy: "22", r: String(R),
        "stroke-dasharray": CIRC.toFixed(2), "stroke-dashoffset": (CIRC * (1 - frac)).toFixed(2),
        transform: "rotate(-90 22 22)",
      })),
    el("span", { class: "gauge-num", "aria-hidden": "true" }, has ? String(score) : "–"));
}

// ---------- match-reason chips ----------
// "+20 location: Kansas City metro" → a chip coloured by sign. The text (with its +/− number) is always
// shown, so colour is never the only signal.
export function reasonSign(reason) {
  const m = /^\s*([+\-−])\s*(\d+)/.exec(String(reason));
  if (!m) return "neutral";
  if (Number(m[2]) === 0) return "neutral";
  return m[1] === "+" ? "plus" : "minus";
}

export function reasonChip(reason) {
  const sign = reasonSign(reason);
  const word = { plus: "Adds points", minus: "Removes points", neutral: "No change" }[sign];
  return el("li", { class: `chip chip-${sign}` }, el("span", { class: "sr-only" }, `${word}: `), String(reason));
}

export function tagChip(tag) {
  return el("span", { class: "tag" }, String(tag).toUpperCase().length <= 4 ? String(tag).toUpperCase() : humanize(tag));
}
