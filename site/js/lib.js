// Pure functions for the listing view: no DOM, no storage, no network, so node --test can run them.
// Every listing field comes from third-party job boards and is treated as untrusted text.

export const STATUSES = ["open", "filtered", "possibly_closed", "closed"];
export const STATUS_LABELS = {
  open: "Open",
  filtered: "Filtered",
  possibly_closed: "Possibly closed",
  closed: "Closed",
};
export const ELIGIBILITY = ["eligible", "unclear", "ineligible"];
export const NONE_ROLE = "__none__";
export const NOT_STATED = "Not stated";

// The single escape helper. The app builds DOM with textContent, so this exists for any future
// place that must produce markup text; nothing from a listing may skip it.
export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"'`]/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;",
  })[c]);
}

// Only http(s) links are ever made clickable: a board could send javascript: or data: URLs.
export function safeUrl(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

export function haversineMiles(a, b) {
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 3958.8 * 2 * Math.asin(Math.sqrt(h)); // same Earth radius as scanner/location.py
}

const hasCoords = (l) => Number.isFinite(l.lat) && Number.isFinite(l.lng);

// D-022: a listing with unknown coordinates has an unknown distance, so it never passes an active
// distance filter. It still shows when the filter is off.
export function milesFromHome(listing, home) {
  return hasCoords(listing) && home && Number.isFinite(home.lat) ? haversineMiles(home, listing) : null;
}

export function isRemoteSection(listing, config) {
  const tags = listing.tags || [];
  return (config.remote_sections || []).some((s) => tags.includes(s.tag));
}

export function seasonLabel(listing) {
  if (listing.season) return listing.season;
  // P5.1: "2028 Audit or Tax Intern" states a year but no season, and none is guessed.
  if (listing.season_year) return `${listing.season_year} · season not stated`;
  return "Season not stated";
}

// Port of scanner/location.py title_place: one to three capitalized words, ", ", a state code.
const WORD = "[A-Z][A-Za-z.'’]*(?:-[A-Z][A-Za-z.'’]*)*";
const TITLE_PLACE = new RegExp(`(?<![\\w-])((?:${WORD} (?:(?:of|de|la|del|du) )?){0,2}${WORD}), ?([A-Z]{2})(?![\\w-])`, "g");

export function titlePlace(title, stateCodes) {
  const codes = new Set(stateCodes || []);
  for (const m of String(title || "").matchAll(TITLE_PLACE)) {
    if (codes.has(m[2]) && /[a-z]/.test(m[1])) return [m[1], m[2]];
  }
  return null;
}

export function locationLabel(listing, config) {
  const section = (config.remote_sections || []).find((s) => (listing.tags || []).includes(s.tag));
  if (section) return section.label;
  let label = listing.location_label;
  if (!label || label === "Location unknown") {
    label = listing.city && listing.state ? `${listing.city}, ${listing.state}` : "Location unknown";
  }
  if ((listing.tags || []).includes("location_conflict")) {
    const named = titlePlace(listing.title, config.state_codes);
    if (named) return `${label} (title says ${named[0]}, ${named[1]})`;
  }
  return label;
}

export function cityKey(listing) {
  return listing.city && listing.state ? `${listing.city}, ${listing.state}` : null;
}

export function sourceNames(listing) {
  const names = new Set();
  if (listing.ats) names.add(listing.ats);
  for (const s of listing.sources || []) if (s && s.source_name) names.add(s.source_name);
  return [...names];
}

export function humanize(key) {
  const text = String(key).replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function defaultFilters(config) {
  return {
    query: "",
    distanceOn: false,
    maxMiles: config.radius_miles,
    city: "",
    roles: [],        // empty = any
    seasons: [],
    dateFrom: "",
    dateTo: "",
    statuses: ["open"], // default view: open only
    sources: [],
    eligibility: [],
    minScore: null,   // null = no minimum
    showRemote: true,
  };
}

export function activeFilterCount(filters, config) {
  const d = defaultFilters(config);
  let n = 0;
  if (filters.query.trim()) n++;
  if (filters.distanceOn) n++;
  if (filters.city) n++;
  for (const k of ["roles", "seasons", "sources", "eligibility"]) if (filters[k].length) n++;
  if (filters.dateFrom || filters.dateTo) n++;
  if ([...filters.statuses].sort().join() !== d.statuses.join()) n++;
  if (filters.minScore !== null) n++;
  if (!filters.showRemote) n++;
  return n;
}

// Builds one predicate per active filter, so a list of 2,000 is checked without per-item setup.
export function makePredicate(filters, config) {
  const checks = [];
  const statuses = new Set(filters.statuses);
  checks.push((l) => statuses.has(l.status));

  const q = filters.query.trim().toLowerCase();
  if (q) {
    const words = q.split(/\s+/);
    checks.push((l) => {
      const text = `${l.title || ""} ${l.company || ""}`.toLowerCase();
      return words.every((w) => text.includes(w));
    });
  }
  if (filters.city) checks.push((l) => cityKey(l) === filters.city);
  if (filters.roles.length) {
    const roles = new Set(filters.roles);
    checks.push((l) => roles.has(l.role_category || NONE_ROLE));
  }
  if (filters.seasons.length) {
    const seasons = new Set(filters.seasons);
    checks.push((l) => seasons.has(l.season || NOT_STATED));
  }
  if (filters.dateFrom) checks.push((l) => (l.first_seen || "") >= filters.dateFrom);
  if (filters.dateTo) checks.push((l) => !!l.first_seen && l.first_seen <= filters.dateTo);
  if (filters.sources.length) {
    const sources = new Set(filters.sources);
    checks.push((l) => sourceNames(l).some((s) => sources.has(s)));
  }
  if (filters.eligibility.length) {
    const el = new Set(filters.eligibility);
    checks.push((l) => el.has(l.eligibility && l.eligibility.status));
  }
  if (filters.minScore !== null) {
    checks.push((l) => Number.isFinite(l.relevance_score) && l.relevance_score >= filters.minScore);
  }
  return (l) => checks.every((c) => c(l));
}

// Place filters (city, distance) describe where you'd work in person, so they skip the remote
// section, as the email's areas filter does (D-033). Every other filter applies to both.
export function applyFilters(listings, filters, config) {
  const base = makePredicate({ ...filters, city: "" }, config);
  const home = config.home;
  const inPerson = [];
  const remote = [];
  for (const l of listings) {
    if (!base(l)) continue;
    if (isRemoteSection(l, config)) {
      if (filters.showRemote) remote.push(l);
      continue;
    }
    if (filters.city && cityKey(l) !== filters.city) continue;
    if (filters.distanceOn) {
      const miles = milesFromHome(l, home);
      if (miles === null || miles > filters.maxMiles) continue;
    }
    inPerson.push(l);
  }
  return { inPerson, remote };
}

const byText = (a, b) => (a || "").localeCompare(b || "", "en", { sensitivity: "base" });
const tie = (a, b) => byText(a.company, b.company) || byText(a.title, b.title) || byText(a.id, b.id);
// Missing values always sort last, whichever direction the sort runs.
const missingLast = (va, vb, cmp) => (va == null ? (vb == null ? 0 : 1) : vb == null ? -1 : cmp(va, vb));
const desc = (x, y) => (x < y ? 1 : x > y ? -1 : 0);
const asc = (x, y) => (x < y ? -1 : x > y ? 1 : 0);

export const SORTS = {
  score: { label: "Score (high first)", cmp: (a, b) => missingLast(a.relevance_score, b.relevance_score, desc) || tie(a, b) },
  first_seen: { label: "First seen (newest)", cmp: (a, b) => missingLast(a.first_seen, b.first_seen, desc) || tie(a, b) },
  date_posted: { label: "Date posted (newest)", cmp: (a, b) => missingLast(a.date_posted, b.date_posted, desc) || tie(a, b) },
  deadline: { label: "Deadline (soonest)", cmp: (a, b) => missingLast(a.deadline, b.deadline, asc) || tie(a, b) },
  company: { label: "Company A–Z", cmp: (a, b) => tie(a, b) },
};

export function sortListings(listings, key) {
  const sort = SORTS[key] || SORTS.score;
  return [...listings].sort(sort.cmp);
}

// "New" is first_seen within new_badge_days of today (SPEC). today is "YYYY-MM-DD".
export function isNew(listing, config, today) {
  if (!listing.first_seen || !today) return false;
  const days = (Date.parse(today) - Date.parse(listing.first_seen)) / 86400000;
  return days >= 0 && days < config.new_badge_days;
}

export function localDate(d = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function countLabel(shown, total, statuses) {
  const words = statuses.length === 1 ? `${STATUS_LABELS[statuses[0]].toLowerCase()} listings`
    : `listings (${statuses.map((s) => STATUS_LABELS[s].toLowerCase()).join(", ")})`;
  return `${shown} of ${total} ${words}`;
}

// The compact health line under the header, from meta.json's totals and source_health.
export function healthSummary(meta) {
  if (!meta || typeof meta !== "object") return null;
  const t = meta.totals || {};
  // meta.errors holds the companies whose fetch failed this run ("error" or "manual_fallback").
  const failed = (Array.isArray(meta.errors) ? meta.errors : []).map((e) => String((e && e.company) || "?"));
  const companies = Array.isArray(meta.companies) ? meta.companies : [];
  return {
    scanTime: typeof meta.run_finished === "string" ? meta.run_finished : null,
    ok: Number.isFinite(t.companies_fetched_ok) ? t.companies_fetched_ok : null,
    failed: Number.isFinite(t.companies_failed) ? t.companies_failed : failed.length,
    failedNames: failed,
    manual: companies.filter((c) => c && c.status === "manual").length,
  };
}
