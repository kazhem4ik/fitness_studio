/**
 * App — главный модуль. Инициализация, toast, глобальные обработчики.
 */

// --- Toast ---
function showToast(message, duration = 2500) {
    const toast = document.getElementById('toast');
    const msg = document.getElementById('toast-message');
    msg.textContent = message;
    toast.classList.remove('hidden', 'hiding');

    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => {
        toast.classList.add('hiding');
        setTimeout(() => {
            toast.classList.add('hidden');
            toast.classList.remove('hiding');
        }, 250);
    }, duration);
}

// --- SlideDown animation (for modal close) ---
const styleSheet = document.createElement('style');
styleSheet.textContent = `
@keyframes slideDown {
    from { transform: translateY(0); }
    to { transform: translateY(100%); }
}`;
document.head.appendChild(styleSheet);

// --- App Init ---
document.addEventListener('DOMContentLoaded', async () => {
    // Инициализируем модули
    Auth.init();
    Calendar.init();
    Appointments.init();

    // Dropdown menu toggle
    const btnMenu = document.getElementById('btn-menu');
    const dropdown = document.getElementById('dropdown-menu');
    btnMenu.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.classList.toggle('hidden');
    });
    document.addEventListener('click', () => {
        dropdown.classList.add('hidden');
    });

    // Close modals on overlay click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (!modal) return;
            const closeBtnId = 
                modal.id === 'appointment-modal' ? 'modal-close' :
                modal.id === 'client-modal' ? 'client-modal-close' :
                modal.id === 'client-details-modal' ? 'cd-btn-close' :
                modal.id === 'client-select-modal' ? 'cs-btn-close' : null;
            if (closeBtnId) {
                const btn = document.getElementById(closeBtnId);
                if (btn) btn.click();
            }
        });
    });

    // Проверяем авторизацию
    const isAuth = await Auth.checkAuth();
    if (isAuth) {
        Auth.showApp();
        Calendar.switchView('month');
    } else {
        Auth.showLogin();
    }

    // При успешном логине
    window.addEventListener('app:ready', () => {
        Calendar.switchView('month');
        showPushModalIfNeeded();
    });

    // Service Worker registration — делаем сразу, не дожидаясь логина
    let swRegistration = null;
    if ('serviceWorker' in navigator) {
        try {
            swRegistration = await navigator.serviceWorker.register('/clients/sw.js?v=8', {
                scope: '/clients/'
            });
            console.log('SW registered:', swRegistration.scope);
            
            // Если уже авторизованы при загрузке страницы
            if (isAuth) {
                showPushModalIfNeeded();
            }
        } catch (err) {
            console.warn('SW registration failed:', err);
        }
    }

    // --- Push Notification Logic ---
    const pushModal = document.getElementById('push-permission-modal');
    const btnPushAllow = document.getElementById('btn-push-allow');
    const btnPushDismiss = document.getElementById('btn-push-dismiss');
    const btnPush = document.getElementById('btn-push-subscribe');

    // Кнопка в dropdown — тот же эффект что и кнопка "Разрешить" в модалке
    if (btnPush) {
        btnPush.addEventListener('click', async () => {
            dropdown.classList.add('hidden');
            await requestPushPermission();
        });
    }

    if (btnPushAllow) {
        btnPushAllow.addEventListener('click', async () => {
            hidePushModal();
            await requestPushPermission();
        });
    }

    if (btnPushDismiss) {
        btnPushDismiss.addEventListener('click', () => {
            hidePushModal();
            // Запомним что пользователь нажал "Не сейчас" — не спрашиваем снова в эту сессию
            sessionStorage.setItem('push_dismissed', '1');
        });
    }

    function showPushModal() {
        if (!pushModal) return;
        pushModal.style.display = 'flex';
    }

    function hidePushModal() {
        if (!pushModal) return;
        pushModal.style.display = 'none';
    }

    function showPushModalIfNeeded() {
        if (!swRegistration) return;
        if (!('Notification' in window)) return; // iOS без экрана домой или старая версия
        if (Notification.permission === 'granted') {
            // Уже разрешено — тихо переподписываемся
            subscribeToPush(true);
            if (btnPush) btnPush.style.display = 'none';
            return;
        }
        if (Notification.permission === 'denied') {
            if (btnPush) btnPush.style.display = 'none';
            return;
        }
        // permission === 'default' — показываем модалку
        if (sessionStorage.getItem('push_dismissed')) {
            // Пользователь уже отклонил в этой сессии — показываем кнопку в меню
            if (btnPush) btnPush.style.display = 'flex';
            return;
        }
        // Небольшая задержка чтобы экран успел прорисоваться
        setTimeout(() => showPushModal(), 800);
    }

    async function requestPushPermission() {
        if (!swRegistration || !('Notification' in window)) return;
        try {
            const perm = await Notification.requestPermission();
            if (perm === 'granted') {
                if (btnPush) btnPush.style.display = 'none';
                await subscribeToPush(false);
            } else {
                showToast('Уведомления отклонены', 3000);
                if (btnPush) btnPush.style.display = 'none';
            }
        } catch (err) {
            console.error('requestPermission error:', err);
            showToast('Ошибка запроса разрешения', 3000);
        }
    }

    async function subscribeToPush(silent = false) {
        if (!swRegistration) return;
        if (!('Notification' in window)) return;
        if (Notification.permission !== 'granted') return;

        try {
            let subscription = await swRegistration.pushManager.getSubscription();
            
            if (!subscription) {
                const res = await fetch('/clients/api/auth/push/vapid-public-key');
                if (!res.ok) throw new Error('No VAPID key');
                const data = await res.json();
                const applicationServerKey = urlB64ToUint8Array(data.public_key);
                subscription = await swRegistration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey
                });
            }

            await fetch('/clients/api/auth/push/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    endpoint: subscription.endpoint,
                    keys: {
                        p256dh: arrayBufferToBase64(subscription.getKey('p256dh')),
                        auth: arrayBufferToBase64(subscription.getKey('auth'))
                    }
                })
            });

            if (!silent) showToast('✅ Уведомления включены!', 3000);
        } catch (err) {
            console.error('Failed to subscribe for push:', err);
            if (!silent) showToast('Ошибка при подписке на push', 3000);
        }
    }

    function urlB64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }
    
    function arrayBufferToBase64(buffer) {
        let binary = '';
        const bytes = new Uint8Array(buffer);
        const len = bytes.byteLength;
        for (let i = 0; i < len; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }
});
