// P8 views: Today, Companies, one company, Contacts placeholder and Not found, plus the listing card
// they share with Listings and My List. Each returns DOM nodes built with el(); nothing from a listing
// or company is ever parsed as HTML.
import { STATUS_LABELS, locationLabel, seasonLabel, isNew, postedLabel, parseYmd } from "./lib.js";
import { routeHash, searchCompanies, atsLabel, companyListingGroups, linkedinLinks } from "./hub.js";
import { el, extLink, appLink, formatDate, formatTime, gauge, tagChip } from "./dom.js";

const companyHash = (id) => routeHash("company", id);

// ---------- listing card ----------
export function badges(listing, ctx) {
  const out = [];
  if (isNew(listing, ctx.config, ctx.today)) out.push(el("span", { class: "badge badge-new" }, "NEW"));
  if (listing.status === "filtered") out.push(el("span", { class: "badge badge-warn" }, "Filtered by config — score may be outdated"));
  else if (listing.status !== "open") out.push(el("span", { class: "badge badge-closed" }, STATUS_LABELS[listing.status] || String(listing.status)));
  if (listing.recurring) out.push(el("span", { class: "badge" }, "Recurring program"));
  if (listing.last_known_open && listing.status !== "open") {
    const d = formatDate(listing.last_known_open);
    if (d) out.push(el("span", { class: "badge" }, `Last known open ${d}`));
  }
  const entry = ctx.getEntry ? ctx.getEntry(listing.id) : null;
  if (entry && entry.saved) out.push(el("span", { class: "badge badge-track" }, `My List: ${entry.status}`));
  return out;
}

export function listingCard(listing, ctx, { showCompany = true } = {}) {
  const when = [seasonLabel(listing)];
  const posted = postedLabel(listing, (ymd) => formatDate(ymd));
  if (posted) when.push(posted);
  const deadline = formatDate(parseYmd(listing.deadline));
  if (deadline) when.push(`Deadline ${deadline}`);
  const company = listing.company || "Unknown company";
  const companyNode = showCompany && typeof listing.company_id === "string" && /^[a-z0-9-]+$/.test(listing.company_id)
    ? appLink(companyHash(listing.company_id), company, { class: "card-company" }) : company;
  return el("li", { class: "card", dataset: { id: listing.id } },
    gauge(listing.relevance_score, { animate: !!ctx.animate }),
    el("div", { class: "card-body" },
      el("h3", { class: "card-title" },
        el("button", { type: "button", class: "card-open", dataset: { id: listing.id },
          onclick: (e) => ctx.openDrawer && ctx.openDrawer(listing.id, e.currentTarget) }, listing.title || "(untitled)")),
      el("p", { class: "card-meta" }, companyNode, ` · ${locationLabel(listing, ctx.config)}`),
      el("p", { class: "card-meta" }, when.join(" · ")),
      el("div", { class: "badges" }, badges(listing, ctx))));
}

// ---------- shared bits ----------
function pageHead(title, sub) {
  return el("header", { class: "page-head" },
    el("h1", { class: "page-title", tabindex: "-1" }, title),
    sub ? el("p", { class: "muted" }, sub) : null);
}

function tile(title, { preset, href = "#/listings", body, cta = "Open in Listings", ctx, extraClass = "" }) {
  const a = el("a", { class: "tile-link", href, onclick: preset && ctx.openListings ? (e) => { e.preventDefault(); ctx.openListings(preset); } : null }, cta);
  return el("section", { class: `tile glass ${extraClass}`.trim() },
    el("h2", { class: "tile-title" }, title), body, a);
}

function bigNumber(n, label) {
  return el("p", { class: "big" }, el("span", { class: "big-num" }, String(n)), " ", el("span", { class: "big-label" }, label));
}

export function healthText(company) {
  const h = company.health;
  const checked = company.lastChecked ? formatTime(company.lastChecked) : null;
  if (company.ats === "manual" || (h && h.status === "manual")) return { text: "No feed: check the careers page by hand", bad: false };
  if (!h) return { text: "Not checked yet", bad: false };
  if (h.status === "ok") return { text: `Fetched OK${checked ? ` · checked ${checked}` : ""}`, bad: false };
  const err = h.last_error ? String(h.last_error) : "no details";
  const times = Number.isInteger(h.consecutive_failures) && h.consecutive_failures > 1 ? ` (${h.consecutive_failures} runs in a row)` : "";
  return { text: `Last fetch failed${times}: ${err}${checked ? ` · checked ${checked}` : ""}`, bad: true };
}

// ---------- Today ----------
export function renderToday(ctx) {
  const s = ctx.summary;
  const tiles = [];

  tiles.push(tile("New listings", { ctx, preset: { newOnly: true },
    body: [bigNumber(s.newCount, s.newCount === 1 ? "listing" : "listings"),
      el("p", { class: "muted" }, `First seen in the last ${ctx.config.new_badge_days} day${ctx.config.new_badge_days === 1 ? "" : "s"}.`)] }));

  tiles.push(tile("Posted in the last 24 h", { ctx, preset: { postedDays: 1 },
    body: [bigNumber(s.postedPosted + s.postedFirstSeen, "listings"),
      el("p", {}, `${s.postedPosted} posted · ${s.postedFirstSeen} first seen`),
      el("p", { class: "muted" }, "“First seen” means the source gave no posting date, so the day the scanner found it is used.")] }));

  const dl = s.deadlines;
  tiles.push(tile(`Deadlines in the next ${s.deadlineWindow} days`, { ctx, preset: { deadlineDays: s.deadlineWindow, sort: "deadline" },
    body: dl.length
      ? el("ol", { class: "mini-list" }, dl.slice(0, 5).map((l) => el("li", {},
        el("span", { class: "mini-date" }, formatDate(parseYmd(l.deadline)) || ""), " ",
        el("button", { type: "button", class: "linklike", onclick: (e) => ctx.openDrawer && ctx.openDrawer(l.id, e.currentTarget) }, l.title || "(untitled)"),
        el("span", { class: "muted" }, ` · ${l.company || ""}`))),
        dl.length > 5 ? el("li", { class: "muted" }, `…and ${dl.length - 5} more`) : null)
      : el("p", { class: "muted" }, "No open listing states a deadline in this window. Most sources don't give one.") }));

  const failed = s.failedNames;
  tiles.push(tile("Scan health", { ctx, preset: {}, cta: `Open ${s.open} listings`,
    body: el("dl", { class: "facts" },
      el("dt", {}, "Last scan ran"), el("dd", {}, s.lastScanRan ? formatTime(s.lastScanRan) : "Unknown (shown after the next deploy)"),
      el("dt", {}, "Data updated"), el("dd", {}, s.dataUpdated ? formatTime(s.dataUpdated) : "Unknown"),
      el("dt", {}, "Failed sources"), el("dd", {}, failed.length
        ? failed.map((name, i) => {
          const c = ctx.companyByName && ctx.companyByName.get(name);
          return [i ? ", " : "", c ? appLink(companyHash(c.id), name) : name];
        })
        : "None"),
      el("dt", {}, "Open listings"), el("dd", {}, String(s.open))) }));

  if (s.remote > 0) {
    const label = (ctx.config.remote_sections || []).map((r) => r.label).join(", ") || "Remote";
    tiles.push(tile(label, { ctx, preset: { focusRemote: true }, cta: "Open the remote section",
      body: [bigNumber(s.remote, s.remote === 1 ? "open listing" : "open listings"),
        el("p", { class: "muted" }, "Remote jobs tied to the state, kept apart from the in-person list.")] }));
  }

  tiles.push(tile("Contacts", { ctx, href: "#/contacts", cta: "About contacts", extraClass: "tile-soon",
    body: el("p", { class: "muted" }, "Coming in P9 — private contacts after Google sign-in.") }));

  return [pageHead("Today", "What changed, what's due, and whether the scan is healthy. Open listings only."),
    el("div", { class: "tiles" }, tiles)];
}

// ---------- Companies ----------
export function companyCard(c) {
  const h = healthText(c);
  return el("li", { class: "company glass-card" },
    el("div", { class: "company-main" },
      el("h2", { class: "company-name" }, appLink(companyHash(c.id), c.name)),
      el("p", { class: "company-count" }, el("span", { class: "big-num-sm" }, String(c.openCount)),
        ` open intern listing${c.openCount === 1 ? "" : "s"}`)),
    el("p", { class: "card-meta" }, atsLabel(c), c.inRegistry ? null : " · no longer in the registry"),
    el("p", { class: `card-meta${h.bad ? " text-bad" : ""}` }, h.text),
    c.tags.length ? el("div", { class: "badges" }, c.tags.map(tagChip)) : null);
}

export function renderCompanies(ctx) {
  const list = el("ul", { class: "companies" });
  const count = el("p", { class: "count", "aria-live": "polite" });
  const draw = () => {
    const shown = searchCompanies(ctx.companies, ctx.companyQuery || "");
    count.textContent = `${shown.length} of ${ctx.companies.length} companies`;
    list.replaceChildren(...shown.map(companyCard));
  };
  let timer = null;
  const input = el("input", { id: "companies-search", type: "search", autocomplete: "off", spellcheck: "false",
    oninput: (e) => {
      ctx.companyQuery = e.target.value;
      clearTimeout(timer);
      timer = setTimeout(draw, 80);
    } });
  input.value = ctx.companyQuery || "";
  draw();
  const first = ((ctx.config.site && ctx.config.site.manual_first_tags) || []).map((t) => t.toUpperCase());
  return [pageHead("Companies", `Every company the scanner knows, including manual ones and any no longer in the registry. ${first.length ? `${first.join(", ")} firms first, then` : "Sorted"} by open listings, then name.`),
    el("div", { class: "field search-field glass" }, el("label", { for: "companies-search" }, "Search companies"), input),
    count, list];
}

// ---------- one company ----------
const GROUP_TITLES = { open: "Open", possibly_closed: "Possibly closed", filtered: "Filtered by config", closed: "Closed", other: "Other" };

export function renderCompany(ctx, company) {
  const h = healthText(company);
  const site = ctx.config.site || {};
  const links = linkedinLinks(company, site);
  const groups = companyListingGroups(ctx.listings, company.id);
  const manualLink = company.ats === "manual" ? extLink(company.careersUrl, "Open the careers page", { class: "button" }) : null;

  return [
    el("p", { class: "crumbs" }, appLink("#/companies", "← All companies")),
    el("header", { class: "page-head company-head glass" },
      el("h1", { class: "page-title", tabindex: "-1" }, company.name),
      company.tags.length ? el("div", { class: "badges" }, company.tags.map(tagChip)) : null,
      el("dl", { class: "facts" },
        el("dt", {}, "Source"), el("dd", {}, company.ats === "manual" ? "Manual: no feed, checked by hand" : atsLabel(company)),
        el("dt", {}, "Fetch health"), el("dd", { class: h.bad ? "text-bad" : null }, h.text),
        el("dt", {}, "Open listings"), el("dd", {}, String(company.openCount)),
        company.inRegistry ? null : [el("dt", {}, "Registry"), el("dd", {}, "No longer listed; history kept")]),
      company.ats === "manual"
        ? (manualLink ? el("p", {}, manualLink) : el("p", { class: "muted" }, company.careersUrl
          ? `Careers page (not a web link, so not clickable): ${company.careersUrl}` : "No careers link is known."))
        : null),

    el("section", { class: "panel glass", "aria-labelledby": "company-listings-h" },
      el("h2", { id: "company-listings-h" }, "Listings, past and present"),
      groups.length ? groups.map((g) => [
        el("h3", { class: "group-title" }, `${GROUP_TITLES[g.status]} (${g.listings.length})`),
        el("ul", { class: "cards" }, g.listings.map((l) => listingCard(l, ctx, { showCompany: false })))])
        : el("p", { class: "muted" }, "The scanner hasn't kept any listings from this company yet.")),

    el("section", { class: "panel glass", "aria-labelledby": "company-people-h" },
      el("h2", { id: "company-people-h" }, "Find people on LinkedIn"),
      el("ul", { class: "link-list" },
        el("li", {}, extLink(links.alumni, `${site.linkedin_school_name || "School"} alumni at ${company.name}`)),
        el("li", {}, extLink(links.broad, `Broad search: ${site.linkedin_school_name || ""} ${company.name}`.replace(/\s+/g, " ")))),
      el("p", { class: "muted" }, "Order to reach out: ISU alumni in finance, banking or accounting first, then campus recruiters, then the hiring team. Save the people you pick in Apollo."),
      el("div", { class: "contacts-slot", role: "note" },
        el("h3", {}, "Your contacts"),
        el("p", {}, "Your private contacts for this company will appear here after sign-in (P9)."))),
  ];
}

// ---------- Contacts, Not found ----------
export function renderContacts() {
  return [pageHead("Contacts"), el("section", { class: "panel glass" },
    el("p", {}, "Coming in P9 — private contacts after Google sign-in."))];
}

export function renderNotFound(what = "page") {
  return [pageHead("Not found"), el("section", { class: "panel glass" },
    el("p", {}, `That ${what} doesn't exist here. It may have been renamed, or the link has a typo.`),
    el("p", {}, appLink("#/today", "Go to Today"), " · ", appLink("#/companies", "See all companies")))];
}
