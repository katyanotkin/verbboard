const CACHE = "vb-v22";
const PRECACHE = [
  "/static/common.css",
  "/static/home.css",
  "/static/learn.css",
  "/static/verbs.css",
  "/static/auth.js",
  "/static/progress.js",
  "/static/storage.js",
  "/static/streak.js",
  "/static/practice_loop.js",
  "/static/verbs_filters.js",
  "/static/pwa.js",
  "/static/learn.js",
  "/static/learn_practice.js",
  "/static/snail.svg",
  "/static/arrow.svg",
  "/static/icons/icon-192x192.png",
  "/static/icons/icon-512x512.png"
];

self.addEventListener("install", e =>
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(PRECACHE))
      .then(() => self.skipWaiting())
      .catch(err => { console.error("SW precache failed:", err); self.skipWaiting(); })
  )
);

self.addEventListener("activate", e =>
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    // clients.claim() intentionally omitted -- claiming open pages mid-session
    // triggers Firebase Auth's controllerchange listener and cancels in-progress
    // signInWithPopup calls. The SW takes control naturally on the next navigation.
  )
);

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);

  const isStaticAsset =
    url.pathname.startsWith("/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname.endsWith(".css") ||
    url.pathname.endsWith(".js") ||
    url.pathname.endsWith(".svg") ||
    url.pathname.endsWith(".png");

  if (!isStaticAsset) {
    return; // bypass SW for API/auth/navigation
  }

  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
