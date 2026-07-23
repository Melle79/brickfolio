/* Brickfolio Service Worker – App-Shell offlinefähig, API immer live */
const CACHE = "brickfolio-v3";
const SHELL = [
  "/",
  "/static/style.css",
  "/static/fonts.css",
  "/static/app.js",
  "/manifest.webmanifest",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  // Schrift liegt lokal – so bleibt die App auch ohne Internet vollständig
  "/static/fonts/nunito-latin-600.woff2",
  "/static/fonts/nunito-latin-800.woff2",
  "/static/fonts/nunito-latin-900.woff2",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return;
  // Netz zuerst (damit Updates sofort ankommen), Cache als Offline-Fallback
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        if (resp.ok && url.origin === location.origin) {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return resp;
      })
      .catch(() => caches.match(e.request))
  );
});
