const CACHE = "scw-monitor-v1";
const ASSETS = ["/scaleway-monitor/", "/scaleway-monitor/index.html", "/scaleway-monitor/manifest.json"];

self.addEventListener("install", e => e.waitUntil(
  caches.open(CACHE).then(c => c.addAll(ASSETS))
));

self.addEventListener("fetch", e => {
  // Toujours réseau d'abord pour les données, cache pour les assets
  if (e.request.url.includes("scaleway.json")) {
    e.respondWith(
      fetch(e.request).then(r => {
        const clone = r.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return r;
      }).catch(() => caches.match(e.request))
    );
  } else {
    e.respondWith(
      caches.match(e.request).then(r => r || fetch(e.request))
    );
  }
});
