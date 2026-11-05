// P8 (D-045): Posted filter, Newest posted sort, Today dashboard, companies, LinkedIn links, routes.
// Every date test uses a fixed clock, never the real one.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  parseYmd, daysBetween, addDays, effectiveDate, postedAgeDays, postedWithin, deadlineWithin, postedLabel,
  postedButtonLabel, defaultFilters, applyFilters, sortListings, activeFilterCount, localDate, SORTS,
} from "../../site/js/lib.js";
import {
  parseRoute, routeHash, navFor, todaySummary, buildCompanies, searchCompanies, atsLabel, companyListingGroups,
  linkedinShortName, linkedinLinks, LINKEDIN_TRAILING_CORPORATE_WORDS,
} from "../../site/js/hub.js";
import { readStoredTheme, storeTheme, pickTheme, THEME_KEY } from "../../site/js/theme.js";

const SITE = {
  posted_within_days: [1, 3, 7, 30], default_sort: "score", default_theme: "dark", linkedin_school_id: "164452",
  linkedin_school_name: "Iowa State University", manual_first_tags: ["ib"], deadline_window_days: 14,
};
const CONFIG = {
  home: { name: "Ames, IA", lat: 42.025725, lng: -93.622491 }, radius_miles: 150,
  seasons: ["Summer 2027", "Not stated"], role_categories: ["accounting"], new_badge_days: 3,
  remote_sections: [{ tag: "remote_iowa", label: "Remote — Iowa" }], state_codes: ["IA"], site: SITE,
};
// 10:30 local time on Thursday 5 November 2026: the fixed "now" for every test here.
const NOW = new Date(2026, 10, 5, 10, 30);
const TODAY = "2026-11-05";

let n = 0;
function listing(over = {}) {
  n += 1;
  return {
    id: `p${n}`, title: "Audit Intern", company: "Acme", company_id: "acme", ats: "workday", sources: [],
    city: "Des Moines", state: "IA", lat: 41.57, lng: -93.61, location_label: "Des Moines, IA", tags: [],
    status: "open", season: "Summer 2027", role_category: "accounting", eligibility: { status: "eligible" },
    relevance_score: 60, first_seen: "2026-11-02", date_posted: null, deadline: null, ...over,
  };
}
const ids = (arr) => arr.map((l) => l.id);
const run = (ls, over = {}) => applyFilters(ls, { ...defaultFilters(CONFIG), ...over }, CONFIG, NOW).inPerson;

// ---------- dates ----------

test("parseYmd accepts real calendar dates only", () => {
  assert.equal(parseYmd("2026-11-03"), "2026-11-03");
  assert.equal(parseYmd("2026-11-03T08:00:00Z"), "2026-11-03");
  for (const bad of [null, undefined, "", "Posted 3 days ago", "11/03/2026", "2026-02-30", "2026-13-01", 20261103, "2026-1-3"]) {
    assert.equal(parseYmd(bad), null, String(bad));
  }
});

test("day arithmetic ignores daylight-saving changes", () => {
  assert.equal(daysBetween("2026-10-31", "2026-11-02"), 2); // US clocks change on 1 Nov 2026
  assert.equal(addDays("2026-11-05", 14), "2026-11-19");
  assert.equal(addDays("2026-03-07", 1), "2026-03-08");
  assert.equal(localDate(NOW), TODAY);
});

test("effective date: date_posted when readable, else first_seen, and it says which", () => {
  assert.deepEqual(effectiveDate(listing({ date_posted: "2026-10-30" })), { ymd: "2026-10-30", kind: "posted" });
  assert.deepEqual(effectiveDate(listing({ date_posted: null })), { ymd: "2026-11-02", kind: "first_seen" });
  assert.deepEqual(effectiveDate(listing({ date_posted: "last Tuesday" })), { ymd: "2026-11-02", kind: "first_seen" });
  assert.deepEqual(effectiveDate(listing({ date_posted: "2026-02-30" })), { ymd: "2026-11-02", kind: "first_seen" });
  assert.equal(effectiveDate(listing({ date_posted: null, first_seen: null })), null);
  // A first_seen date is never called a posting date.
  assert.equal(postedLabel(listing({ date_posted: "2026-10-30" })), "Posted 2026-10-30");
  assert.equal(postedLabel(listing({ date_posted: null })), "First seen 2026-11-02");
  assert.equal(postedLabel(listing({ date_posted: "garbage" })), "First seen 2026-11-02");
  assert.equal(postedLabel(listing({ date_posted: null, first_seen: null })), null);
});

test("a future date counts as today", () => {
  const future = listing({ date_posted: "2026-11-20" });
  assert.equal(postedAgeDays(future, TODAY), 0);
  assert.equal(postedWithin(future, 1, TODAY), true);
  assert.deepEqual(ids(run([future], { postedDays: 1 })), [future.id]);
});

test("Posted buckets with a fixed now: 24 h, 3, 7 and 30 days", () => {
  const today = listing({ date_posted: "2026-11-05" });
  const yesterday = listing({ date_posted: "2026-11-04" });
  const twoAgo = listing({ date_posted: "2026-11-03" });
  const threeAgo = listing({ date_posted: "2026-11-02" });
  const fourAgo = listing({ date_posted: "2026-11-01" });
  const weekAgo = listing({ date_posted: "2026-10-29" });
  const eightAgo = listing({ date_posted: "2026-10-28" });
  const monthAgo = listing({ date_posted: "2026-10-06" });
  const older = listing({ date_posted: "2026-10-05" });
  const seenToday = listing({ date_posted: null, first_seen: "2026-11-05" });
  const unreadable = listing({ date_posted: "n/a", first_seen: "2026-11-04" });
  const noDates = listing({ date_posted: null, first_seen: null });
  const all = [today, yesterday, twoAgo, threeAgo, fourAgo, weekAgo, eightAgo, monthAgo, older, seenToday, unreadable, noDates];
  assert.deepEqual(ids(run(all, { postedDays: 1 })), ids([today, yesterday, seenToday, unreadable]));
  assert.deepEqual(ids(run(all, { postedDays: 3 })), ids([today, yesterday, twoAgo, threeAgo, seenToday, unreadable]));
  assert.deepEqual(ids(run(all, { postedDays: 7 })), ids([today, yesterday, twoAgo, threeAgo, fourAgo, weekAgo, seenToday, unreadable]));
  assert.deepEqual(ids(run(all, { postedDays: 30 })), ids(all.filter((l) => l !== older && l !== noDates)));
  assert.equal(run(all).length, all.length, "Any = no date filter, so undated listings still show");
  assert.equal(postedButtonLabel(1), "24 h");
  assert.equal(postedButtonLabel(7), "7 days");
});

test("the Posted filter measures from the clock it is given", () => {
  const l = listing({ date_posted: "2026-11-04" });
  const later = new Date(2026, 10, 9, 9, 0);
  assert.equal(applyFilters([l], { ...defaultFilters(CONFIG), postedDays: 1 }, CONFIG, NOW).inPerson.length, 1);
  assert.equal(applyFilters([l], { ...defaultFilters(CONFIG), postedDays: 1 }, CONFIG, later).inPerson.length, 0);
});

test("Newest posted: effective date newest first, ties by score, missing last", () => {
  const a = listing({ date_posted: "2026-11-01", relevance_score: 50 });
  const b = listing({ date_posted: null, first_seen: "2026-11-04", relevance_score: 40 }); // first seen counts
  const c = listing({ date_posted: "2026-11-04", relevance_score: 90 });                  // same day as b, higher score
  const d = listing({ date_posted: "bad", first_seen: null, relevance_score: 99 });       // no date at all
  const e = listing({ date_posted: "2026-11-30", relevance_score: 10 });                  // future: newest
  assert.deepEqual(ids(sortListings([a, b, c, d, e], "newest_posted")), ids([e, c, b, a, d]));
  assert.equal(SORTS.newest_posted.label, "Newest posted");
  assert.equal(SORTS.date_posted.hidden, true, "the old stated-date-only sort stays out of the menu");
});

test("new-only and deadline filters, and they count as active", () => {
  const fresh = listing({ first_seen: "2026-11-04" });
  const old = listing({ first_seen: "2026-10-01" });
  const due = listing({ deadline: "2026-11-19" });
  const late = listing({ deadline: "2026-11-20" });
  const past = listing({ deadline: "2026-11-04" });
  assert.deepEqual(ids(run([fresh, old], { newOnly: true })), [fresh.id]);
  assert.deepEqual(ids(run([due, late, past, fresh], { deadlineDays: 14 })), [due.id]);
  const f = defaultFilters(CONFIG);
  assert.equal(activeFilterCount({ ...f, postedDays: 7, newOnly: true, deadlineDays: 14 }, CONFIG), 3);
  assert.equal(deadlineWithin(listing({ deadline: TODAY }), 0, TODAY), true);
});

// ---------- Today ----------

test("Today counts match fixtures and use open listings only", () => {
  const ls = [
    listing({ first_seen: "2026-11-05", date_posted: "2026-11-05" }),                  // new, posted 24 h
    listing({ first_seen: "2026-11-04", date_posted: null }),                          // new, first seen 24 h
    listing({ first_seen: "2026-11-03", date_posted: "2026-10-01" }),                  // new only
    listing({ first_seen: "2026-11-01", date_posted: "2026-11-04", deadline: "2026-11-10" }), // posted 24 h, due
    listing({ first_seen: "2026-11-05", date_posted: "2026-11-05", status: "closed" }),     // ignored
    listing({ first_seen: "2026-11-05", date_posted: null, status: "filtered", deadline: "2026-11-06" }), // ignored
    listing({ first_seen: "2026-11-05", date_posted: null, status: "possibly_closed" }),  // ignored
    listing({ first_seen: "2026-10-01", deadline: "2026-11-19", relevance_score: 10 }),   // due, last day
    listing({ first_seen: "2026-10-01", deadline: "2026-11-19", relevance_score: 80 }),   // due, same day, higher score
    listing({ first_seen: "2026-10-01", deadline: "2026-11-20" }),                        // outside 14 days
    listing({ first_seen: "2026-10-01", deadline: "2026-11-04" }),                        // already past
    listing({ first_seen: "2026-10-01", deadline: "not a date" }),
    listing({ first_seen: "2026-11-05", tags: ["remote_iowa"], lat: null, lng: null }),    // remote, new, first seen
  ];
  const meta = { run_finished: "2026-11-05T12:52:21+00:00", totals: { companies_fetched_ok: 60, companies_failed: 1 },
    errors: [{ company: "Acme" }], companies: [] };
  const s = todaySummary(ls, { ...CONFIG, last_scan_ran: "2026-11-05T12:53:40+00:00" }, meta, TODAY);
  assert.equal(s.open, 10);
  assert.equal(s.newCount, 4);
  assert.equal(s.postedPosted, 2);
  assert.equal(s.postedFirstSeen, 2);
  assert.deepEqual(s.deadlines.map((l) => l.deadline), ["2026-11-10", "2026-11-19", "2026-11-19"]);
  assert.equal(s.deadlines[1].relevance_score, 80, "same day: higher score first");
  assert.equal(s.deadlineWindow, 14);
  assert.equal(s.remote, 1);
  assert.equal(s.dataUpdated, "2026-11-05T12:52:21+00:00");
  assert.equal(s.lastScanRan, "2026-11-05T12:53:40+00:00");
  assert.deepEqual(s.failedNames, ["Acme"]);
});

test("Today deadlines follow site.deadline_window_days", () => {
  const ls = [listing({ deadline: "2026-11-08" }), listing({ deadline: "2026-11-12" })];
  const short = todaySummary(ls, { ...CONFIG, site: { ...SITE, deadline_window_days: 3 } }, null, TODAY);
  assert.equal(short.deadlines.length, 1);
  assert.equal(short.deadlineWindow, 3);
  assert.equal(todaySummary(ls, CONFIG, null, TODAY).deadlines.length, 2);
  const none = todaySummary(ls, CONFIG, null, TODAY);
  assert.equal(none.lastScanRan, null, "no last_scan_ran in site_config → none shown, never invented");
  assert.equal(none.dataUpdated, null);
});

// ---------- companies ----------

const REGISTRY = { schema_version: 1, companies: [
  { id: "wintrust-financial", name: "Wintrust Financial", ats: "workday", careers_url: "https://wintrust.wd1.myworkdayjobs.com/Search", cities: ["Chicago"], priority: 1, tags: [], linkedin_name: null },
  { id: "lazard", name: "Lazard", ats: "manual", careers_url: "https://www.lazard.com/careers/", cities: ["Chicago"], priority: 1, tags: ["ib"], linkedin_name: null },
  { id: "baird", name: "Baird", ats: "manual", careers_url: null, cities: [], priority: 1, tags: ["ib"], linkedin_name: null },
  { id: "aon", name: "Aon", ats: "workday", careers_url: null, cities: [], priority: 2, tags: [], linkedin_name: null },
] };
const STATUS = {
  "wintrust-financial": { company_id: "wintrust-financial", company: "Wintrust Financial", ats: "workday", last_checked: "2026-11-05T12:24:43+00:00", fetch_health: { status: "ok", last_error: null } },
  aon: { company_id: "aon", company: "Aon", ats: "workday", last_checked: "2026-11-05T12:24:43+00:00", fetch_health: { status: "error", last_error: "HTTP 500", consecutive_failures: 2 } },
  "gone-co": { company_id: "gone-co", company: "Gone Co", ats: "greenhouse", careers_url: "https://boards.greenhouse.io/gone", last_checked: "2026-10-01T00:00:00+00:00", fetch_health: { status: "ok" } },
};

test("companies: registry + status history + listings, IB first, then open count, then name", () => {
  const ls = [
    listing({ company_id: "wintrust-financial", company: "Wintrust Financial" }),
    listing({ company_id: "wintrust-financial", company: "Wintrust Financial" }),
    listing({ company_id: "wintrust-financial", company: "Wintrust Financial", status: "closed" }),
    listing({ company_id: "aon", company: "Aon" }),
    listing({ company_id: "lazard", company: "Lazard", status: "closed" }),
    listing({ company_id: "orphan-co", company: "Orphan Co" }),
  ];
  const cs = buildCompanies(REGISTRY, STATUS, ls, CONFIG);
  assert.deepEqual(cs.map((c) => c.id), ["baird", "lazard", "wintrust-financial", "aon", "orphan-co", "gone-co"]);
  const by = Object.fromEntries(cs.map((c) => [c.id, c]));
  assert.equal(by["wintrust-financial"].openCount, 2);
  assert.equal(by["wintrust-financial"].listingCount, 3);
  assert.equal(by.lazard.openCount, 0);
  assert.equal(by["gone-co"].inRegistry, false, "a company only in companies_status.json is kept (history is never deleted)");
  assert.equal(by["gone-co"].careersUrl, "https://boards.greenhouse.io/gone");
  assert.equal(by.aon.health.status, "error");
  assert.equal(atsLabel(by.lazard), "Manual");
  assert.equal(atsLabel(by.aon), "Workday");
  assert.deepEqual(searchCompanies(cs, "laz").map((c) => c.id), ["lazard"]);
  assert.deepEqual(searchCompanies(cs, "IB").map((c) => c.id), ["baird", "lazard"]);
  assert.equal(searchCompanies(cs, "  ").length, cs.length);
  // With no registry file at all, the page still works from companies_status.json and the listings.
  assert.deepEqual(buildCompanies(null, STATUS, [], CONFIG).map((c) => c.id), ["aon", "gone-co", "wintrust-financial"]);
});

test("company page groups: open → possibly_closed → filtered → closed", () => {
  const ls = [
    listing({ company_id: "x", status: "closed", relevance_score: 99 }),
    listing({ company_id: "x", status: "filtered" }),
    listing({ company_id: "x", status: "open", relevance_score: 20 }),
    listing({ company_id: "x", status: "open", relevance_score: 70 }),
    listing({ company_id: "x", status: "possibly_closed" }),
    listing({ company_id: "y", status: "open" }),
  ];
  const groups = companyListingGroups(ls, "x");
  assert.deepEqual(groups.map((g) => g.status), ["open", "possibly_closed", "filtered", "closed"]);
  assert.deepEqual(groups[0].listings.map((l) => l.relevance_score), [70, 20]);
  assert.deepEqual(companyListingGroups(ls, "none"), []);
});

test("Companies page from 2,000 listings stays fast", () => {
  const many = [];
  for (let i = 0; i < 2000; i++) many.push(listing({ company_id: `co-${i % 150}`, company: `Company ${i % 150}`, status: i % 7 ? "open" : "closed" }));
  const registry = { companies: Array.from({ length: 150 }, (_, i) => ({ id: `co-${i}`, name: `Company ${i}`, ats: "workday", cities: [], priority: 2, tags: i % 10 ? [] : ["ib"] })) };
  buildCompanies(registry, {}, many, CONFIG);
  const times = [];
  for (let k = 0; k < 10; k++) {
    const t = performance.now();
    searchCompanies(buildCompanies(registry, {}, many, CONFIG), "company 1");
    times.push(performance.now() - t);
  }
  times.sort((a, b) => a - b);
  const median = (times[4] + times[5]) / 2;
  console.log(`Companies model from 2,000 listings, median: ${median.toFixed(2)} ms`);
  assert.ok(median < 100, `median ${median.toFixed(1)} ms`);
});

// ---------- LinkedIn ----------

const SCHOOL = "164452";
const alumni = (k) => `https://www.linkedin.com/search/results/people/?keywords=${k}&origin=COMPANY_PAGE_CANNED_SEARCH&schoolFilter=%5B%22${SCHOOL}%22%5D`;
const broad = (k) => `https://www.linkedin.com/search/results/people/?keywords=Iowa%20State%20University%20${k}`;
const links = (name, linkedinName = null) => linkedinLinks({ name, linkedinName }, SITE);

test("LinkedIn links match Engine B's formats exactly", () => {
  assert.deepEqual(links("Wintrust Financial"), { alumni: alumni("Wintrust"), broad: broad("Wintrust") });
  assert.deepEqual(links("Federal Reserve System"), { alumni: alumni("Federal%20Reserve"), broad: broad("Federal%20Reserve") });
  assert.deepEqual(links("CME Group", "CME Group"), { alumni: alumni("CME%20Group"), broad: broad("CME%20Group") });
  assert.deepEqual(links("Nuveen / TIAA", "Nuveen"), { alumni: alumni("Nuveen"), broad: broad("Nuveen") });
  // "&" must be encoded, or LinkedIn would read it as a new query parameter.
  assert.deepEqual(links("Cottingham & Butler"), { alumni: alumni("Cottingham%20%26%20Butler"), broad: broad("Cottingham%20%26%20Butler") });
  assert.deepEqual(links("H&R Block"), { alumni: alumni("H%26R%20Block"), broad: broad("H%26R%20Block") });
  // A name that would strip to nothing keeps its full name.
  assert.deepEqual(links("Financial Group"), { alumni: alumni("Financial%20Group"), broad: broad("Financial%20Group") });
});

test("short names: trailing corporate words go, the rest stays", () => {
  assert.equal(linkedinShortName("Wintrust Financial"), "Wintrust");
  assert.equal(linkedinShortName("Federal Reserve System"), "Federal Reserve");
  assert.equal(linkedinShortName("Principal Financial Group"), "Principal");
  assert.equal(linkedinShortName("Moelis & Company"), "Moelis");
  assert.equal(linkedinShortName("Goldman Sachs & Co."), "Goldman Sachs");
  assert.equal(linkedinShortName("Acme, Inc."), "Acme");
  assert.equal(linkedinShortName("Acme Holdings LLC"), "Acme");
  assert.equal(linkedinShortName("Ames National Corporation"), "Ames National");
  assert.equal(linkedinShortName("Group Financial"), "Group Financial", "never empty");
  assert.equal(linkedinShortName("Inc."), "Inc.");
  assert.equal(linkedinShortName("Financial Planning Partners"), "Financial Planning Partners", "only trailing words");
  assert.equal(linkedinShortName("Anything", "  Override  "), "Override");
  assert.equal(linkedinShortName("Wintrust Financial", ""), "Wintrust", "an empty override is ignored");
  for (const w of ["Financial", "System", "Group", "Inc", "Inc.", "LLC", "Corp", "Corporation", "Co", "Company", "Holdings"]) {
    assert.ok(LINKEDIN_TRAILING_CORPORATE_WORDS.includes(w), w);
  }
});

test("LinkedIn values come from site_config, not from code", () => {
  const other = linkedinLinks({ name: "Acme" }, { ...SITE, linkedin_school_id: "999", linkedin_school_name: "Drake University" });
  assert.equal(other.alumni, "https://www.linkedin.com/search/results/people/?keywords=Acme&origin=COMPANY_PAGE_CANNED_SEARCH&schoolFilter=%5B%22999%22%5D");
  assert.equal(other.broad, "https://www.linkedin.com/search/results/people/?keywords=Drake%20University%20Acme");
});

// ---------- routes ----------

test("routes parse, with Today as the default", () => {
  assert.deepEqual(parseRoute(""), { name: "today" });
  assert.deepEqual(parseRoute("#"), { name: "today" });
  assert.deepEqual(parseRoute("#/"), { name: "today" });
  for (const r of ["today", "listings", "companies", "my-list", "contacts"]) assert.deepEqual(parseRoute(`#/${r}`), { name: r });
  assert.deepEqual(parseRoute("#/company/wintrust-financial"), { name: "company", id: "wintrust-financial" });
  assert.deepEqual(parseRoute("#/listings?posted=7"), { name: "listings" }, "room for P10's URL filters");
  for (const bad of ["#/nope", "#/company", "#/company/", "#/company/Bad_ID", "#/company/a/b", "#/company/%E0%A4%A",
    "#/company/<script>", "#/listings/extra", "#/Today", "#/company/javascript:alert(1)"]) {
    assert.deepEqual(parseRoute(bad), { name: "not-found" }, bad);
  }
  assert.equal(routeHash("company", "moelis-company"), "#/company/moelis-company");
  assert.equal(routeHash("my-list"), "#/my-list");
  assert.equal(navFor({ name: "company", id: "x" }), "companies");
});

// ---------- theme ----------

test("theme: stored choice wins, else site.default_theme, and blocked storage is harmless", () => {
  const mem = new Map();
  const storage = { getItem: (k) => mem.get(k) ?? null, setItem: (k, v) => mem.set(k, v) };
  assert.equal(readStoredTheme(storage), null);
  assert.equal(pickTheme(null, "light"), "light");
  assert.equal(pickTheme(null, "neon"), "dark");
  assert.equal(storeTheme(storage, "light"), true);
  assert.equal(mem.get(THEME_KEY), "light");
  assert.ok(THEME_KEY.startsWith("internship-scanner:"));
  assert.equal(pickTheme(readStoredTheme(storage), "dark"), "light");
  mem.set(THEME_KEY, "<script>");
  assert.equal(readStoredTheme(storage), null);
  const blocked = { getItem() { throw new Error("SecurityError"); }, setItem() { throw new Error("QuotaExceeded"); } };
  assert.equal(readStoredTheme(blocked), null);
  assert.equal(storeTheme(blocked, "light"), false);
  assert.equal(readStoredTheme(null), null);
});
