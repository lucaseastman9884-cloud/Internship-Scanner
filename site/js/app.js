// The page: loads the data, routes between views, wires the controls, and draws the drawer.
// Listing and company text never goes into innerHTML: el() only ever creates text nodes.
import {
  STATUSES, STATUS_LABELS, ELIGIBILITY, NONE_ROLE, NOT_STATED, SORTS,
  applyFilters, sortListings, defaultFilters, activeFilterCount, countLabel, healthSummary,
  locationLabel, seasonLabel, cityKey, sourceNames, humanize, localDate, milesFromHome,
  effectiveDate, parseYmd, postedButtonLabel,
} from "./lib.js";
import {
  TRACKER_STATUSES, createStore, getEntry, updateEntry, savedIds, exportText, parseImport, mergeTrackers,
} from "./tracker.js";
import { parseRoute, resolveRoute, navFor, todaySummary, buildCompanies, routeHash } from "./hub.js";
import { el, extLink, appLink, formatDate, formatTime, gauge, reasonChip, tagChip } from "./dom.js";
import { listingCard, renderToday, renderCompanies, renderCompany, renderContacts, renderNotFound } from "./views.js";
import { readStoredTheme, storeTheme, pickTheme } from "./theme.js";

const PAGE = 100; // cards drawn at a time; "Show more" adds the next batch
const $ = (id) => document.getElementById(id);
const VIEW_IDS = {
  today: "view-today", listings: "listings-view", companies: "view-companies", company: "view-company",
  "my-list": "mylist-view", contacts: "view-contacts", "not-found": "view-not-found",
};
const TITLES = { today: "Today", listings: "Listings", companies: "Companies", "my-list": "My List", contacts: "Contacts", "not-found": "Not found" };
const THEME_COLORS = { dark: "#070912", light: "#f4f5fb" };
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const state = {
  config: null,
  meta: null,
  listings: [],
  byId: new Map(),
  companies: [],
  companyById: new Map(),
  companyByName: new Map(),
  companyQuery: "",
  filters: null,
  sort: "score",
  shown: PAGE,
  route: null,
  store: null,
  storage: null,
  drawerId: null,
  lastTrigger: null,
  animateCards: true,
  loaded: false,
};
const today = () => localDate(new Date());

// ---------- data ----------

// The service worker marks responses it served from its cache, so the page can say it's offline.
async function fetchJson(path) {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return { data: await res.json(), fromCache: res.headers.get("x-served-from") === "sw-cache" };
}

async function load() {
  const results = await Promise.allSettled([
    fetchJson("./site_config.json"), fetchJson("./data/internships.json"), fetchJson("./data/meta.json"),
    fetchJson("./companies.json"), fetchJson("./data/companies_status.json"),
  ]);
  const [config, listings, meta, registry, status] = results;
  if (config.status !== "fulfilled" || listings.status !== "fulfilled" || !Array.isArray(listings.value.data)) {
    throw new Error("data unavailable");
  }
  const value = (r) => (r.status === "fulfilled" ? r.value.data : null);
  state.config = { ...config.value.data, site: config.value.data.site || {} };
  state.listings = listings.value.data.filter((l) => l && typeof l === "object" && typeof l.id === "string");
  state.byId = new Map(state.listings.map((l) => [l.id, l]));
  state.meta = value(meta);
  state.companies = buildCompanies(value(registry), value(status), state.listings, state.config);
  state.companyById = new Map(state.companies.map((c) => [c.id, c]));
  state.companyByName = new Map(state.companies.map((c) => [c.name, c]));
  return { offline: results.some((r) => r.status === "fulfilled" && r.value.fromCache) };
}

// ---------- theme ----------

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const btn = $("theme-toggle");
  const next = theme === "dark" ? "light" : "dark";
  btn.textContent = next === "light" ? "Light theme" : "Dark theme";
  btn.setAttribute("aria-label", `Switch to the ${next} theme`);
  btn.setAttribute("aria-pressed", String(theme === "light"));
  $("theme-color").setAttribute("content", THEME_COLORS[theme]);
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  applyTheme(next);
  if (!storeTheme(state.storage, next)) $("storage-banner").hidden = false;
}

// ---------- header ----------

function renderHeader(offline) {
  const h = healthSummary(state.meta);
  const when = h && h.scanTime ? formatTime(h.scanTime) : null;
  // meta.json is only committed when the data changed (D-023), so the scan itself may be newer.
  const ran = state.config.last_scan_ran ? formatTime(state.config.last_scan_ran) : null;
  $("freshness").textContent = [ran ? `Last scan ran: ${ran}` : null,
    when ? `Data updated: ${when}` : "Data update time unknown"].filter(Boolean).join(" · ");
  if (h && h.ok !== null) {
    const parts = [`Sources: ${h.ok} OK`, `${h.failed} failed`];
    if (h.manual) parts.push(`${h.manual} checked by hand`);
    $("health").textContent = parts.join(" · ") + (h.failedNames.length ? ` (failed: ${h.failedNames.join(", ")})` : "");
  } else {
    $("health").textContent = "";
  }
  if (offline) {
    $("offline-banner").textContent = `Offline — data from ${when || "an earlier visit"}`;
    $("offline-banner").hidden = false;
  }
}

// ---------- shared context for views ----------

function ctx(extra = {}) {
  return {
    config: state.config,
    listings: state.listings,
    companies: state.companies,
    companyByName: state.companyByName,
    get companyQuery() { return state.companyQuery; },
    set companyQuery(v) { state.companyQuery = v; },
    today: today(),
    animate: state.animateCards && !reducedMotion(),
    getEntry: (id) => getEntry(state.store.tracker, id),
    openDrawer,
    openListings,
    ...extra,
  };
}

// ---------- filters ----------

function checkboxGroup(fieldset, name, options, selected, type = "checkbox") {
  for (const [i, opt] of options.entries()) {
    const id = `${name}-${i}`;
    fieldset.append(el("div", { class: "check" },
      el("input", { type, id, name, value: opt.value, checked: selected.includes(opt.value) }),
      el("label", { for: id }, opt.label)));
  }
}

function postedOptions() {
  const days = [...(state.config.site.posted_within_days || [1, 3, 7, 30])];
  if (!days.includes(1)) days.unshift(1); // Today's "Posted in the last 24 h" tile needs it
  return days.sort((a, b) => a - b);
}

function buildFilterControls() {
  const { config, listings } = state;
  state.filters = defaultFilters(config);
  state.sort = SORTS[config.site.default_sort] ? config.site.default_sort : "score";
  $("home-name").textContent = config.home.name;
  $("remote-name").textContent = (config.remote_sections || []).map((s) => s.label).join(", ") || "remote";
  $("remote-heading").textContent = (config.remote_sections || []).map((s) => s.label).join(", ") || "Remote";
  $("f-new-days").textContent = `first seen in the last ${config.new_badge_days} day${config.new_badge_days === 1 ? "" : "s"}`;
  $("f-deadline-days").textContent = String(config.site.deadline_window_days ?? 14);
  if (!(config.home && Number.isFinite(config.home.lat))) $("f-distance-on").disabled = true;

  const sort = $("f-sort");
  for (const [key, s] of Object.entries(SORTS)) if (!s.hidden) sort.append(el("option", { value: key }, s.label));
  sort.value = state.sort;

  const seg = $("f-posted-options");
  const opts = [{ value: "", label: "Any" }, ...postedOptions().map((d) => ({ value: String(d), label: postedButtonLabel(d) }))];
  for (const [i, opt] of opts.entries()) {
    const id = `posted-${i}`;
    seg.append(el("input", { type: "radio", id, name: "posted", value: opt.value, checked: opt.value === "" }),
      el("label", { for: id }, opt.label));
  }

  checkboxGroup($("f-status"), "status", STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] })), state.filters.statuses);

  const distance = $("f-distance");
  distance.value = String(config.radius_miles);

  const cities = [...new Set(listings.map(cityKey).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  for (const c of cities) $("f-city").append(el("option", { value: c }, c));

  // Config names come first; any category or season only found in the data is added, so a
  // config change never hides listings that still carry an old value.
  const roles = [...config.role_categories];
  for (const l of listings) if (l.role_category && !roles.includes(l.role_category)) roles.push(l.role_category);
  checkboxGroup($("f-role"), "role",
    [...roles.map((r) => ({ value: r, label: humanize(r) })), { value: NONE_ROLE, label: "None" }], []);

  const seasons = config.seasons.filter((s) => s !== NOT_STATED);
  for (const l of listings) if (l.season && !seasons.includes(l.season)) seasons.push(l.season);
  checkboxGroup($("f-season"), "season", [...seasons, NOT_STATED].map((s) => ({ value: s, label: s })), []);

  const sources = [...new Set(listings.flatMap(sourceNames))].sort();
  checkboxGroup($("f-source"), "source", sources.map((s) => ({ value: s, label: humanize(s) })), []);
  checkboxGroup($("f-elig"), "elig", ELIGIBILITY.map((s) => ({ value: s, label: humanize(s) })), []);

  const dates = listings.map((l) => l.first_seen).filter(Boolean).sort();
  for (const id of ["f-from", "f-to"]) {
    if (dates.length) { $(id).min = dates[0]; $(id).max = dates[dates.length - 1]; }
  }

  // The slider's lowest stop means "no minimum".
  const scores = listings.map((l) => l.relevance_score).filter(Number.isFinite);
  const score = $("f-score");
  score.min = String(Math.floor(Math.min(0, ...scores) / 5) * 5);
  score.max = String(Math.ceil(Math.max(5, ...scores) / 5) * 5);
  score.value = score.min;

  if (window.matchMedia("(min-width: 900px)").matches) $("filters").open = true;
  writeControlLabels();
}

function checkedValues(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((i) => i.value);
}

function readFilters() {
  const score = $("f-score");
  const f = state.filters;
  f.query = $("f-query").value;
  f.distanceOn = $("f-distance-on").checked;
  f.maxMiles = Number($("f-distance").value);
  f.city = $("f-city").value;
  f.statuses = checkedValues("status");
  f.roles = checkedValues("role");
  f.seasons = checkedValues("season");
  f.sources = checkedValues("source");
  f.eligibility = checkedValues("elig");
  f.dateFrom = $("f-from").value;
  f.dateTo = $("f-to").value;
  f.minScore = score.value === score.min ? null : Number(score.value);
  f.showRemote = $("f-remote").checked;
  const posted = checkedValues("posted")[0] || "";
  f.postedDays = posted ? Number(posted) : null;
  f.newOnly = $("f-new").checked;
  f.deadlineDays = $("f-deadline").checked ? Number(state.config.site.deadline_window_days ?? 14) : null;
  state.sort = $("f-sort").value;
}

function writeControlLabels() {
  const distance = $("f-distance");
  distance.disabled = !$("f-distance-on").checked;
  $("f-distance-out").textContent = `${distance.value} miles`;
  const score = $("f-score");
  $("f-score-out").textContent = score.value === score.min ? "Any score" : `${score.value} or higher`;
}

function resetControls() {
  const d = defaultFilters(state.config);
  $("f-query").value = "";
  $("f-distance-on").checked = false;
  $("f-distance").value = String(d.maxMiles);
  $("f-city").value = "";
  for (const box of $("filter-form").querySelectorAll('input[type="checkbox"][name]')) {
    box.checked = box.name === "status" && d.statuses.includes(box.value);
  }
  for (const radio of document.querySelectorAll('input[name="posted"]')) radio.checked = radio.value === "";
  $("f-new").checked = false;
  $("f-deadline").checked = false;
  $("f-from").value = "";
  $("f-to").value = "";
  $("f-score").value = $("f-score").min;
  $("f-remote").checked = true;
}

function clearFilters() {
  resetControls();
  onFiltersChanged();
}

let searchTimer = null;
function onFiltersChanged() {
  writeControlLabels();
  readFilters();
  state.shown = PAGE;
  state.animateCards = false; // gauges fill in once per visit, not on every keystroke
  renderList();
}

// A Today tile: start from the default filters, set the tile's one filter, then open Listings.
function openListings(preset = {}) {
  resetControls();
  if (preset.newOnly) $("f-new").checked = true;
  if (preset.postedDays) {
    for (const radio of document.querySelectorAll('input[name="posted"]')) radio.checked = radio.value === String(preset.postedDays);
  }
  if (preset.deadlineDays != null) $("f-deadline").checked = true;
  $("f-sort").value = preset.sort && SORTS[preset.sort] ? preset.sort
    : (SORTS[state.config.site.default_sort] ? state.config.site.default_sort : "score");
  readFilters();
  state.shown = PAGE;
  state.pendingFocus = preset.focusRemote ? "remote-section" : null;
  if (location.hash === "#/listings") onRoute(); else location.hash = "#/listings";
}

// ---------- list ----------

function renderList() {
  const { listings, filters, config } = state;
  const { inPerson, remote } = applyFilters(listings, filters, config, new Date());
  const sortedPeople = sortListings(inPerson, state.sort);
  const sortedRemote = sortListings(remote, state.sort);

  const statuses = new Set(filters.statuses);
  const total = listings.filter((l) => statuses.has(l.status)).length;
  $("result-count").textContent = filters.statuses.length
    ? countLabel(inPerson.length + remote.length, total, filters.statuses)
    : "No status selected: tick at least one under Status.";
  $("status-note").hidden = !(statuses.has("filtered") && listings.some((l) => l.status === "filtered"));
  const n = activeFilterCount(filters, config);
  $("filter-count").textContent = n ? `(${n} active)` : "";

  const c = ctx();
  $("list").replaceChildren(...sortedPeople.slice(0, state.shown).map((l) => listingCard(l, c)));
  const more = $("more");
  more.hidden = sortedPeople.length <= state.shown;
  more.textContent = `Show more (${sortedPeople.length - state.shown} left)`;

  const msg = $("state-msg");
  if (!inPerson.length && !remote.length) {
    msg.replaceChildren("No listings match — ", el("button", { type: "button", class: "secondary", onclick: clearFilters }, "Clear filters"));
    msg.hidden = false;
  } else if (!inPerson.length) {
    msg.replaceChildren("No in-person listings match. Remote listings are below.");
    msg.hidden = false;
  } else {
    msg.hidden = true;
  }

  const section = $("remote-section");
  section.hidden = !filters.showRemote || !(config.remote_sections || []).length;
  $("remote-list").replaceChildren(...sortedRemote.map((l) => listingCard(l, c)));
  $("remote-empty").hidden = sortedRemote.length > 0;
}

// ---------- drawer ----------

function row(label, value) {
  return value === null || value === undefined || value === "" ? [] : [el("dt", {}, label), el("dd", {}, value)];
}

function trackerControls(listing) {
  const entry = getEntry(state.store.tracker, listing.id) || { saved: false, status: "Saved", notes: "" };
  const save = (changes) => {
    state.store.set(updateEntry(state.store.tracker, listing, changes));
    if (!state.store.available) $("storage-banner").hidden = false;
    refreshAfterTrackerChange();
    const e = getEntry(state.store.tracker, listing.id);
    $("tracker-updated").textContent = e ? `Updated ${formatTime(e.updated_at)}` : "";
    $("t-saved").checked = !!(e && e.saved);
  };
  const status = el("select", { id: "t-status", onchange: (e) => save({ status: e.target.value }) },
    TRACKER_STATUSES.map((s) => el("option", { value: s, selected: s === entry.status }, s)));
  let notesTimer = null;
  const notes = el("textarea", { id: "t-notes", maxlength: "5000",
    oninput: (e) => { clearTimeout(notesTimer); const v = e.target.value; notesTimer = setTimeout(() => save({ notes: v }), 400); },
    // Leaving the box saves at once, so closing the tab right after typing loses nothing.
    onchange: (e) => { clearTimeout(notesTimer); save({ notes: e.target.value }); } });
  notes.value = entry.notes;
  return el("div", { class: "tracker" },
    el("div", { class: "check" },
      el("input", { type: "checkbox", id: "t-saved", checked: entry.saved, onchange: (e) => save({ saved: e.target.checked }) }),
      el("label", { for: "t-saved" }, "Save to My List")),
    el("div", {}, el("label", { for: "t-status" }, "Status"), status),
    el("div", {}, el("label", { for: "t-notes" }, "Notes (only in this browser)"), notes),
    el("p", { id: "tracker-updated", class: "muted" }, entry.updated_at ? `Updated ${formatTime(entry.updated_at)}` : ""));
}

function companyLinkInDrawer(listing) {
  const name = listing.company || "";
  if (!state.companyById.has(listing.company_id)) return name;
  // Closing first keeps focus handling simple; the hash change then opens the company page.
  return appLink(routeHash("company", listing.company_id), name, { onclick: () => closeDrawer(false) });
}

function drawerContent(id) {
  const listing = state.byId.get(id);
  if (!listing) {
    // Tracked earlier but no longer in the data: show what the tracker remembered.
    const entry = getEntry(state.store.tracker, id);
    const snap = (entry && entry.snapshot) || { title: "Unknown listing", company: "" };
    const stub = { id, title: snap.title, company: snap.company };
    return [
      el("h2", { id: "drawer-title" }, snap.title || "Unknown listing"),
      el("p", { class: "muted" }, snap.company),
      el("p", { class: "note" }, "This listing is no longer in the scanner's data."),
      el("h3", {}, "Tracker"), trackerControls(stub),
    ];
  }
  const elig = listing.eligibility || {};
  const miles = milesFromHome(listing, state.config.home);
  const apply = extLink(listing.apply_url, "Apply on the company site", { class: "button" });
  const sources = (listing.sources || []).map((s) => {
    const a = extLink(s && s.url, humanize((s && s.source_name) || "source"));
    return el("li", {}, a || `${humanize((s && s.source_name) || "source")} (link not shown: not a web address)`);
  });
  const eff = effectiveDate(listing);
  return [
    el("div", { class: "drawer-title-row" },
      gauge(listing.relevance_score, { size: "lg", animate: !reducedMotion() }),
      el("div", {},
        el("h2", { id: "drawer-title" }, listing.title || "(untitled)"),
        el("p", { class: "muted" }, companyLinkInDrawer(listing)))),
    listing.status === "filtered" ? el("p", { class: "note" }, "Filtered by config — score may be outdated.") : null,
    el("dl", {},
      row("Location", locationLabel(listing, state.config)),
      row("Distance", miles === null ? null : `${Math.round(miles)} miles from ${state.config.home.name}`),
      row("Season", seasonLabel(listing)),
      row("Eligibility", elig.status ? `${humanize(elig.status)}${elig.reason ? ` — ${elig.reason}` : ""}` : null),
      row("Score", Number.isFinite(listing.relevance_score) ? String(listing.relevance_score) : null),
      row("Status", STATUS_LABELS[listing.status] || listing.status),
      row("Role", listing.role_category ? humanize(listing.role_category) : "None"),
      // A first_seen date is never called a posting date.
      eff && eff.kind === "posted" ? row("Posted", formatDate(eff.ymd)) : row("Posted", "Not stated by the source"),
      row("Deadline", formatDate(parseYmd(listing.deadline))),
      row("First seen", formatDate(listing.first_seen)),
      row("Last seen", formatDate(listing.last_seen)),
      row("Recurring", listing.recurring ? "Yes, this program has run before" : null),
      row("Last known open", formatDate(listing.last_known_open)),
      (listing.tags || []).length ? row("Tags", el("span", { class: "badges" }, listing.tags.map(tagChip))) : []),
    el("h3", {}, "Apply"),
    apply ? el("p", { class: "apply" }, apply) : el("p", { class: "muted" }, "No safe apply link (not a web address)."),
    sources.length ? [el("h3", {}, "Sources"), el("ul", {}, sources)] : null,
    (listing.match_reasons || []).length ? [el("h3", {}, "Why it scored this way"),
      el("ul", { class: "chips" }, listing.match_reasons.map(reasonChip))] : null,
    listing.description_snippet ? [el("h3", {}, "Description snippet"), el("p", { class: "snippet" }, listing.description_snippet)] : null,
    el("h3", {}, "Tracker"), trackerControls(listing),
  ];
}

function focusables() {
  return [...$("drawer").querySelectorAll("a[href], button, input, select, textarea, [tabindex]:not([tabindex='-1'])")]
    .filter((n) => !n.disabled && !n.hidden);
}

function openDrawer(id, trigger) {
  state.drawerId = id;
  state.lastTrigger = trigger || null;
  $("drawer-body").replaceChildren(...drawerContent(id).flat(3).filter(Boolean));
  $("drawer-body").scrollTop = 0;
  $("drawer").hidden = false;
  $("scrim").hidden = false;
  // inert keeps the page behind out of tab order and screen readers while the dialog is open.
  for (const id2 of ["main", "top"]) $(id2).inert = true;
  document.body.classList.add("drawer-open");
  $("drawer-close").focus();
}

function closeDrawer(restoreFocus = true) {
  if ($("drawer").hidden) return;
  $("drawer").hidden = true;
  $("scrim").hidden = true;
  for (const id of ["main", "top"]) $(id).inert = false;
  document.body.classList.remove("drawer-open");
  // The list may have been redrawn while the drawer was open, so find the card again by id.
  let target = state.lastTrigger;
  if (restoreFocus && (!target || !target.isConnected)) {
    const view = $(VIEW_IDS[state.route ? state.route.name : "listings"]);
    target = view && view.querySelector(`.card-open[data-id="${CSS.escape(state.drawerId)}"]`);
  }
  state.drawerId = null;
  if (restoreFocus && target && target.isConnected) target.focus();
}

function onDrawerKey(e) {
  if ($("drawer").hidden) return;
  if (e.key === "Escape") { e.preventDefault(); closeDrawer(); return; }
  if (e.key !== "Tab") return;
  const items = focusables();
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

// ---------- My List ----------

function myListCard(id) {
  const listing = state.byId.get(id);
  const entry = getEntry(state.store.tracker, id);
  if (listing) return listingCard(listing, ctx({ animate: false }));
  const snap = entry.snapshot || { title: "Unknown listing", company: "" };
  return el("li", { class: "card", dataset: { id } },
    gauge(null),
    el("div", { class: "card-body" },
      el("h3", { class: "card-title" },
        el("button", { type: "button", class: "card-open", dataset: { id }, onclick: (e) => openDrawer(id, e.currentTarget) },
          snap.title || "Unknown listing")),
      el("p", { class: "card-meta" }, snap.company || ""),
      el("div", { class: "badges" },
        el("span", { class: "badge badge-closed" }, "No longer in the data"),
        el("span", { class: "badge badge-track" }, `My List: ${entry.status}`))));
}

function renderMyList() {
  const ids = savedIds(state.store.tracker);
  $("mylist-count").textContent = `(${ids.length})`;
  $("mylist").replaceChildren(...ids.map(myListCard));
  $("mylist-empty").hidden = ids.length > 0;
}

function refreshAfterTrackerChange() {
  renderMyList();
  if (state.route && state.route.name === "listings") renderList();
  else if (state.route && state.route.name === "company") renderRoute(state.route, { keepFocus: true });
}

function exportTracker() {
  const blob = new Blob([exportText(state.store.tracker)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: `internship-tracker-${localDate()}.json` });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function importTracker(file) {
  const msg = $("import-msg");
  msg.hidden = false;
  let text;
  try {
    text = await file.text();
  } catch {
    msg.textContent = "Import failed: the file couldn't be read. Nothing was changed.";
    return;
  }
  const parsed = parseImport(text);
  if (!parsed.ok) {
    msg.textContent = `Import failed: ${parsed.error} Nothing was changed.`;
    return;
  }
  const { tracker, summary } = mergeTrackers(state.store.tracker, parsed.tracker);
  const stored = state.store.set(tracker);
  msg.textContent = `Imported: ${summary.added} added, ${summary.updated} updated, ${summary.kept} kept (yours were newer or the same).`
    + (stored ? "" : " Storage is blocked, so this lasts only until you close the tab.");
  if (!stored) $("storage-banner").hidden = false;
  refreshAfterTrackerChange();
}

// ---------- routing ----------

function renderRoute(route, { keepFocus = false } = {}) {
  const view = resolveRoute(route, state.companyById);
  const { name } = view;
  const company = view.company || null;
  for (const [key, id] of Object.entries(VIEW_IDS)) $(id).hidden = key !== name;
  const nav = navFor({ name });
  for (const a of document.querySelectorAll("[data-nav]")) {
    if (a.dataset.nav === nav) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }

  const c = ctx();
  if (name === "today") $("view-today").replaceChildren(...renderToday({ ...c, summary: todaySummary(state.listings, state.config, state.meta, c.today) }).flat(3).filter(Boolean));
  else if (name === "listings") renderList();
  else if (name === "companies") $("view-companies").replaceChildren(...renderCompanies(c).flat(3).filter(Boolean));
  else if (name === "company") $("view-company").replaceChildren(...renderCompany(c, company).flat(3).filter(Boolean));
  else if (name === "my-list") renderMyList();
  else if (name === "contacts") $("view-contacts").replaceChildren(...renderContacts().flat(3).filter(Boolean));
  else $("view-not-found").replaceChildren(...renderNotFound(view.what).flat(3).filter(Boolean));

  document.title = `${company ? company.name : TITLES[name]} · Internship Scanner`;
  if (keepFocus) return;
  // Move focus to the new page's heading (not on first load), so keyboard and screen-reader users land there.
  const focusTarget = state.pendingFocus ? $(state.pendingFocus) : $(VIEW_IDS[name]).querySelector(".page-title");
  state.pendingFocus = null;
  if (!state.loaded) return;
  if (focusTarget && focusTarget.id === "remote-section") {
    focusTarget.focus({ preventScroll: true });
    focusTarget.scrollIntoView({ block: "start" });
  } else {
    window.scrollTo(0, 0);
    if (focusTarget) focusTarget.focus({ preventScroll: true });
  }
}

function onRoute() {
  if (!state.config) return;
  closeDrawer(false);
  const route = parseRoute(location.hash);
  const same = state.route && state.route.name === route.name && state.route.id === route.id;
  state.route = route;
  state.animateCards = !same;
  const update = () => renderRoute(route);
  // View Transitions where the browser has them, never under reduced motion.
  if (state.loaded && !same && typeof document.startViewTransition === "function" && !reducedMotion()) {
    document.startViewTransition(update);
  } else {
    update();
  }
}

// ---------- service worker ----------

function registerWorker() {
  // Service workers need a secure context (HTTPS, or localhost for testing).
  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  let reloading = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (reloading) return;
    reloading = true;
    window.location.reload();
  });
  navigator.serviceWorker.register("./service-worker.js").then((reg) => {
    const offer = (worker) => {
      // Only an update needs a reload; the very first install has no page to replace.
      if (!worker || !navigator.serviceWorker.controller) return;
      $("update-banner").hidden = false;
      $("update-reload").onclick = () => worker.postMessage({ type: "SKIP_WAITING" });
    };
    if (reg.waiting) offer(reg.waiting);
    reg.addEventListener("updatefound", () => {
      const worker = reg.installing;
      if (!worker) return;
      worker.addEventListener("statechange", () => { if (worker.state === "installed") offer(worker); });
    });
  }).catch(() => { /* the app still works online without it */ });
}

// ---------- start ----------

function wire() {
  const form = $("filter-form");
  form.addEventListener("submit", (e) => e.preventDefault());
  form.addEventListener("change", (e) => { if (e.target.id !== "f-query") onFiltersChanged(); });
  form.addEventListener("input", (e) => {
    if (e.target.id === "f-query") {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(onFiltersChanged, 150);
    } else if (e.target.type === "range") {
      onFiltersChanged(); // sliders update while dragging, not only on release
    }
  });
  $("clear-filters").addEventListener("click", clearFilters);
  $("more").addEventListener("click", () => { state.shown += PAGE; state.animateCards = false; renderList(); });
  $("drawer-close").addEventListener("click", () => closeDrawer());
  $("scrim").addEventListener("click", () => closeDrawer());
  document.addEventListener("keydown", onDrawerKey);
  $("export-btn").addEventListener("click", exportTracker);
  $("import-btn").addEventListener("click", () => $("import-file").click());
  $("import-file").addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) importTracker(file);
    e.target.value = "";
  });
  $("theme-toggle").addEventListener("click", toggleTheme);
  window.addEventListener("hashchange", onRoute);
  // The moving background pauses while the tab is hidden (it costs nothing to look at then).
  const syncHidden = () => document.documentElement.classList.toggle("is-hidden", document.hidden);
  document.addEventListener("visibilitychange", syncHidden);
  syncHidden();
}

async function start() {
  try { state.storage = window.localStorage; } catch { state.storage = null; /* blocked: memory only */ }
  const stored = readStoredTheme(state.storage);
  applyTheme(pickTheme(stored, null)); // a returning visitor's choice applies before any data loads
  state.store = createStore(state.storage || { getItem() { throw new Error("no storage"); }, setItem() { throw new Error("no storage"); } });
  if (!state.store.available) $("storage-banner").hidden = false;
  wire();
  registerWorker();
  let offline = false;
  try {
    ({ offline } = await load());
  } catch {
    $("freshness").textContent = "";
    $("load-state").replaceChildren(
      "The listings couldn't be loaded, and there's no saved copy yet. Check your connection and reload.",
      el("br"), el("button", { type: "button", onclick: () => window.location.reload() }, "Reload"));
    return;
  }
  if (!stored) applyTheme(pickTheme(null, state.config.site.default_theme));
  $("load-state").hidden = true;
  renderHeader(offline);
  buildFilterControls();
  readFilters();
  renderMyList();
  onRoute();
  state.loaded = true;
}

start();
