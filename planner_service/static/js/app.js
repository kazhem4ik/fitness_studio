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

// --- Generic Modal Helper ---
window.showGenericModal = function(title, fields, allowDelete = false) {
    return new Promise((resolve) => {
        const modal = document.getElementById('generic-modal');
        const titleEl = document.getElementById('generic-modal-title');
        const bodyEl = document.getElementById('generic-modal-body');
        const formEl = document.getElementById('generic-form');
        const btnDelete = document.getElementById('generic-modal-delete');
        
        titleEl.textContent = title;
        bodyEl.innerHTML = '';
        
        if (allowDelete) {
            btnDelete.classList.remove('hidden');
        } else {
            btnDelete.classList.add('hidden');
        }
        
        fields.forEach(field => {
            const group = document.createElement('div');
            group.className = 'form-group';
            
            const label = document.createElement('label');
            label.htmlFor = field.id;
            label.textContent = field.label + (field.required ? ' *' : '');
            group.appendChild(label);
            
            if (field.type === 'select') {
                const select = document.createElement('select');
                select.id = field.id;
                if (field.required) select.required = true;
                field.options.forEach(opt => {
                    const option = document.createElement('option');
                    option.value = opt.value;
                    option.textContent = opt.text;
                    if (opt.selected || opt.value === field.value) option.selected = true;
                    select.appendChild(option);
                });
                group.appendChild(select);
            } else {
                const input = document.createElement('input');
                input.type = field.type || 'text';
                input.id = field.id;
                if (field.placeholder) input.placeholder = field.placeholder;
                if (field.value !== undefined) input.value = field.value;
                if (field.required) input.required = true;
                if (field.min !== undefined) input.min = field.min;
                if (field.step !== undefined) input.step = field.step;
                group.appendChild(input);
            }
            bodyEl.appendChild(group);
        });
        
        // Clean up previous listeners
        const newForm = formEl.cloneNode(true);
        formEl.parentNode.replaceChild(newForm, formEl);
        
        const closeBtn = document.getElementById('generic-modal-close');
        const closeIcon = document.getElementById('generic-modal-close-icon');
        
        const close = () => {
            modal.classList.add('hidden');
            resolve(null);
        };
        
        closeBtn.addEventListener('click', close);
        closeIcon.addEventListener('click', close);
        
        newForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const result = {};
            fields.forEach(f => {
                const el = document.getElementById(f.id);
                result[f.id] = el.value;
            });
            modal.classList.add('hidden');
            resolve(result);
        });
        
        const newBtnDelete = document.getElementById('generic-modal-delete');
        
        newBtnDelete.addEventListener('click', () => {
            modal.classList.add('hidden');
            resolve({ action: 'delete' });
        });
        
        modal.classList.remove('hidden');
    });
};

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
        window.dispatchEvent(new CustomEvent('app:ready'));
    } else {
        Auth.showLogin();
    }

    // При успешном логине
    window.addEventListener('app:ready', () => {
        Calendar.switchView('month');
        showPushModalIfNeeded();
        
        const tabAdmin = document.getElementById('tab-admin');
        if (Auth.currentUser && Auth.currentUser.role === 'admin') {
            tabAdmin.classList.remove('hidden');
        } else {
            tabAdmin.classList.add('hidden');
            // Если была открыта админка, переключаем на календарь
            if (document.getElementById('view-admin').classList.contains('active')) {
                document.querySelector('.tab[data-view="month"]').click();
            }
        }
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
            
            // Всегда отписываемся и подписываемся заново, чтобы сбросить старый ключ
            if (subscription) {
                await subscription.unsubscribe();
                subscription = null;
            }
            
            const res = await fetch('/clients/api/auth/push/vapid-public-key?_t=' + Date.now());
            if (!res.ok) throw new Error('No VAPID key');
            const data = await res.json();
            const pubKey = data.public_key.trim();
            
            const uint8ArrayKey = urlB64ToUint8Array(pubKey);
            
            // Пытаемся подписаться, перебирая разные форматы ключа
            try {
                // Сначала пробуем стандартный Uint8Array
                subscription = await swRegistration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: uint8ArrayKey
                });
            } catch (err1) {
                console.warn('subscribe with Uint8Array failed:', err1);
                try {
                    // Если не вышло (ошибка iOS), пробуем передать сырой ArrayBuffer
                    subscription = await swRegistration.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: uint8ArrayKey.buffer
                    });
                } catch (err2) {
                    console.warn('subscribe with ArrayBuffer failed:', err2);
                    // Если и это не вышло, пробуем передать просто строку (DOMString, поддерживается в iOS 16.4+)
                    subscription = await swRegistration.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: pubKey
                    });
                }
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
            if (!silent) showToast('Ошибка: ' + (err.message || err.name || String(err)), 6000);
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
    
    // --- Admin Module (UI) ---
    const AdminUI = {
        init() {
            const btnAddTrainer = document.getElementById('btn-add-trainer');
            if (btnAddTrainer) {
                btnAddTrainer.addEventListener('click', () => this.showTrainerModal());
            }

            const trainerForm = document.getElementById('trainer-form');
            if (trainerForm) {
                trainerForm.addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.saveTrainer();
                });
            }
        },

        async loadTrainers() {
            try {
                const trainers = await API.admin.getTrainers();
                const list = document.getElementById('admin-trainers-list');
                if (!list) return;

                if (!trainers.length) {
                    list.innerHTML = '<p class="empty-text">Нет пользователей</p>';
                    return;
                }

                list.innerHTML = trainers.map(t => `
                    <div class="client-card" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; background:var(--surface-light); padding:16px; border-radius:12px; border:1px solid var(--border);">
                        <div>
                            <div style="font-weight:600; font-size:16px;">${t.display_name} <span style="font-size:12px; font-weight:400; padding:2px 6px; border-radius:4px; background:${t.role === 'admin' ? '#7c3aed' : '#2563eb'}; color:#fff; margin-left:8px;">${t.role}</span></div>
                            <div style="color:var(--text-secondary); font-size:14px; margin-top:4px;">Логин: ${t.login}</div>
                            <div style="color:${t.is_active ? 'var(--color-success)' : 'var(--color-danger)'}; font-size:12px; margin-top:4px;">
                                ${t.is_active ? 'Активен' : 'Деактивирован'}
                            </div>
                        </div>
                        <div style="display:flex; gap:8px;">
                            <button class="btn-icon btn-edit-trainer" data-id="${t.id}" data-trainer='${JSON.stringify(t).replace(/'/g, "&#39;")}'>
                                <i class="fas fa-pen"></i>
                            </button>
                            ${t.id !== Auth.currentUser.id && t.is_active ? `
                            <button class="btn-icon btn-delete-trainer" data-id="${t.id}" style="color:var(--color-danger);">
                                <i class="fas fa-trash"></i>
                            </button>
                            ` : ''}
                        </div>
                    </div>
                `).join('');

                list.querySelectorAll('.btn-edit-trainer').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const t = JSON.parse(e.currentTarget.dataset.trainer);
                        this.showTrainerModal(t);
                    });
                });

                list.querySelectorAll('.btn-delete-trainer').forEach(btn => {
                    btn.addEventListener('click', async (e) => {
                        if (!confirm('Точно деактивировать пользователя? Данные сохранятся.')) return;
                        const id = e.currentTarget.dataset.id;
                        try {
                            await API.admin.deleteTrainer(id);
                            showToast('Пользователь деактивирован');
                            this.loadTrainers();
                        } catch (err) {
                            showToast('Ошибка: ' + err.message);
                        }
                    });
                });

            } catch (err) {
                showToast('Ошибка загрузки пользователей: ' + err.message);
            }
        },

        showTrainerModal(trainer = null) {
            const modal = document.getElementById('trainer-modal');
            const title = document.getElementById('trainer-modal-title');
            
            document.getElementById('trainer-form').reset();
            
            if (trainer) {
                title.textContent = 'Редактировать пользователя';
                document.getElementById('trainer-id').value = trainer.id;
                document.getElementById('trainer-login').value = trainer.login;
                document.getElementById('trainer-login').disabled = true;
                document.getElementById('trainer-name').value = trainer.display_name;
                document.getElementById('trainer-role').value = trainer.role;
                document.getElementById('trainer-active').checked = trainer.is_active;
            } else {
                title.textContent = 'Добавить тренера';
                document.getElementById('trainer-id').value = '';
                document.getElementById('trainer-login').disabled = false;
                document.getElementById('trainer-active').checked = true;
            }
            
            modal.classList.remove('hidden');
        },

        async saveTrainer() {
            const id = document.getElementById('trainer-id').value;
            const login = document.getElementById('trainer-login').value;
            const display_name = document.getElementById('trainer-name').value;
            const role = document.getElementById('trainer-role').value;
            const password = document.getElementById('trainer-password').value;
            const is_active = document.getElementById('trainer-active').checked;

            try {
                if (id) {
                    // Update
                    const data = { display_name, role, is_active };
                    if (password) data.password = password;
                    await API.admin.updateTrainer(id, data);
                    showToast('Пользователь обновлён');
                } else {
                    // Create
                    if (!password) {
                        showToast('Пароль обязателен для нового пользователя');
                        return;
                    }
                    await API.admin.createTrainer({ login, display_name, role, password });
                    showToast('Пользователь создан');
                }
                
                document.getElementById('trainer-modal').classList.add('hidden');
                this.loadTrainers();
            } catch (err) {
                showToast('Ошибка: ' + err.message);
            }
        }
    };
    
    AdminUI.init();
    
    // Переопределяем логику вкладок, чтобы загружать данные при переходе на Админ
    const tabs = document.querySelectorAll('.view-tabs .tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const viewId = tab.dataset.view;
            if (viewId === 'admin') {
                AdminUI.loadTrainers();
            }
        });
    });

});
