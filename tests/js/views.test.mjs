// P8 views, rendered into a fake DOM: hostile company and listing text stays text on every page,
// unsafe links are never clickable, and every route renders (unknown ones show "Not found").
import { test } from "node:test";
import assert from "node:assert/strict";
import { installFakeDom, allElements, textOf } from "./fake-dom.mjs";

installFakeDom();
const { listingCard, renderToday, renderCompanies, renderCompany, renderContacts, renderNotFound, companyCard } = await import("../../site/js/views.js");
const { buildCompanies, todaySummary, parseRoute, resolveRoute } = await import("../../site/js/hub.js");
const { reasonChip, reasonSign, gauge } = await import("../../site/js/dom.js");

const SITE = { posted_within_days: [1, 3, 7, 30], default_sort: "score", default_theme: "dark", linkedin_school_id: "164452",
  linkedin_school_name: "Iowa State University", manual_first_tags: ["ib"], deadline_window_days: 14 };
const CONFIG = { home: { name: "Ames, IA", lat: 42.03, lng: -93.62 }, radius_miles: 150, seasons: ["Not stated"],
  role_categories: [], new_badge_days: 3, remote_sections: [{ tag: "remote_iowa", label: "Remote — Iowa" }],
  state_codes: ["IA"], site: SITE };
const TODAY = "2026-11-05";

const EVIL_NAME = `<img src=x onerror=alert(1)>Evil & Co`;
const EVIL_TITLE = `<script>alert("t")</script><b>Intern</b>`;
const EVIL_ERROR = `<iframe src=javascript:alert(2)>`;
const REGISTRY = { companies: [
  { id: "evil-co", name: EVIL_NAME, ats: "manual", careers_url: "javascript:alert(3)", cities: [], priority: 1, tags: ["<i>ib</i>"], linkedin_name: null },
  { id: "safe-co", name: "Safe Co", ats: "workday", careers_url: "https://safe.example/jobs", cities: [], priority: 2, tags: [], linkedin_name: null },
  { id: "data-co", name: "Data Co", ats: "manual", careers_url: "data:text/html,<script>alert(4)</script>", cities: [], priority: 2, tags: [] },
] };
const STATUS = { "safe-co": { company_id: "safe-co", company: "Safe Co", ats: "workday", last_checked: "2026-11-05T12:00:00Z",
  fetch_health: { status: "error", last_error: EVIL_ERROR, consecutive_failures: 3 } } };
const LISTINGS = [
  { id: "x1", title: EVIL_TITLE, company: EVIL_NAME, company_id: "evil-co", status: "open", first_seen: "2026-11-05",
    date_posted: "2026-11-05", deadline: "2026-11-10", relevance_score: 77, tags: ["remote_iowa"], season: null,
    location_label: `<svg onload=alert(5)>`, apply_url: "javascript:alert(6)", match_reasons: ["+20 <img src=y>"] },
  { id: "x2", title: "Plain Intern", company: "Safe Co", company_id: "safe-co", status: "closed", first_seen: "2026-10-01",
    date_posted: null, relevance_score: 40, tags: [], last_known_open: "2026-10-20", recurring: true },
  { id: "x3", title: "Weird id", company: "Weird", company_id: "javascript:alert(7)", status: "open", first_seen: "2026-11-01", tags: [] },
];
const META = { run_finished: "2026-11-05T12:52:21+00:00", totals: { companies_fetched_ok: 1, companies_failed: 1 },
  errors: [{ company: EVIL_NAME }], companies: [] };

function makeCtx() {
  const companies = buildCompanies(REGISTRY, STATUS, LISTINGS, CONFIG);
  return {
    config: CONFIG, listings: LISTINGS, companies, companyByName: new Map(companies.map((c) => [c.name, c])),
    companyQuery: "", today: TODAY, animate: false, getEntry: () => null, openDrawer() {}, openListings() {},
    summary: todaySummary(LISTINGS, CONFIG, META, TODAY),
  };
}

const ALLOWED_TAGS = new Set(["A", "BUTTON", "CIRCLE", "DD", "DIV", "DL", "DT", "H1", "H2", "H3", "HEADER", "INPUT", "LABEL",
  "LI", "OL", "P", "SECTION", "SPAN", "SVG", "UL"]);

function assertSafe(nodes, label) {
  const els = allElements(nodes);
  assert.ok(els.length > 0, label);
  for (const e of els) {
    assert.ok(ALLOWED_TAGS.has(e.tagName), `${label}: unexpected <${e.tagName}>`);
    for (const [k, v] of e.attributes) {
      assert.ok(!/^on/i.test(k), `${label}: event attribute ${k}`);
      if (k === "href") assert.match(v, /^(#\/[a-z0-9/-]*|https?:\/\/)/, `${label}: href ${v}`);
      assert.ok(!/javascript:|data:text/i.test(v), `${label}: ${k}=${v}`);
    }
  }
  return els;
}

test("hostile names render as text on Today", () => {
  const nodes = renderToday(makeCtx());
  assertSafe(nodes, "today");
  const text = textOf(nodes);
  assert.ok(text.includes(EVIL_TITLE), "deadline list shows the title as text");
  assert.ok(text.includes(EVIL_NAME), "failed source shows the name as text");
});

test("hostile names render as text on Companies", () => {
  const nodes = renderCompanies(makeCtx());
  const els = assertSafe(nodes, "companies");
  const text = textOf(nodes);
  assert.ok(text.includes(EVIL_NAME) && text.includes(EVIL_ERROR) && text.includes("<I>IB</I>") === false);
  assert.ok(text.includes("<i>ib</i>") || text.includes("<I>IB</I>") || text.includes("<i>ib</i>".toUpperCase()));
  assert.ok(els.some((e) => e.tagName === "A" && e.getAttribute("href") === "#/company/evil-co"));
});

test("hostile company page: text stays text, javascript: and data: careers links aren't clickable", () => {
  const ctx = makeCtx();
  const evil = ctx.companies.find((c) => c.id === "evil-co");
  const nodes = renderCompany(ctx, evil);
  const els = assertSafe(nodes, "company");
  const text = textOf(nodes);
  assert.ok(text.includes(EVIL_NAME) && text.includes(EVIL_TITLE));
  assert.ok(text.includes("javascript:alert(3)"), "the unsafe URL is shown as plain text");
  assert.ok(!els.some((e) => e.tagName === "A" && !/^(https:\/\/|#\/)/.test(e.getAttribute("href") || "")),
    "every link is https or an in-app route");
  const dataCo = renderCompany(ctx, ctx.companies.find((c) => c.id === "data-co"));
  assertSafe(dataCo, "data-co");
  // LinkedIn links: exactly two, new tab, no opener or referrer, name encoded.
  const li = els.filter((e) => e.tagName === "A" && (e.getAttribute("href") || "").startsWith("https://www.linkedin.com/"));
  assert.equal(li.length, 2);
  for (const a of li) {
    assert.equal(a.getAttribute("target"), "_blank");
    assert.equal(a.getAttribute("rel"), "noopener noreferrer");
    assert.ok(!a.getAttribute("href").includes("<"), "the name is URL-encoded");
  }
  assert.ok(text.includes("Your private contacts for this company will appear here after sign-in (P9)."));
});

test("hostile listing card on Listings: text only, no unsafe links", () => {
  const ctx = makeCtx();
  for (const l of LISTINGS) {
    const card = listingCard(l, ctx);
    const els = assertSafe(card, `card ${l.id}`);
    assert.ok(textOf(card).includes(l.title));
    const companyLink = els.find((e) => e.getAttribute("class") === "card-company");
    if (l.id === "x3") assert.equal(companyLink, undefined, "an odd company_id doesn't become a link");
    else assert.equal(companyLink.getAttribute("href"), `#/company/${l.company_id}`);
  }
  // Posted vs first seen labels on cards.
  assert.match(textOf(listingCard(LISTINGS[0], ctx)), /Posted /);
  assert.match(textOf(listingCard(LISTINGS[1], ctx)), /First seen /);
  assert.doesNotMatch(textOf(listingCard(LISTINGS[1], ctx)), /Posted /);
  assert.match(textOf(listingCard(LISTINGS[1], ctx)), /Recurring program/);
  assert.match(textOf(listingCard(LISTINGS[1], ctx)), /Last known open/);
});

test("match-reason chips: colour by sign, text always there", () => {
  assert.equal(reasonSign("+20 location: Chicago metro"), "plus");
  assert.equal(reasonSign("-15 role: no target role keyword found"), "minus");
  assert.equal(reasonSign("−30 title: 'marketing' is off-target"), "minus");
  assert.equal(reasonSign("+0 eligibility: unclear"), "neutral");
  assert.equal(reasonSign("season: not stated"), "neutral");
  const chip = reasonChip("+20 <img src=y>");
  assertSafe(chip, "chip");
  assert.equal(chip.getAttribute("class"), "chip chip-plus");
  assert.match(textOf(chip), /Adds points: \+20 <img src=y>/);
});

test("gauges expose the score as text for screen readers", () => {
  const g = gauge(85);
  assert.equal(g.getAttribute("role"), "img");
  assert.equal(g.getAttribute("aria-label"), "Score 85 of 100");
  assert.equal(gauge(null).getAttribute("aria-label"), "No score");
  const neg = allElements(gauge(-20)).find((e) => e.getAttribute("class") === "gauge-value");
  assert.equal(neg.getAttribute("stroke-dashoffset"), neg.getAttribute("stroke-dasharray"), "a negative score shows an empty ring");
});

test("every route renders, and unknown routes or company ids show Not found", () => {
  const ctx = makeCtx();
  const byId = new Map(ctx.companies.map((c) => [c.id, c]));
  const heading = (nodes) => allElements(nodes).find((e) => e.tagName === "H1").textContent;
  const render = (hash) => {
    const view = resolveRoute(parseRoute(hash), byId);
    switch (view.name) {
      case "today": return ["today", heading(renderToday(ctx))];
      case "companies": return ["companies", heading(renderCompanies(ctx))];
      case "company": return ["company", heading(renderCompany(ctx, view.company))];
      case "contacts": return ["contacts", heading(renderContacts())];
      case "not-found": return ["not-found", heading(renderNotFound(view.what)), textOf(renderNotFound(view.what))];
      default: return [view.name]; // listings and my-list are static markup in index.html
    }
  };
  assert.deepEqual(render(""), ["today", "Today"]);
  assert.deepEqual(render("#/today"), ["today", "Today"]);
  assert.deepEqual(render("#/listings"), ["listings"]);
  assert.deepEqual(render("#/my-list"), ["my-list"]);
  assert.deepEqual(render("#/companies"), ["companies", "Companies"]);
  assert.deepEqual(render("#/company/safe-co"), ["company", "Safe Co"]);
  assert.deepEqual(render("#/contacts"), ["contacts", "Contacts"]);
  const unknownRoute = render("#/does-not-exist");
  assert.equal(unknownRoute[0], "not-found");
  assert.match(unknownRoute[2], /That page doesn't exist/);
  const unknownCompany = render("#/company/no-such-company");
  assert.equal(unknownCompany[0], "not-found");
  assert.match(unknownCompany[2], /That company doesn't exist/);
  // The Not found view always offers a way back.
  assert.ok(allElements(renderNotFound("page")).some((e) => e.tagName === "A" && e.getAttribute("href") === "#/today"));
  assert.match(textOf(renderContacts()), /Coming in P9 — private contacts after Google sign-in\./);
});

test("Companies page: one card per company, IB first", () => {
  const ctx = makeCtx();
  const nodes = renderCompanies(ctx);
  const cards = allElements(nodes).filter((e) => e.getAttribute("class") === "company glass-card");
  assert.equal(cards.length, ctx.companies.length);
  assert.ok(textOf(companyCard(ctx.companies.find((c) => c.id === "safe-co"))).includes("Last fetch failed (3 runs in a row)"));
  assert.match(textOf(companyCard(ctx.companies.find((c) => c.id === "evil-co"))), /Manual/);
});
