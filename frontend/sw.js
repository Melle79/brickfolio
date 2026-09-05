/* Brickfolio Service Worker – App-Shell offlinefähig, API immer live */
const CACHE = "brickfolio-v10";
const SHELL = [
  "/",
  "/static/style.css",
  "/static/fonts.css",
  "/static/app.js",
  "/static/jedipedia-titel.js",
  "/static/theme-boot.js",
  "/manifest.webmanifest",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  // Schrift liegt lokal – ohne Internet sieht die Oberfläche trotzdem richtig
  // aus. Daten kommen immer live vom eigenen Server (/api/ wird nie gecacht).
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
  // Fremde Hosts gehen den Browser direkt an. Katalogbilder von BrickLink,
  // Rebrickable und Brickognize haben in diesem Cache nichts verloren – und
  // solange der Worker sie anfasste, machte er aus einem stockenden Abruf
  // einen harten Netzwerkfehler: Das Bild blieb dann leer, statt beim
  // nächsten Blättern einfach nachzuladen.
  if (url.origin !== location.origin) return;
  // Netz zuerst (damit Updates sofort ankommen), Cache als Offline-Fallback
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        if (resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return resp;
      })
      // Ohne Treffer im Cache liefert `caches.match` undefined – und
      // `respondWith(undefined)` wirft „Failed to convert value to
      // 'Response'". Der Browser sah dann einen kaputten Worker statt einer
      // ehrlichen Fehlermeldung. Also immer eine echte Antwort zurückgeben.
      .catch(() => caches.match(e.request).then((hit) => hit || new Response(
        "Offline", { status: 504, statusText: "Gateway Timeout" })))
  );
});

/* Meldung vom eigenen Server. Der Inhalt ist bewusst knapp – Einzelheiten
   stehen in der App, nicht auf dem Sperrbildschirm. */
self.addEventListener("push", (e) => {
  let d = { title: "Brickfolio", body: "", url: "/" };
  try { if (e.data) d = Object.assign(d, e.data.json()); } catch (_) { /* egal */ }
  e.waitUntil(self.registration.showNotification(d.title, {
    body: d.body,
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    // Gleichartige Meldungen ersetzen einander, statt sich zu stapeln.
    tag: "brickfolio",
    data: { url: d.url || "/" },
  }));
});

/* Antippen bringt ein offenes Fenster nach vorn, statt ein zweites zu öffnen. */
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const ziel = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true })
    .then((fenster) => {
      for (const f of fenster) {
        if ("focus" in f) return f.focus();
      }
      return self.clients.openWindow(ziel);
    }));
});
