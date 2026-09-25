const CACHE_NAME = "agi-web-agent-v1";
const SHELL = ["/", "/web/index.html", "/web/app.js", "/web/manifest.webmanifest"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", event => {
  const u = new URL(event.request.url);
  if (u.origin !== location.origin || event.request.method !== "GET") return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(resp => {
    if (resp.ok) { const clone = resp.clone(); caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone)); }
    return resp;
  })));
});