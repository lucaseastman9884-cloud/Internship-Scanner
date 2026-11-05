// P8 (D-045): routes, the Today dashboard's numbers, the company registry and LinkedIn links.
// Pure functions only (no DOM, storage or network), so node --test covers them.
import { isNew, effectiveDate, postedAgeDays, deadlineWithin, parseYmd, isRemoteSection, healthSummary } from "./lib.js";

// ---------- routes ----------
// Hash routes work on GitHub Pages with no 404 fallback. Kept to "#/name" and "#/company/<id>", so
// P10 can add URL-encoded filters after a "?" without breaking these.
export const ROUTES = ["today", "listings", "companies", "company", "my-list", "contacts"];
export const DEFAULT_ROUTE = "today";
const COMPANY_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/; // scanner/config.py company_id()

export function parseRoute(hash) {
  const raw = String(hash || "").replace(/^#/, "");
  const path = raw.split("?")[0];
  if (path === "" || path === "/") return { name: DEFAULT_ROUTE };
  const parts = path.replace(/^\//, "").split("/");
  if (parts.length === 1 && ROUTES.includes(parts[0]) && parts[0] !== "company") return { name: parts[0] };
  if (parts.length === 2 && parts[0] === "company") {
    let id = parts[1];
    try { id = decodeURIComponent(id); } catch { return { name: "not-found" }; }
    if (COMPANY_ID.test(id)) return { name: "company", id };
  }
  return { name: "not-found" };
}

export function routeHash(name, id) {
  return name === "company" ? `#/company/${encodeURIComponent(id)}` : `#/${name}`;
}

// Which view to show: a company id that isn't known shows "Not found", like an unknown route.
export function resolveRoute(route, companyById) {
  if (route.name === "company") {
    const company = companyById.get(route.id);
    return company ? { name: "company", company } : { name: "not-found", what: "company" };
  }
  return route.name === "not-found" ? { name: "not-found", what: "page" } : { name: route.name };
}

// The nav item a route belongs to (a company page sits under Companies).
export function navFor(route) {
  return route.name === "company" ? "companies" : route.name;
}

// ---------- Today ----------
// Every number counts open listings only (P8 spec).
export function todaySummary(listings, config, meta, today) {
  const open = listings.filter((l) => l && l.status === "open");
  const site = config.site || {};
  const window = Number.isInteger(site.deadline_window_days) ? site.deadline_window_days : 14;
  const posted = { posted: 0, first_seen: 0 };
  for (const l of open) {
    if (postedAgeDays(l, today) === null || postedAgeDays(l, today) > 1) continue;
    posted[effectiveDate(l).kind]++;
  }
  const deadlines = open.filter((l) => deadlineWithin(l, window, today))
    .sort((a, b) => (parseYmd(a.deadline) < parseYmd(b.deadline) ? -1 : parseYmd(a.deadline) > parseYmd(b.deadline) ? 1
      : (b.relevance_score ?? -Infinity) - (a.relevance_score ?? -Infinity)));
  const health = healthSummary(meta);
  return {
    open: open.length,
    newCount: open.filter((l) => isNew(l, config, today)).length,
    postedPosted: posted.posted,
    postedFirstSeen: posted.first_seen,
    deadlines,
    deadlineWindow: window,
    remote: open.filter((l) => isRemoteSection(l, config)).length,
    dataUpdated: health ? health.scanTime : null,
    lastScanRan: typeof config.last_scan_ran === "string" ? config.last_scan_ran : null,
    failedNames: health ? health.failedNames : [],
    failedCount: health ? health.failed : 0,
  };
}

// ---------- companies ----------
// One entry per company: the registry (companies.json, made at deploy) joined with
// companies_status.json (never deleted, so removed companies still appear) and the listings.
export function buildCompanies(registry, status, listings, config) {
  const byId = new Map();
  const ensure = (id, name) => {
    if (!byId.has(id)) {
      byId.set(id, { id, name: name || id, ats: null, careersUrl: null, cities: [], priority: null, tags: [],
        linkedinName: null, inRegistry: false, health: null, lastChecked: null, openCount: 0, listingCount: 0 });
    }
    return byId.get(id);
  };
  for (const c of (registry && Array.isArray(registry.companies) ? registry.companies : [])) {
    if (!c || typeof c.id !== "string") continue;
    const e = ensure(c.id, c.name);
    Object.assign(e, {
      name: typeof c.name === "string" ? c.name : e.name,
      ats: typeof c.ats === "string" ? c.ats : null,
      careersUrl: typeof c.careers_url === "string" ? c.careers_url : null,
      cities: Array.isArray(c.cities) ? c.cities.filter((x) => typeof x === "string") : [],
      priority: Number.isInteger(c.priority) ? c.priority : null,
      tags: Array.isArray(c.tags) ? c.tags.filter((x) => typeof x === "string") : [],
      linkedinName: typeof c.linkedin_name === "string" ? c.linkedin_name : null,
      inRegistry: true,
    });
  }
  const statusEntries = status && typeof status === "object" && !Array.isArray(status) ? Object.values(status) : [];
  for (const s of statusEntries) {
    if (!s || typeof s.company_id !== "string") continue;
    const e = ensure(s.company_id, typeof s.company === "string" ? s.company : null);
    if (!e.ats && typeof s.ats === "string") e.ats = s.ats;
    if (!e.careersUrl && typeof s.careers_url === "string") e.careersUrl = s.careers_url;
    e.health = s.fetch_health && typeof s.fetch_health === "object" ? s.fetch_health : null;
    e.lastChecked = typeof s.last_checked === "string" ? s.last_checked : null;
  }
  for (const l of listings) {
    if (!l || typeof l.company_id !== "string") continue;
    const e = ensure(l.company_id, l.company);
    e.listingCount++;
    if (l.status === "open") e.openCount++;
  }
  const firstTags = new Set((config.site && config.site.manual_first_tags) || []);
  const out = [...byId.values()];
  for (const e of out) e.featured = e.tags.some((t) => firstTags.has(t));
  return out.sort((a, b) => (b.featured - a.featured) || (b.openCount - a.openCount)
    || a.name.localeCompare(b.name, "en", { sensitivity: "base" }) || (a.id < b.id ? -1 : 1));
}

export function searchCompanies(companies, query) {
  const words = String(query || "").trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return companies;
  return companies.filter((c) => {
    const text = `${c.name} ${c.tags.join(" ")} ${c.ats || ""} ${c.cities.join(" ")}`.toLowerCase();
    return words.every((w) => text.includes(w));
  });
}

export function atsLabel(company) {
  if (!company.ats) return "Unknown source";
  return company.ats === "manual" ? "Manual" : company.ats.charAt(0).toUpperCase() + company.ats.slice(1);
}

// A company page lists every listing it ever had, in this order (P8 spec).
export const COMPANY_STATUS_ORDER = ["open", "possibly_closed", "filtered", "closed"];

export function companyListingGroups(listings, companyId) {
  const groups = new Map(COMPANY_STATUS_ORDER.map((s) => [s, []]));
  const other = [];
  for (const l of listings) {
    if (!l || l.company_id !== companyId) continue;
    (groups.get(l.status) || other).push(l);
  }
  const byScore = (a, b) => (b.relevance_score ?? -Infinity) - (a.relevance_score ?? -Infinity)
    || String(a.title || "").localeCompare(String(b.title || ""));
  const out = COMPANY_STATUS_ORDER.map((status) => ({ status, listings: groups.get(status).sort(byScore) }));
  if (other.length) out.push({ status: "other", listings: other.sort(byScore) });
  return out.filter((g) => g.listings.length);
}

// ---------- LinkedIn (Engine B's formats, D-043) ----------
// Trailing words removed from a company name for LinkedIn's keyword search, compared case-insensitively.
// "& Co" and "& Company" are covered because a trailing "&" is removed once its "Co"/"Company" is gone.
export const LINKEDIN_TRAILING_CORPORATE_WORDS = [
  "Financial", "System", "Group", "Inc", "Inc.", "LLC", "Corp", "Corp.", "Corporation", "Co", "Co.", "Company",
  "Holdings", "&",
];
const TRAILING = new Set(LINKEDIN_TRAILING_CORPORATE_WORDS.map((w) => w.toLowerCase()));

export function linkedinShortName(name, override) {
  if (typeof override === "string" && override.trim()) return override.trim();
  const full = String(name || "").trim().replace(/\s+/g, " ");
  const words = full.split(" ");
  // "Acme, Inc." → "Acme": a comma before a removed word goes with it.
  while (words.length && TRAILING.has(words[words.length - 1].replace(/,$/, "").toLowerCase())) words.pop();
  const short = words.join(" ").replace(/,$/, "").trim();
  return short || full; // never reduce a name to nothing
}

export function linkedinLinks(company, site) {
  const short = encodeURIComponent(linkedinShortName(company.name, company.linkedinName));
  const schoolId = encodeURIComponent(String(site.linkedin_school_id));
  const school = encodeURIComponent(String(site.linkedin_school_name));
  return {
    alumni: `https://www.linkedin.com/search/results/people/?keywords=${short}&origin=COMPANY_PAGE_CANNED_SEARCH&schoolFilter=%5B%22${schoolId}%22%5D`,
    broad: `https://www.linkedin.com/search/results/people/?keywords=${school}%20${short}`,
  };
}
