const CACHE = 'kerrie-v2';
const ASSETS = [
  '/',
  '/ops',
  '/offline',
  '/manifest.webmanifest',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/img/logo.svg',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png'
];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).then(response => {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(event.request, copy)).catch(() => {});
      return response;
    }).catch(async () => {
      const cached = await caches.match(event.request);
      return cached || caches.match('/offline');
    })
  );
});
