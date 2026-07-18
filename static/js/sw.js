
const CACHE = "book-with-kerrie-v1";
const ASSETS = [
  "/",
  "/book",
  "/trips",
  "/track",
  "/static/css/style.css",
  "/static/js/main.js",
  "/static/logo.svg",
  "/favicon.ico",
];
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
});
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((key) => (key === CACHE ? null : caches.delete(key))))
    )
  );
});
self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request).catch(() => caches.match("/"));
    })
  );
});
