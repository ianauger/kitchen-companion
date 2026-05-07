// Kitchen Companion Service Worker
const CACHE_NAME = 'kitchen-companion-v1';
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/features',
  '/search',
];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        // Non-critical: some pages may require auth and 404 on install
        console.warn('Service worker: some assets could not be cached', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch: network-first with cache fallback for HTML, cache-first for static
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  const isHTML = event.request.headers.get('accept')?.includes('text/html') ||
                 url.pathname.endsWith('/') || !url.pathname.includes('.');
  const isStatic = url.pathname.match(/\.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?)$/);
  const isAPI = url.pathname.startsWith('/api/');

  // API and dynamic requests: network-only
  if (isAPI || event.request.method !== 'GET') {
    return;
  }

  if (isStatic) {
    // Static assets: cache-first
    event.respondWith(
      caches.match(event.request).then((cached) => {
        const fetchPromise = fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        });
        return cached || fetchPromise;
      })
    );
  } else if (isHTML) {
    // Pages: network-first with offline fallback
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => {
          return caches.match(event.request).then((cached) => {
            return cached || caches.match('/');
          });
        })
    );
  }
});
