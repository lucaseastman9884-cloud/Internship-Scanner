// Offline support. The app shell is cached per app version; the data is network-first, so a
// visit online always gets the newest scan and a visit offline gets the last one seen.
// scripts/stage_site.py replaces the stamp below with a hash of site/, so any app change gets a
// new cache name and the old one is deleted on activate.
const VERSION = "__BUILD_STAMP__";
const SHELL_CACHE = `shell-${VERSION}`;
const DATA_CACHE = "data-v1"; // kept across app versions: it's the offline copy of the listings

const SHELL = [
  "./",
  "./index.html",
  "./styles.css",
  "./js/app.js",
  "./js/lib.js",
  "./js/tracker.js",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/maskable-512.png",
];
const DATA = ["site_config.json", "data/internships.json", "data/meta.json", "data/companies_status.json"];
const scopeUrl = (path) => new URL(path, self.registration.scope).href;

self.addEventListener("install", (event) => {
  // cache: "reload" skips the browser's HTTP cache, so a new version never precaches old files.
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) =>
    cache.addAll(SHELL.map((p) => new Request(p, { cache: "reload" })))));
  // No skipWaiting here: the page shows "New version — reload" and the visitor chooses when.
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keep = new Set([SHELL_CACHE, DATA_CACHE]);
    for (const name of await caches.keys()) if (!keep.has(name)) await caches.delete(name);
    await self.clients.claim();
  })());
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});

// A cached data response gets a marker header, so the page can say "Offline — data from …".
async function markCached(response) {
  const headers = new Headers(response.headers);
  headers.set("x-served-from", "sw-cache");
  return new Response(await response.blob(), { status: response.status, statusText: response.statusText, headers });
}

async function networkFirst(request) {
  const cache = await caches.open(DATA_CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request.url, response.clone());
    return response;
  } catch (err) {
    const cached = await cache.match(request.url);
    if (cached) return markCached(cached);
    throw err;
  }
}

async function shellFirst(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request, { ignoreSearch: true });
  if (cached) return cached;
  try {
    return await fetch(request);
  } catch (err) {
    // An offline navigation to any page in scope gets the app.
    if (request.mode === "navigate") {
      const index = await cache.match(scopeUrl("./index.html"));
      if (index) return index;
    }
    throw err;
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // the app makes no third-party requests
  const dataUrls = DATA.map(scopeUrl);
  if (dataUrls.includes(url.origin + url.pathname)) {
    event.respondWith(networkFirst(new Request(url.origin + url.pathname, { cache: "no-cache" })));
    return;
  }
  event.respondWith(shellFirst(request));
});
