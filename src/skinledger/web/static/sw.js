// SkinLedger service worker.
// It caches only the static app shell. API responses, pages, images and masks stay
// network-only: they are never written to a cache.

const CACHE_NAME = "skinledger-shell-v2";
const SHELL_ASSETS = [
  "/offline",
  "/static/app.css",
  "/static/manifest.webmanifest",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/vendor/pico.min.css",
  "/static/vendor/htmx.min.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
      ),
  );
  self.clients.claim();
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  const sameOrigin = url.origin === self.location.origin;

  // Static assets: cache-first.
  if (sameOrigin && url.pathname.startsWith("/static/")) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Pages: network-only, with the cached offline shell as the only fallback.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/offline")));
  }

  // Anything else (API calls, images, masks) is left to the network and never cached.
});
