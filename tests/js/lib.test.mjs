// Run with: node --test tests/js/
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  escapeHtml, safeUrl, haversineMiles, milesFromHome, seasonLabel, locationLabel, titlePlace,
  defaultFilters, applyFilters, sortListings, isNew, countLabel, activeFilterCount, healthSummary, NONE_ROLE,
} from "../../site/js/lib.js";

const CONFIG = {
  home: { name: "Ames, IA", lat: 42.025725, lng: -93.622491 },
  radius_miles: 150,
  seasons: ["Summer 2027", "Summer 2028", "Not stated"],
  role_categories: ["investment_banking", "accounting"],
  new_badge_days: 3,
  remote_sections: [{ tag: "remote_iowa", label: "Remote — Iowa" }],
  state_codes: ["IA", "IL", "MO", "OH", "KS"],
};

let n = 0;
function listing(over = {}) {
  n += 1;
  return {
    id: `id${n}`, title: "Audit Intern", company: "Acme", ats: "workday",
    sources: [{ source_name: "workday", url: "https://acme.example/job" }],
    city: "Des Moines", state: "IA", lat: 41.57259, lng: -93.610243, location_label: "Des Moines, IA",
    is_remote: false, tags: [], status: "open", season: "Summer 2027", season_year: null,
    role_category: "accounting", eligibility: { status: "eligible", reason: "ok" },
    relevance_score: 60, first_seen: "2026-11-02", date_posted: null, deadline: null,
    ...over,
  };
}
const ids = (arr) => arr.map((l) => l.id);
const run = (listings, over = {}) => applyFilters(listings, { ...defaultFilters(CONFIG), ...over }, CONFIG);

test("escapeHtml escapes every markup character", () => {
  assert.equal(escapeHtml(`<img src=x onerror="alert(1)">&'\``), "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&#39;&#96;");
  assert.equal(escapeHtml(null), "");
  assert.equal(escapeHtml(42), "42");
});

test("safeUrl allows only http and https", () => {
  assert.equal(safeUrl("https://a.example/x?y=1"), "https://a.example/x?y=1");
  assert.equal(safeUrl("http://a.example/"), "http://a.example/");
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl(" JavaScript:alert(1)"), null);
  assert.equal(safeUrl("data:text/html,<script>alert(1)</script>"), null);
  assert.equal(safeUrl("/relative/path"), null);
  assert.equal(safeUrl(""), null);
  assert.equal(safeUrl(undefined), null);
  assert.equal(safeUrl({ href: "https://x" }), null);
});

test("haversine distance matches the pipeline's Ames to Des Moines figure", () => {
  const miles = haversineMiles(CONFIG.home, { lat: 41.57259, lng: -93.610243 });
  assert.ok(miles > 30 && miles < 33, String(miles));
});

test("status default is open only", () => {
  const open = listing();
  const filtered = listing({ status: "filtered" });
  const closed = listing({ status: "closed" });
  assert.deepEqual(defaultFilters(CONFIG).statuses, ["open"]);
  assert.deepEqual(ids(run([open, filtered, closed]).inPerson), [open.id]);
  assert.deepEqual(ids(run([open, filtered, closed], { statuses: ["open", "filtered"] }).inPerson), [open.id, filtered.id]);
});

test("search matches title and company words, case-insensitive", () => {
  const a = listing({ title: "Investment Banking Summer Analyst", company: "William Blair" });
  const b = listing({ title: "Tax Intern", company: "RSM" });
  assert.deepEqual(ids(run([a, b], { query: "banking" }).inPerson), [a.id]);
  assert.deepEqual(ids(run([a, b], { query: "blair summer" }).inPerson), [a.id]);
  assert.deepEqual(ids(run([a, b], { query: "rsm" }).inPerson), [b.id]);
  assert.deepEqual(ids(run([a, b], { query: "   " }).inPerson), [a.id, b.id]);
});

test("distance filter uses haversine and is off by default", () => {
  const near = listing(); // Des Moines, ~31 mi
  const far = listing({ city: "Chicago", state: "IL", lat: 41.837045, lng: -87.684939 }); // ~305 mi
  assert.equal(run([near, far]).inPerson.length, 2);
  assert.deepEqual(ids(run([near, far], { distanceOn: true, maxMiles: 150 }).inPerson), [near.id]);
  assert.deepEqual(ids(run([near, far], { distanceOn: true, maxMiles: 400 }).inPerson), [near.id, far.id]);
});

test("unknown coordinates never pass an active distance filter (D-022), but show when it's off", () => {
  const unknown = listing({ lat: null, lng: null, city: null, state: null, location_label: "Location unknown" });
  assert.equal(milesFromHome(unknown, CONFIG.home), null);
  assert.deepEqual(ids(run([unknown]).inPerson), [unknown.id]);
  assert.deepEqual(run([unknown], { distanceOn: true, maxMiles: 100000 }).inPerson, []);
});

test("city filter", () => {
  const a = listing();
  const b = listing({ city: "Chicago", state: "IL" });
  assert.deepEqual(ids(run([a, b], { city: "Chicago, IL" }).inPerson), [b.id]);
});

test("role filter includes None", () => {
  const ib = listing({ role_category: "investment_banking" });
  const none = listing({ role_category: null });
  assert.deepEqual(ids(run([ib, none], { roles: ["investment_banking"] }).inPerson), [ib.id]);
  assert.deepEqual(ids(run([ib, none], { roles: [NONE_ROLE] }).inPerson), [none.id]);
});

test("season filter: Not stated covers year-only and empty seasons", () => {
  const s = listing();
  const yearOnly = listing({ season: null, season_year: 2028 });
  const none = listing({ season: null });
  assert.deepEqual(ids(run([s, yearOnly, none], { seasons: ["Not stated"] }).inPerson), [yearOnly.id, none.id]);
  assert.deepEqual(ids(run([s, yearOnly, none], { seasons: ["Summer 2027"] }).inPerson), [s.id]);
});

test("season label shows a year-only listing without inventing a season", () => {
  assert.equal(seasonLabel(listing()), "Summer 2027");
  assert.equal(seasonLabel(listing({ season: null, season_year: 2028 })), "2028 · season not stated");
  assert.equal(seasonLabel(listing({ season: null })), "Season not stated");
});

test("date range on first_seen is inclusive", () => {
  const a = listing({ first_seen: "2026-11-01" });
  const b = listing({ first_seen: "2026-11-03" });
  const c = listing({ first_seen: null });
  assert.deepEqual(ids(run([a, b, c], { dateFrom: "2026-11-02" }).inPerson), [b.id]);
  assert.deepEqual(ids(run([a, b, c], { dateTo: "2026-11-01" }).inPerson), [a.id]);
  assert.deepEqual(ids(run([a, b, c], { dateFrom: "2026-11-01", dateTo: "2026-11-03" }).inPerson), [a.id, b.id]);
});

test("source filter reads ats and source names", () => {
  const w = listing();
  const g = listing({ ats: "greenhouse", sources: [{ source_name: "greenhouse", url: "https://x.example" }] });
  assert.deepEqual(ids(run([w, g], { sources: ["greenhouse"] }).inPerson), [g.id]);
});

test("eligibility filter", () => {
  const e = listing();
  const u = listing({ eligibility: { status: "unclear", reason: "" } });
  const i = listing({ eligibility: { status: "ineligible", reason: "2027 grads only" } });
  assert.deepEqual(ids(run([e, u, i], { eligibility: ["unclear", "ineligible"] }).inPerson), [u.id, i.id]);
});

test("minimum score filter", () => {
  const lo = listing({ relevance_score: 13 });
  const hi = listing({ relevance_score: 85 });
  const neg = listing({ relevance_score: -20 });
  assert.deepEqual(ids(run([lo, hi, neg], { minScore: 50 }).inPerson), [hi.id]);
  assert.equal(run([lo, hi, neg]).inPerson.length, 3);
});

test("remote_iowa listings stay in their own section and the toggle hides it", () => {
  const remote = listing({ is_remote: true, lat: null, lng: null, city: null, tags: ["remote_iowa"], location_label: "Remote" });
  const local = listing();
  const all = run([remote, local]);
  assert.deepEqual(ids(all.inPerson), [local.id]);
  assert.deepEqual(ids(all.remote), [remote.id]);
  assert.deepEqual(run([remote, local], { showRemote: false }).remote, []);
  // Place filters skip the remote section; other filters still apply.
  assert.deepEqual(ids(run([remote, local], { distanceOn: true, maxMiles: 10 }).remote), [remote.id]);
  assert.deepEqual(ids(run([remote, local], { city: "Des Moines, IA" }).remote), [remote.id]);
  assert.deepEqual(run([remote, local], { minScore: 99 }).remote, []);
  assert.equal(locationLabel(remote, CONFIG), "Remote — Iowa");
});

test("location_conflict listings show the title's place", () => {
  const l = listing({ title: "Intern, Tax- Cincinnati, OH", city: "Overland Park", state: "KS",
    location_label: "Overland Park, KS", tags: ["location_conflict"] });
  assert.equal(locationLabel(l, CONFIG), "Overland Park, KS (title says Cincinnati, OH)");
  assert.equal(locationLabel({ ...l, tags: [] }, CONFIG), "Overland Park, KS");
  assert.deepEqual(titlePlace("Remote (IL, CA, NY)", CONFIG.state_codes), null);
});

test("unknown location label", () => {
  assert.equal(locationLabel(listing({ location_label: "Location unknown", city: null, state: null }), CONFIG), "Location unknown");
});

test("sort orders, with missing values last", () => {
  const a = listing({ company: "Bravo", relevance_score: 50, first_seen: "2026-11-01", date_posted: null, deadline: "2026-12-01" });
  const b = listing({ company: "alpha", relevance_score: 90, first_seen: "2026-11-03", date_posted: "2026-10-01", deadline: null });
  const c = listing({ company: "Charlie", relevance_score: 70, first_seen: null, date_posted: "2026-10-20", deadline: "2026-11-15" });
  const d = listing({ company: "Delta", relevance_score: null, first_seen: "2026-11-02", date_posted: null, deadline: null });
  const all = [a, b, c, d];
  assert.deepEqual(ids(sortListings(all, "score")), [b.id, c.id, a.id, d.id]);
  assert.deepEqual(ids(sortListings(all, "first_seen")), [b.id, d.id, a.id, c.id]);
  assert.deepEqual(ids(sortListings(all, "date_posted")), [c.id, b.id, a.id, d.id]);
  assert.deepEqual(ids(sortListings(all, "deadline")), [c.id, a.id, b.id, d.id]);
  assert.deepEqual(ids(sortListings(all, "company")), [b.id, a.id, c.id, d.id]);
  assert.deepEqual(ids(sortListings(all, "nonsense")), ids(sortListings(all, "score")));
  assert.deepEqual(ids(all), [a.id, b.id, c.id, d.id], "sorting doesn't change the input");
});

test("new badge uses new_badge_days", () => {
  assert.equal(isNew(listing({ first_seen: "2026-11-02" }), CONFIG, "2026-11-04"), true);
  assert.equal(isNew(listing({ first_seen: "2026-11-01" }), CONFIG, "2026-11-04"), false);
  assert.equal(isNew(listing({ first_seen: null }), CONFIG, "2026-11-04"), false);
});

test("result count wording", () => {
  assert.equal(countLabel(42, 188, ["open"]), "42 of 188 open listings");
  assert.equal(countLabel(3, 204, ["open", "filtered"]), "3 of 204 listings (open, filtered)");
});

test("active filter count and defaults", () => {
  const f = defaultFilters(CONFIG);
  assert.equal(activeFilterCount(f, CONFIG), 0);
  assert.equal(activeFilterCount({ ...f, query: "x", minScore: 40, statuses: ["open", "closed"] }, CONFIG), 3);
});

test("health summary from meta.json", () => {
  const h = healthSummary({ run_finished: "2026-11-03T12:45:13+00:00", totals: { companies_fetched_ok: 58, companies_failed: 1 },
    errors: [{ company: "Acme" }], companies: [{ status: "manual" }, { status: "ok" }] });
  assert.deepEqual(h, { scanTime: "2026-11-03T12:45:13+00:00", ok: 58, failed: 1, failedNames: ["Acme"], manual: 1 });
  assert.equal(healthSummary(null), null);
});

test("filtering and sorting 2,000 synthetic listings stays fast", () => {
  const many = [];
  for (let i = 0; i < 2000; i++) {
    many.push(listing({ title: `Intern ${i}`, relevance_score: i % 100, lat: 41 + (i % 50) / 10, lng: -94 + (i % 30) / 10,
      status: i % 10 ? "open" : "filtered", season: i % 3 ? "Summer 2027" : null }));
  }
  const f = { query: "intern 1", distanceOn: true, maxMiles: 300, seasons: ["Summer 2027", "Not stated"], minScore: 20 };
  sortListings(run(many, f).inPerson, "score"); // warm-up pass
  const times = [];
  for (let k = 0; k < 10; k++) {
    const start = performance.now();
    sortListings(run(many, f).inPerson, "score");
    times.push(performance.now() - start);
  }
  times.sort((a, b) => a - b);
  const median = (times[4] + times[5]) / 2;
  console.log(`2,000-listing filter+sort median: ${median.toFixed(1)} ms`);
  // Generous limit: GitHub's shared runners are slower and noisier than a laptop.
  assert.ok(median < 100, `median filter+sort pass took ${median.toFixed(1)} ms`);
});
