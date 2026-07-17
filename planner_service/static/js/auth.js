/**
 * Auth module — логика авторизации и управление экранами.
 */
const Auth = {
    currentUser: null,

    /**
     * Проверяет текущую авторизацию при загрузке.
     */
    async checkAuth() {
        try {
            const user = await API.me();
            this.currentUser = user;
            return true;
        } catch {
            this.currentUser = null;
            return false;
        }
    },

    /**
     * Вход по логину и паролю.
     */
    async login(login, password) {
        const result = await API.login(login, password);
        if (result.success) {
            const user = await API.me();
            this.currentUser = user;
        }
        return result;
    },

    /**
     * Выход из системы.
     */
    async logout() {
        try {
            await API.logout();
        } catch {
            // Даже если ошибка — выходим
        }
        this.currentUser = null;
    },

    /**
     * Показывает экран логина.
     */
    showLogin() {
        document.getElementById('login-screen').classList.add('active');
        document.getElementById('app-screen').classList.remove('active');
        document.getElementById('login-error').classList.add('hidden');
        document.getElementById('login-input').value = '';
        document.getElementById('password-input').value = '';
    },

    /**
     * Показывает основное приложение.
     */
    showApp() {
        document.getElementById('login-screen').classList.remove('active');
        document.getElementById('app-screen').classList.add('active');
    },

    /**
     * Инициализация обработчиков.
     */
    init() {
        const form = document.getElementById('login-form');
        const loginBtn = document.getElementById('login-btn');
        const errorEl = document.getElementById('login-error');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const login = document.getElementById('login-input').value.trim();
            const password = document.getElementById('password-input').value;

            if (!login || !password) return;

            // Show loading
            loginBtn.querySelector('.btn-text').classList.add('hidden');
            loginBtn.querySelector('.btn-loader').classList.remove('hidden');
            loginBtn.disabled = true;
            errorEl.classList.add('hidden');

            try {
                await this.login(login, password);
                this.showApp();
                // Загружаем данные за сегодня
                window.dispatchEvent(new CustomEvent('app:ready'));
            } catch (err) {
                errorEl.textContent = err.message || 'Ошибка авторизации';
                errorEl.classList.remove('hidden');
            } finally {
                loginBtn.querySelector('.btn-text').classList.remove('hidden');
                loginBtn.querySelector('.btn-loader').classList.add('hidden');
                loginBtn.disabled = false;
            }
        });

        // Обработка истечения токена
        window.addEventListener('auth:expired', () => {
            this.currentUser = null;
            this.showLogin();
            showToast('Сессия истекла. Войдите снова.');
        });

        // Logout
        document.getElementById('btn-logout').addEventListener('click', async () => {
            await this.logout();
            this.showLogin();
            document.getElementById('dropdown-menu').classList.add('hidden');
        });
    }
};
