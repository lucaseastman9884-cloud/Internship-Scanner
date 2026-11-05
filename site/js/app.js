// The page: loads the data, wires the controls, and draws the list, drawer and My List.
// Listing text never goes into innerHTML: el() below only ever creates text nodes.
import {
  STATUSES, STATUS_LABELS, ELIGIBILITY, NONE_ROLE, NOT_STATED, SORTS,
  applyFilters, sortListings, defaultFilters, activeFilterCount, countLabel, healthSummary,
  locationLabel, seasonLabel, cityKey, sourceNames, humanize, isNew, localDate, milesFromHome, safeUrl,
} from "./lib.js";
import {
  TRACKER_STATUSES, createStore, getEntry, updateEntry, savedIds, exportText, parseImport, mergeTrackers,
} from "./tracker.js";

const PAGE = 100; // cards drawn at a time; "Show more" adds the next batch
const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

// Links from job boards: http(s) only, new tab, no opener and no referrer.
function link(url, text) {
  const safe = safeUrl(url);
  if (!safe) return null;
  return el("a", { href: safe, target: "_blank", rel: "noopener noreferrer" }, text);
}

function formatDate(ymd) {
  if (typeof ymd !== "string" || !/^\d{4}-\d{2}-\d{2}/.test(ymd)) return null;
  const [y, m, d] = ymd.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatTime(iso) {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : new Date(t).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

const state = {
  config: null,
  meta: null,
  listings: [],
  byId: new Map(),
  filters: null,
  sort: "score",
  shown: PAGE,
  view: "listings",
  today: localDate(),
  store: null,
  drawerId: null,
  lastTrigger: null,
};

// ---------- data ----------

// The service worker marks responses it served from its cache, so the page can say it's offline.
async function fetchJson(path) {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return { data: await res.json(), fromCache: res.headers.get("x-served-from") === "sw-cache" };
}

async function load() {
  const [config, listings, meta] = await Promise.allSettled([
    fetchJson("./site_config.json"), fetchJson("./data/internships.json"), fetchJson("./data/meta.json"),
  ]);
  if (config.status !== "fulfilled" || listings.status !== "fulfilled" || !Array.isArray(listings.value.data)) {
    throw new Error("data unavailable");
  }
  state.config = config.value.data;
  state.listings = listings.value.data.filter((l) => l && typeof l === "object" && typeof l.id === "string");
  state.byId = new Map(state.listings.map((l) => [l.id, l]));
  state.meta = meta.status === "fulfilled" ? meta.value.data : null;
  const offline = [config, listings, meta].some((r) => r.status === "fulfilled" && r.value.fromCache);
  return { offline };
}

// ---------- header ----------

function renderHeader(offline) {
  const h = healthSummary(state.meta);
  const when = h && h.scanTime ? formatTime(h.scanTime) : null;
  $("freshness").textContent = when ? `Last scan: ${when}` : "Last scan time unknown";
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

// ---------- filters ----------

function checkboxGroup(fieldset, name, options, selected) {
  for (const [i, opt] of options.entries()) {
    const id = `${name}-${i}`;
    fieldset.append(el("div", { class: "check" },
      el("input", { type: "checkbox", id, name, value: opt.value, checked: selected.includes(opt.value) }),
      el("label", { for: id }, opt.label)));
  }
}

function buildFilterControls() {
  const { config, listings } = state;
  state.filters = defaultFilters(config);
  $("home-name").textContent = config.home.name;
  $("remote-name").textContent = (config.remote_sections || []).map((s) => s.label).join(", ") || "remote";
  $("remote-heading").textContent = (config.remote_sections || []).map((s) => s.label).join(", ") || "Remote";

  const sort = $("f-sort");
  for (const [key, s] of Object.entries(SORTS)) sort.append(el("option", { value: key }, s.label));

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
  state.sort = $("f-sort").value;
}

function writeControlLabels() {
  const distance = $("f-distance");
  distance.disabled = !$("f-distance-on").checked;
  $("f-distance-out").textContent = `${distance.value} miles`;
  const score = $("f-score");
  $("f-score-out").textContent = score.value === score.min ? "Any score" : `${score.value} or higher`;
}

function clearFilters() {
  const d = defaultFilters(state.config);
  $("f-query").value = "";
  $("f-distance-on").checked = false;
  $("f-distance").value = String(d.maxMiles);
  $("f-city").value = "";
  for (const box of $("filter-form").querySelectorAll('input[type="checkbox"][name]')) {
    box.checked = box.name === "status" && d.statuses.includes(box.value);
  }
  $("f-from").value = "";
  $("f-to").value = "";
  $("f-score").value = $("f-score").min;
  $("f-remote").checked = true;
  onFiltersChanged();
}

let searchTimer = null;
function onFiltersChanged() {
  writeControlLabels();
  readFilters();
  state.shown = PAGE;
  renderList();
}

// ---------- list ----------

function badges(listing) {
  const out = [];
  if (Number.isFinite(listing.relevance_score)) out.push(el("span", { class: "badge" }, `Score ${listing.relevance_score}`));
  if (isNew(listing, state.config, state.today)) out.push(el("span", { class: "badge badge-new" }, "NEW"));
  if (listing.status === "filtered") out.push(el("span", { class: "badge badge-warn" }, "Filtered by config — score may be outdated"));
  else if (listing.status !== "open") out.push(el("span", { class: "badge badge-closed" }, STATUS_LABELS[listing.status] || listing.status));
  const entry = state.store && getEntry(state.store.tracker, listing.id);
  if (entry && entry.saved) out.push(el("span", { class: "badge badge-track" }, `My List: ${entry.status}`));
  return out;
}

function card(listing) {
  const posted = formatDate(listing.date_posted);
  const deadline = formatDate(listing.deadline);
  const when = [seasonLabel(listing)];
  if (posted) when.push(`Posted ${posted}`);
  if (deadline) when.push(`Deadline ${deadline}`);
  return el("li", {},
    el("button", { type: "button", class: "card", dataset: { id: listing.id }, onclick: (e) => openDrawer(listing.id, e.currentTarget) },
      el("span", { class: "card-title" }, listing.title || "(untitled)"),
      el("span", { class: "card-meta" }, `${listing.company || "Unknown company"} · ${locationLabel(listing, state.config)}`),
      el("span", { class: "card-meta" }, when.join(" · ")),
      el("span", { class: "badges" }, badges(listing))));
}

function renderList() {
  const { listings, filters, config } = state;
  const { inPerson, remote } = applyFilters(listings, filters, config);
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

  const list = $("list");
  list.replaceChildren(...sortedPeople.slice(0, state.shown).map(card));
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
  $("remote-list").replaceChildren(...sortedRemote.map(card));
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
  const apply = link(listing.apply_url, "Apply on the company site");
  const sources = (listing.sources || []).map((s) => {
    const a = link(s && s.url, humanize((s && s.source_name) || "source"));
    return el("li", {}, a || `${humanize((s && s.source_name) || "source")} (link not shown: not a web address)`);
  });
  return [
    el("h2", { id: "drawer-title" }, listing.title || "(untitled)"),
    el("p", { class: "muted" }, listing.company || ""),
    listing.status === "filtered" ? el("p", { class: "note" }, "Filtered by config — score may be outdated.") : null,
    el("dl", {},
      row("Location", locationLabel(listing, state.config)),
      row("Distance", miles === null ? null : `${Math.round(miles)} miles from ${state.config.home.name}`),
      row("Season", seasonLabel(listing)),
      row("Eligibility", elig.status ? `${humanize(elig.status)}${elig.reason ? ` — ${elig.reason}` : ""}` : null),
      row("Score", Number.isFinite(listing.relevance_score) ? String(listing.relevance_score) : null),
      row("Status", STATUS_LABELS[listing.status] || listing.status),
      row("Role", listing.role_category ? humanize(listing.role_category) : "None"),
      row("Date posted", formatDate(listing.date_posted)),
      row("Deadline", formatDate(listing.deadline)),
      row("First seen", formatDate(listing.first_seen)),
      row("Last seen", formatDate(listing.last_seen)),
      row("Recurring", listing.recurring ? "Yes, this program has run before" : null),
      row("Last known open", formatDate(listing.last_known_open))),
    el("h3", {}, "Apply"),
    apply ? el("p", { class: "apply" }, apply) : el("p", { class: "muted" }, "No safe apply link (not a web address)."),
    sources.length ? [el("h3", {}, "Sources"), el("ul", {}, sources)] : null,
    (listing.match_reasons || []).length ? [el("h3", {}, "Why it scored this way"),
      el("ul", {}, listing.match_reasons.map((r) => el("li", {}, r)))] : null,
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
  $("drawer-body").replaceChildren(...drawerContent(id).flat(2).filter(Boolean));
  $("drawer-body").scrollTop = 0;
  $("drawer").hidden = false;
  $("scrim").hidden = false;
  // inert keeps the page behind out of tab order and screen readers while the dialog is open.
  for (const id2 of ["main", "top"]) $(id2).inert = true;
  document.body.classList.add("drawer-open");
  $("drawer-close").focus();
}

function closeDrawer() {
  if ($("drawer").hidden) return;
  $("drawer").hidden = true;
  $("scrim").hidden = true;
  for (const id of ["main", "top"]) $(id).inert = false;
  document.body.classList.remove("drawer-open");
  // The list may have been redrawn while the drawer was open, so find the card again by id.
  let target = state.lastTrigger;
  if (!target || !target.isConnected) {
    const sel = `.card[data-id="${CSS.escape(state.drawerId)}"]`;
    target = document.querySelector(state.view === "mylist" ? `#mylist ${sel}` : sel);
  }
  state.drawerId = null;
  if (target) target.focus();
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
  if (listing) {
    const li = card(listing);
    li.querySelector(".card").onclick = (e) => openDrawer(id, e.currentTarget);
    return li;
  }
  const snap = entry.snapshot || { title: "Unknown listing", company: "" };
  return el("li", {},
    el("button", { type: "button", class: "card", dataset: { id }, onclick: (e) => openDrawer(id, e.currentTarget) },
      el("span", { class: "card-title" }, snap.title || "Unknown listing"),
      el("span", { class: "card-meta" }, snap.company || ""),
      el("span", { class: "badges" },
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
  renderList();
}

function setView(view) {
  state.view = view;
  $("listings-view").hidden = view !== "listings";
  $("mylist-view").hidden = view !== "mylist";
  $("view-listings").setAttribute("aria-pressed", String(view === "listings"));
  $("view-mylist").setAttribute("aria-pressed", String(view === "mylist"));
  if (view === "mylist") renderMyList();
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
  $("more").addEventListener("click", () => { state.shown += PAGE; renderList(); });
  $("view-listings").addEventListener("click", () => setView("listings"));
  $("view-mylist").addEventListener("click", () => setView("mylist"));
  $("drawer-close").addEventListener("click", closeDrawer);
  $("scrim").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", onDrawerKey);
  $("export-btn").addEventListener("click", exportTracker);
  $("import-btn").addEventListener("click", () => $("import-file").click());
  $("import-file").addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) importTracker(file);
    e.target.value = "";
  });
}

async function start() {
  let storage = null;
  try { storage = window.localStorage; } catch { /* blocked: createStore falls back to memory */ }
  state.store = createStore(storage || { getItem() { throw new Error("no storage"); }, setItem() { throw new Error("no storage"); } });
  if (!state.store.available) $("storage-banner").hidden = false;
  wire();
  registerWorker();
  let offline = false;
  try {
    ({ offline } = await load());
  } catch {
    $("freshness").textContent = "";
    $("state-msg").replaceChildren(
      "The listings couldn't be loaded, and there's no saved copy yet. Check your connection and reload.",
      el("br"), el("button", { type: "button", onclick: () => window.location.reload() }, "Reload"));
    $("result-count").textContent = "";
    return;
  }
  renderHeader(offline);
  buildFilterControls();
  readFilters();
  renderList();
  renderMyList();
}

start();
