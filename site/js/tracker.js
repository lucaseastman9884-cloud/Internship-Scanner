// The application tracker. It lives only in this browser's localStorage (SPEC privacy rule):
// nothing is ever sent anywhere. Export/import moves it between browsers as a JSON file.

export const STORAGE_KEY = "internship-scanner:tracker:v1";
export const TRACKER_VERSION = 1;
export const TRACKER_STATUSES = ["Saved", "Applied", "Interview", "Offer", "Rejected"];

const LIMITS = { entries: 5000, notes: 5000, title: 300, company: 200, fileBytes: 1_000_000 };
const ID = /^[A-Za-z0-9_-]{1,64}$/;
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?(Z|[+-]\d{2}:\d{2})$/;

export function emptyTracker() {
  return { version: TRACKER_VERSION, entries: {} };
}

const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
const isPlainObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

function validEntry(e) {
  if (!isPlainObject(e)) return "an entry is not an object";
  const keys = Object.keys(e);
  const allowed = new Set(["saved", "status", "notes", "updated_at", "snapshot"]);
  if (keys.some((k) => !allowed.has(k))) return "an entry has an unknown field";
  if (typeof e.saved !== "boolean") return "saved must be true or false";
  if (!TRACKER_STATUSES.includes(e.status)) return `status must be one of ${TRACKER_STATUSES.join(", ")}`;
  if (typeof e.notes !== "string" || e.notes.length > LIMITS.notes) return "notes must be text under 5,000 characters";
  if (typeof e.updated_at !== "string" || !ISO.test(e.updated_at) || Number.isNaN(Date.parse(e.updated_at))) {
    return "updated_at must be a date and time";
  }
  if (e.snapshot !== undefined) {
    const s = e.snapshot;
    if (!isPlainObject(s) || Object.keys(s).some((k) => k !== "title" && k !== "company")) return "snapshot is malformed";
    if (typeof s.title !== "string" || s.title.length > LIMITS.title) return "snapshot title is malformed";
    if (typeof s.company !== "string" || s.company.length > LIMITS.company) return "snapshot company is malformed";
  }
  return null;
}

// Checks the whole object before anything is used, so a bad file changes nothing.
// Returns { ok: true, tracker } with a clean copy, or { ok: false, error }.
export function validateTracker(data) {
  if (!isPlainObject(data)) return { ok: false, error: "The file isn't a tracker export." };
  if (data.version !== TRACKER_VERSION) return { ok: false, error: `Unsupported tracker version (expected ${TRACKER_VERSION}).` };
  if (!isPlainObject(data.entries)) return { ok: false, error: "The file has no entries list." };
  const ids = Object.keys(data.entries);
  if (ids.length > LIMITS.entries) return { ok: false, error: "The file has too many entries." };
  // A null-prototype map, so ids like "__proto__" can't reach Object.prototype.
  const entries = Object.create(null);
  for (const id of ids) {
    if (!ID.test(id)) return { ok: false, error: "The file has an invalid listing id." };
    const problem = validEntry(data.entries[id]);
    if (problem) return { ok: false, error: `Entry ${id}: ${problem}.` };
    const e = data.entries[id];
    entries[id] = { saved: e.saved, status: e.status, notes: e.notes, updated_at: e.updated_at };
    if (e.snapshot) entries[id].snapshot = { title: e.snapshot.title, company: e.snapshot.company };
  }
  return { ok: true, tracker: { version: TRACKER_VERSION, entries } };
}

export function parseImport(text) {
  if (typeof text !== "string" || text.length > LIMITS.fileBytes) return { ok: false, error: "The file is too large." };
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    return { ok: false, error: "The file isn't valid JSON." };
  }
  return validateTracker(stripExportFields(data));
}

// Newer updated_at wins per listing; on a tie, the current entry stays.
export function mergeTrackers(current, incoming) {
  const entries = Object.create(null);
  for (const id of Object.keys(current.entries)) entries[id] = current.entries[id];
  const summary = { added: 0, updated: 0, kept: 0 };
  for (const id of Object.keys(incoming.entries)) {
    const next = incoming.entries[id];
    const have = own(current.entries, id) ? current.entries[id] : null;
    if (!have) {
      entries[id] = next;
      summary.added++;
    } else if (Date.parse(next.updated_at) > Date.parse(have.updated_at)) {
      entries[id] = next;
      summary.updated++;
    } else {
      summary.kept++;
    }
  }
  return { tracker: { version: TRACKER_VERSION, entries }, summary };
}

export function getEntry(tracker, id) {
  return own(tracker.entries, id) ? tracker.entries[id] : null;
}

// Returns a new tracker; the snapshot keeps My List readable after a listing leaves the data.
export function updateEntry(tracker, listing, changes, now = new Date()) {
  if (!ID.test(listing.id)) return tracker;
  const prev = getEntry(tracker, listing.id) || { saved: false, status: "Saved", notes: "" };
  const next = { ...prev, ...changes, updated_at: now.toISOString() };
  // Choosing a status other than Saved means it's being tracked, so it joins My List.
  if (changes.status && changes.status !== prev.status) next.saved = true;
  if (!TRACKER_STATUSES.includes(next.status)) next.status = "Saved";
  next.notes = String(next.notes || "").slice(0, LIMITS.notes);
  if (listing.title || listing.company) {
    next.snapshot = {
      title: String(listing.title || "").slice(0, LIMITS.title),
      company: String(listing.company || "").slice(0, LIMITS.company),
    };
  }
  const entries = Object.create(null);
  for (const id of Object.keys(tracker.entries)) entries[id] = tracker.entries[id];
  entries[listing.id] = next;
  return { version: TRACKER_VERSION, entries };
}

export function savedIds(tracker) {
  return Object.keys(tracker.entries)
    .filter((id) => tracker.entries[id].saved)
    .sort((a, b) => (tracker.entries[b].updated_at > tracker.entries[a].updated_at ? 1 : -1));
}

export function exportText(tracker) {
  // fromEntries defines own properties, so an id such as "__proto__" stays plain data.
  const entries = Object.fromEntries(Object.keys(tracker.entries).map((id) => [id, tracker.entries[id]]));
  return JSON.stringify({ version: TRACKER_VERSION, exported_at: new Date().toISOString(), entries }, null, 2);
}

// exported_at is written by exportText and allowed back in on import.
export function stripExportFields(data) {
  if (isPlainObject(data) && own(data, "exported_at")) {
    const { exported_at: _ignored, ...rest } = data;
    return rest;
  }
  return data;
}

// storage is window.localStorage or anything with getItem/setItem. Any failure (private mode,
// blocked site data, quota) leaves the app working in memory, and `available` says so.
export function createStore(storage) {
  let available = true;
  let tracker = emptyTracker();
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = validateTracker(JSON.parse(raw));
      if (parsed.ok) tracker = parsed.tracker;
    }
  } catch {
    available = false;
  }
  return {
    get available() { return available; },
    get tracker() { return tracker; },
    set(next) {
      tracker = next;
      try {
        storage.setItem(STORAGE_KEY, JSON.stringify({ version: TRACKER_VERSION, entries: { ...next.entries } })); // spread defines own keys
        return true;
      } catch {
        available = false;
        return false;
      }
    },
  };
}
