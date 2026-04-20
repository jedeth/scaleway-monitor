const CACHE = "scw-monitor-v3";

// Vider les anciens caches à chaque nouvelle version
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ).then(() => self.clients.claim())
));

self.addEventListener("install", e => {
  self.skipWaiting();
});

self.addEventListener("fetch", e => {
  // Réseau d'abord pour tout — cache en fallback offline uniquement
  e.respondWith(
    fetch(e.request).then(r => {
      if (r.ok) {
        const clone = r.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
      }
      return r;
    }).catch(() => caches.match(e.request))
  );
});
