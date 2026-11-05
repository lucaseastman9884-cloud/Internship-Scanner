// P8: WCAG AA contrast for every text/background pair, in BOTH themes, read straight from the theme
// tokens in site/styles.css. 4.5:1 for normal text; 3:1 for focus rings (WCAG 1.4.11, UI and
// graphical objects). Large text isn't given the 3:1 allowance here: everything is held to 4.5:1.
//
// Glass panels and badges are see-through, so each background is worked out by stacking the layers
// as the browser does: the page colour, then the brightest point of each moving glow orb (or none),
// then the panel, card or chip on top. Every combination must pass.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../../site/styles.css", import.meta.url), "utf8");

function tokens(name) {
  const start = css.indexOf(`/* tokens:${name}`);
  assert.ok(start >= 0, `no tokens:${name} block`);
  const block = css.slice(start, css.indexOf("/* end tokens */", start));
  const out = {};
  for (const m of block.matchAll(/--([\w-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}

function parseColor(v) {
  let m = /^#([0-9a-f]{6})$/i.exec(v);
  if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)).concat(1);
  m = /^rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\)$/i.exec(v);
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3]), Number(m[4])];
  throw new Error(`can't read colour ${v}`);
}

// Paint `top` (may be see-through) over an opaque `bottom`.
const over = (top, bottom) => [0, 1, 2].map((i) => top[i] * top[3] + bottom[i] * (1 - top[3])).concat(1);
const withAlpha = (c, a) => [c[0], c[1], c[2], a];

function luminance([r, g, b]) {
  const ch = (v) => { const s = v / 255; return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
}
export function ratio(a, b) {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

const results = [];

for (const theme of ["dark", "light"]) {
  test(`contrast: ${theme} theme passes WCAG AA`, () => {
    const t = tokens(theme);
    const c = (name) => { assert.ok(t[name], `${theme}: missing --${name}`); return parseColor(t[name]); };
    const bg = c("bg");
    const glowAlpha = Number(t["glow-opacity"]);
    assert.ok(glowAlpha > 0 && glowAlpha <= 1);
    // The page behind everything: plain, or under the centre of each glow orb.
    const pages = [["page", bg], ...["glow-1", "glow-2", "glow-3"].map((g) => [`page+${g}`, over(withAlpha(c(g), glowAlpha), bg)])];
    const layered = (layer, on = pages) => on.map(([n, base]) => [`${layer}/${n}`, over(c(layer), base)]);
    const panels = [...layered("panel"), ["panel-solid", c("panel-solid")]];
    const cards = [...layered("card"), ...layered("card", panels)]; // cards sit on the page and inside panels
    const surfaces = [...pages, ...panels, ...cards];
    const on = (layer, under) => under.map(([n, base]) => [`${layer}/${n}`, over(c(layer), base)]);

    const pairs = [
      // [label, foreground token, backgrounds, minimum]
      ["body text", "text", surfaces, 4.5],
      ["muted text", "muted", surfaces, 4.5],
      ["links", "link", surfaces, 4.5],
      ["failure text", "bad", [...panels, ...cards], 4.5],
      ["NEW badge", "new", cards, 4.5],
      ["badge text", "badge-text", [...on("badge-bg", cards), ...on("badge-bg", panels)], 4.5],
      ["warning text", "warn-text", [...on("warn-bg", pages), ...on("warn-bg", cards), ...on("warn-bg", panels)], 4.5],
      ["chip +", "plus-text", [...on("plus-bg", panels), ...on("plus-bg", cards)], 4.5],
      ["chip −", "minus-text", [...on("minus-bg", panels), ...on("minus-bg", cards)], 4.5],
      ["chip 0", "neutral-text", [...on("neutral-bg", panels), ...on("neutral-bg", cards)], 4.5],
      ["button text", "on-accent", [["accent-1", c("accent-1")], ["accent-2", c("accent-2")], ["accent-3", c("accent-3")]], 4.5],
      ["focus ring", "focus", surfaces, 3],
    ];
    const failures = [];
    let worst = Infinity;
    for (const [label, fg, backs, min] of pairs) {
      for (const [where, back] of backs) {
        const r = ratio(c(fg), back);
        worst = Math.min(worst, min === 4.5 ? r : worst);
        results.push({ theme, label, where, r });
        if (r < min) failures.push(`${label} (--${fg}) on ${where}: ${r.toFixed(2)}:1 < ${min}:1`);
      }
    }
    const focusWorst = Math.min(...results.filter((x) => x.theme === theme && x.label === "focus ring").map((x) => x.r));
    console.log(`${theme}: ${results.filter((x) => x.theme === theme).length} pairs, worst text ${worst.toFixed(2)}:1, worst focus ${focusWorst.toFixed(2)}:1`);
    assert.deepEqual(failures, []);
  });
}

test("both themes define the same tokens", () => {
  assert.deepEqual(Object.keys(tokens("dark")).sort(), Object.keys(tokens("light")).sort());
});

test("the contrast maths matches WCAG's reference points", () => {
  assert.equal(ratio([0, 0, 0], [255, 255, 255]).toFixed(1), "21.0");
  assert.equal(ratio([118, 118, 118], [255, 255, 255]).toFixed(2), "4.54"); // #767676, the classic AA grey
});
