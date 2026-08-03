/**
 * Service Worker — только push-уведомления.
 *
 * Запросы намеренно не перехватываются: WebKit на iOS может зависнуть на
 * повреждённом Cache Storage. Страницы и статика всегда загружаются с сервера.
 */

self.addEventListener('install', () => {
    self.skipWaiting();
});

// --- Activate: удаляем все старые офлайн-кэши ---
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(async names => {
            await Promise.all(
                names
                    .filter(name => name.startsWith('fitness-planner-'))
                    .map(name => caches.delete(name))
            );
            await self.clients.claim();
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
