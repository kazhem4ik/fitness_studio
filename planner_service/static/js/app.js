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
        Calendar.render();
    });

    // Service Worker registration
    if ('serviceWorker' in navigator) {
        try {
            const reg = await navigator.serviceWorker.register('/clients/sw.js', {
                scope: '/clients/'
            });
            console.log('SW registered:', reg.scope);
        } catch (err) {
            console.warn('SW registration failed:', err);
        }
    }
});
