/**
 * API module — обёртка над fetch для взаимодействия с backend.
 * Все запросы используют httpOnly cookies для авторизации.
 */
const API = {
    BASE: '/clients/api',

    /**
     * Общий метод запроса.
     */
    async request(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
        };
        if (body) {
            opts.body = JSON.stringify(body);
        }

        const response = await fetch(`${this.BASE}${path}`, opts);

        if (response.status === 401) {
            // Токен истёк — переключаем на логин
            window.dispatchEvent(new CustomEvent('auth:expired'));
            throw new Error('Unauthorized');
        }

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
            const errMsg = typeof err.detail === 'object' ? JSON.stringify(err.detail) : err.detail;
            throw new Error(errMsg || `HTTP ${response.status}`);
        }

        // Пустой ответ (204 и т.д.)
        const text = await response.text();
        return text ? JSON.parse(text) : null;
    },

    // --- Auth ---
    login(login, password) {
        return this.request('POST', '/auth/login', { login, password });
    },

    logout() {
        return this.request('POST', '/auth/logout');
    },

    me() {
        return this.request('GET', '/auth/me');
    },

    // --- Appointments ---
    getAppointments(params = {}) {
        const query = new URLSearchParams();
        if (params.target_date) query.set('target_date', params.target_date);
        if (params.date_from) query.set('date_from', params.date_from);
        if (params.date_to) query.set('date_to', params.date_to);
        const qs = query.toString();
        return this.request('GET', `/appointments${qs ? '?' + qs : ''}`);
    },

    createAppointment(data) {
        return this.request('POST', '/appointments', data);
    },

    updateAppointment(id, data) {
        return this.request('PUT', `/appointments/${id}`, data);
    },

    deleteAppointment(id) {
        return this.request('DELETE', `/appointments/${id}`);
    },

    // --- Clients ---
    getClients() {
        return this.request('GET', '/clients');
    },

    createClient(data) {
        return this.request('POST', '/clients', data);
    },

    updateClient(id, data) {
        return this.request('PUT', `/clients/${id}`, data);
    },

    getClientDetails(id) {
        return this.request('GET', `/clients/${id}`);
    },

    addPackage(clientId, data) {
        return this.request('POST', `/clients/${clientId}/packages`, data);
    },

    markAttended(clientId, appointmentId) {
        return this.request('POST', `/clients/${clientId}/attend/${appointmentId}`);
    },

    // --- Finances ---
    getFinanceSummary(period = 'month') {
        return this.request('GET', `/finances/summary?period=${period}`);
    },

    getExpenses(dateFrom, dateTo) {
        let qs = '';
        if (dateFrom && dateTo) {
            qs = `?date_from=${dateFrom}&date_to=${dateTo}`;
        }
        return this.request('GET', `/finances/expenses${qs}`);
    },
    
    getIncome(dateFrom, dateTo) {
        let qs = '';
        if (dateFrom && dateTo) {
            qs = `?date_from=${dateFrom}&date_to=${dateTo}`;
        }
        return this.request('GET', `/finances/income${qs}`);
    },

    addExpense(data) {
        return this.request('POST', '/finances/expenses', data);
    },
    
    addIncome(data) {
        return this.request('POST', '/finances/incomes', data);
    },

    // --- Client name suggestions ---
    getClientNames(query = '') {
        const qs = query ? `?q=${encodeURIComponent(query)}` : '';
        return this.request('GET', `/appointments/clients${qs}`);
    },
};
