// Run with: node --test tests/js/
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  STORAGE_KEY, emptyTracker, validateTracker, parseImport, mergeTrackers, updateEntry, getEntry, savedIds,
  exportText, createStore,
} from "../../site/js/tracker.js";

const entry = (over = {}) => ({ saved: true, status: "Saved", notes: "", updated_at: "2026-11-03T10:00:00.000Z", ...over });
const file = (entries, over = {}) => JSON.stringify({ version: 1, entries, ...over });

function memoryStorage() {
  const map = new Map();
  return { getItem: (k) => (map.has(k) ? map.get(k) : null), setItem: (k, v) => map.set(k, String(v)), map };
}

test("updateEntry saves status, notes and a snapshot", () => {
  let t = emptyTracker();
  const listing = { id: "abc123", title: "IB Summer Analyst", company: "Blair" };
  t = updateEntry(t, listing, { saved: true }, new Date("2026-11-03T10:00:00Z"));
  t = updateEntry(t, listing, { status: "Applied", notes: "sent resume" }, new Date("2026-11-04T10:00:00Z"));
  assert.deepEqual(getEntry(t, "abc123"), {
    saved: true, status: "Applied", notes: "sent resume", updated_at: "2026-11-04T10:00:00.000Z",
    snapshot: { title: "IB Summer Analyst", company: "Blair" },
  });
  assert.deepEqual(savedIds(t), ["abc123"]);
});

test("choosing a status adds the listing to My List", () => {
  const t = updateEntry(emptyTracker(), { id: "x1", title: "t", company: "c" }, { status: "Interview" });
  assert.equal(getEntry(t, "x1").saved, true);
});

test("export then import round-trips", () => {
  let t = updateEntry(emptyTracker(), { id: "a1", title: "T", company: "C" }, { saved: true, notes: "n" });
  const parsed = parseImport(exportText(t));
  assert.equal(parsed.ok, true);
  assert.deepEqual({ ...parsed.tracker.entries }, { ...t.entries });
});

test("merge: newer updated_at wins, ties keep the current entry", () => {
  const current = { version: 1, entries: { a: entry({ notes: "mine", updated_at: "2026-11-03T10:00:00.000Z" }),
    b: entry({ notes: "mine-b", updated_at: "2026-11-05T10:00:00.000Z" }), c: entry({ notes: "same" }) } };
  const incoming = { version: 1, entries: { a: entry({ notes: "theirs", updated_at: "2026-11-04T10:00:00.000Z" }),
    b: entry({ notes: "old", updated_at: "2026-11-01T10:00:00.000Z" }), c: entry({ notes: "tie" }), d: entry({ notes: "new" }) } };
  const { tracker, summary } = mergeTrackers(current, incoming);
  assert.equal(tracker.entries.a.notes, "theirs");
  assert.equal(tracker.entries.b.notes, "mine-b");
  assert.equal(tracker.entries.c.notes, "same");
  assert.equal(tracker.entries.d.notes, "new");
  assert.deepEqual(summary, { added: 1, updated: 1, kept: 2 });
});

test("import rejects malformed files without changing anything", () => {
  const bad = [
    "not json",
    "[]",
    "null",
    file({}, { version: 2 }),
    JSON.stringify({ version: 1, entries: [] }),
    file({ "bad id!": entry() }),
    file({ a: entry({ status: "Hired" }) }),
    file({ a: entry({ saved: "yes" }) }),
    file({ a: entry({ notes: 5 }) }),
    file({ a: entry({ notes: "x".repeat(5001) }) }),
    file({ a: entry({ updated_at: "yesterday" }) }),
    file({ a: entry({ extra: 1 }) }),
    file({ a: entry({ snapshot: { title: "<b>", company: "c", html: "<script>" } }) }),
    file({ a: { ...entry(), snapshot: "text" } }),
    "x".repeat(1_000_001),
  ];
  for (const text of bad) {
    const r = parseImport(text);
    assert.equal(r.ok, false, `accepted: ${text.slice(0, 80)}`);
    assert.equal(typeof r.error, "string");
  }
});

test("import of a hostile file can't pollute prototypes", () => {
  const text = '{"version":1,"entries":{"__proto__":{"saved":true,"status":"Saved","notes":"","updated_at":"2026-11-03T10:00:00.000Z"},'
    + '"constructor":{"saved":true,"status":"Saved","notes":"<img src=x onerror=alert(1)>","updated_at":"2026-11-03T10:00:00.000Z"}}}';
  const r = parseImport(text);
  assert.equal(r.ok, true);
  assert.equal(({}).saved, undefined);
  assert.equal(Object.getPrototypeOf(r.tracker.entries), null);
  // Notes are kept as plain text; the app renders them with textContent.
  assert.equal(r.tracker.entries.constructor.notes, "<img src=x onerror=alert(1)>");
  const { tracker } = mergeTrackers(emptyTracker(), r.tracker);
  assert.equal(({}).status, undefined);
  assert.ok(exportText(tracker).includes('"__proto__"'));
});

test("validateTracker returns a clean copy", () => {
  const r = validateTracker({ version: 1, entries: { a: entry({ snapshot: { title: "T", company: "C" } }) } });
  assert.equal(r.ok, true);
  assert.deepEqual({ ...r.tracker.entries }, { a: entry({ snapshot: { title: "T", company: "C" } }) });
});

test("store persists under one namespaced key and survives a reload", () => {
  const storage = memoryStorage();
  const s1 = createStore(storage);
  s1.set(updateEntry(s1.tracker, { id: "a1", title: "T", company: "C" }, { saved: true }));
  assert.deepEqual([...storage.map.keys()], [STORAGE_KEY]);
  const s2 = createStore(storage);
  assert.equal(getEntry(s2.tracker, "a1").saved, true);
  assert.equal(s2.available, true);
});

test("store keeps working in memory when storage throws", () => {
  const broken = { getItem() { throw new Error("SecurityError"); }, setItem() { throw new Error("QuotaExceeded"); } };
  const s = createStore(broken);
  assert.equal(s.available, false);
  assert.equal(s.set(updateEntry(s.tracker, { id: "a1", title: "T", company: "C" }, { saved: true })), false);
  assert.equal(getEntry(s.tracker, "a1").saved, true);
});

test("a corrupt stored value is ignored, not fatal", () => {
  const storage = memoryStorage();
  storage.setItem(STORAGE_KEY, "{broken");
  const s = createStore(storage);
  assert.deepEqual(Object.keys(s.tracker.entries), []);
});
