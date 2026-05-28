const CACHE = "vb-v12";
const PRECACHE = [
  "/static/common.css",
  "/static/home.css",
  "/static/learn.css",
  "/static/verbs.css",
  "/static/auth.js",
  "/static/progress.js",
  "/static/storage.js",
  "/static/practice_loop.js",
  "/static/verbs_filters.js",
  "/static/snail.svg",
  "/static/arrow.svg",
  "/static/icons/icon-192x192.png",
  "/static/icons/icon-512x512.png"
];

self.addEventListener("install", e =>
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  )
);

self.addEventListener("activate", e =>
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  )
);

self.addEventListener("fetch", e => {
  if (e.request.mode === "navigate") return;
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
