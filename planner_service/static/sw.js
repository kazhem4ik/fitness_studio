/**
 * Service Worker — кэширование ресурсов для офлайн-работы + push-уведомления.
 */

const CACHE_NAME = 'fitness-planner-v11';
const STATIC_ASSETS = [
    '/clients/',
    '/clients/static/css/style.css',
    '/clients/static/js/api.js',
    '/clients/static/js/auth.js',
    '/clients/static/js/calendar.js',
    '/clients/static/js/appointments.js',
    '/clients/static/js/app.js',
    '/clients/static/icons/icon-192.png',
    '/clients/static/icons/icon-512.png',
];

// --- Install: кэшируем статику ---
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// --- Activate: чистим старые кэши ---
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(names => {
            return Promise.all(
                names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))
            );
        })
    );
    self.clients.claim();
});

// --- Fetch: Network First для API, Cache First для статики ---
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // API запросы — всегда сеть
    if (url.pathname.includes('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() => {
                return new Response(JSON.stringify({ detail: 'Нет соединения' }), {
                    status: 503,
                    headers: { 'Content-Type': 'application/json' },
                });
            })
        );
        return;
    }

    // Статика — Cache First
    event.respondWith(
        caches.match(event.request).then(cached => {
            return cached || fetch(event.request).then(response => {
                // Кэшируем новые ресурсы
                if (response.status === 200) {
                    const cloned = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, cloned));
                }
                return response;
            });
        })
    );
});

// --- Push уведомления ---
self.addEventListener('push', (event) => {
    let data = { title: 'Напоминание', body: 'У вас скоро тренировка!' };

    if (event.data) {
        try {
            data = event.data.json();
        } catch {
            data.body = event.data.text();
        }
    }

    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/clients/static/icons/icon-192.png',
            badge: '/clients/static/icons/icon-192.png',
            vibrate: [200, 100, 200],
            tag: data.tag || 'default',
            data: data.url || '/clients/',
        })
    );
});

// --- Клик по уведомлению ---
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: 'window' }).then(clientList => {
            for (const client of clientList) {
                if (client.url.includes('/clients') && 'focus' in client) {
                    return client.focus();
                }
            }
            return clients.openWindow(event.notification.data || '/clients/');
        })
    );
});
