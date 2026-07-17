/**
 * Appointments module — управление записями (создание, редактирование, удаление).
 */
const Appointments = {
    editingId: null,
    suggestTimer: null,

    /**
     * Открыть модалку для новой записи.
     */
    openNew(date = null) {
        this.editingId = null;
        document.getElementById('modal-title').textContent = 'Новая запись';
        document.getElementById('btn-delete-apt').classList.add('hidden');
        document.getElementById('btn-save-apt').textContent = 'Сохранить';

        // Очистка формы
        const form = document.getElementById('appointment-form');
        form.reset();

        // Установить дату (текущую или выбранную)
        const d = date || Calendar.currentDate;
        document.getElementById('apt-date').value = Calendar.formatDate(d);

        // Время по умолчанию — ближайший час
        const now = new Date();
        const nextHour = new Date(now);
        nextHour.setMinutes(0, 0, 0);
        nextHour.setHours(nextHour.getHours() + 1);
        const endHour = new Date(nextHour);
        endHour.setHours(endHour.getHours() + 1);

        document.getElementById('apt-time-start').value = 
            `${String(nextHour.getHours()).padStart(2,'0')}:00`;
        document.getElementById('apt-time-end').value = 
            `${String(endHour.getHours()).padStart(2,'0')}:00`;

        this.showModal();
    },

    /**
     * Открыть модалку для редактирования.
     */
    openEdit(apt) {
        this.editingId = apt.id;
        document.getElementById('modal-title').textContent = 'Редактирование';
        document.getElementById('btn-delete-apt').classList.remove('hidden');
        document.getElementById('btn-save-apt').textContent = 'Обновить';

        // Заполняем поля
        document.getElementById('apt-client-name').value = apt.client_name;
        document.getElementById('apt-client-phone').value = apt.client_phone || '';
        document.getElementById('apt-date').value = apt.date;
        document.getElementById('apt-time-start').value = apt.time_start.substring(0, 5);
        document.getElementById('apt-time-end').value = apt.time_end.substring(0, 5);
        document.getElementById('apt-training-type').value = apt.training_type || '';
        document.getElementById('apt-notes').value = apt.notes || '';
        document.getElementById('apt-price').value = apt.price || '';
        document.getElementById('apt-payment-method').value = apt.payment_method || '';
        document.getElementById('apt-is-paid').checked = apt.is_paid;

        this.showModal();
    },

    /**
     * Показать модалку.
     */
    showModal() {
        document.getElementById('appointment-modal').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    },

    /**
     * Закрыть модалку.
     */
    closeModal() {
        const modal = document.getElementById('appointment-modal');
        const sheet = modal.querySelector('.modal-sheet');

        sheet.style.animation = 'none';
        sheet.offsetHeight; // reflow
        sheet.style.animation = 'slideDown 0.25s var(--ease-out) forwards';

        setTimeout(() => {
            modal.classList.add('hidden');
            sheet.style.animation = '';
            document.body.style.overflow = '';
            document.getElementById('client-suggestions').classList.add('hidden');
        }, 250);
    },

    /**
     * Сохранение записи (создание или обновление).
     */
    async save() {
        const data = {
            client_name: document.getElementById('apt-client-name').value.trim(),
            client_phone: document.getElementById('apt-client-phone').value.trim() || null,
            date: document.getElementById('apt-date').value,
            time_start: document.getElementById('apt-time-start').value + ':00',
            time_end: document.getElementById('apt-time-end').value + ':00',
            training_type: document.getElementById('apt-training-type').value || null,
            notes: document.getElementById('apt-notes').value.trim() || null,
            price: parseFloat(document.getElementById('apt-price').value) || null,
            payment_method: document.getElementById('apt-payment-method').value || null,
            is_paid: document.getElementById('apt-is-paid').checked,
        };

        if (!data.client_name || !data.date || !data.time_start || !data.time_end) {
            showToast('Заполните обязательные поля');
            return;
        }

        try {
            if (this.editingId) {
                await API.updateAppointment(this.editingId, data);
                showToast('✅ Запись обновлена');
            } else {
                await API.createAppointment(data);
                showToast('✅ Запись создана');
            }
            this.closeModal();
            Calendar.render();
        } catch (err) {
            showToast('❌ ' + err.message);
        }
    },

    /**
     * Удаление записи.
     */
    async delete() {
        if (!this.editingId) return;

        if (!confirm('Удалить эту запись?')) return;

        try {
            await API.deleteAppointment(this.editingId);
            showToast('🗑️ Запись удалена');
            this.closeModal();
            Calendar.render();
        } catch (err) {
            showToast('❌ ' + err.message);
        }
    },

    /**
     * Автоподсказки имён клиентов.
     */
    async loadSuggestions(query) {
        if (query.length < 1) {
            document.getElementById('client-suggestions').classList.add('hidden');
            return;
        }

        try {
            const names = await API.getClientNames(query);
            const container = document.getElementById('client-suggestions');

            if (names.length === 0) {
                container.classList.add('hidden');
                return;
            }

            container.innerHTML = '';
            names.forEach(name => {
                const item = document.createElement('div');
                item.className = 'suggestion-item';
                item.textContent = name;
                item.addEventListener('click', () => {
                    document.getElementById('apt-client-name').value = name;
                    container.classList.add('hidden');
                });
                container.appendChild(item);
            });
            container.classList.remove('hidden');
        } catch {
            // Игнорируем ошибки подсказок
        }
    },

    /**
     * Инициализация обработчиков.
     */
    init() {
        // FAB — новая запись
        document.getElementById('fab-add').addEventListener('click', () => this.openNew());

        // Закрытие модалки
        document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
        document.querySelector('.modal-overlay').addEventListener('click', () => this.closeModal());

        // Сохранение
        document.getElementById('appointment-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.save();
        });

        // Удаление
        document.getElementById('btn-delete-apt').addEventListener('click', () => this.delete());

        // Автоподсказки
        document.getElementById('apt-client-name').addEventListener('input', (e) => {
            clearTimeout(this.suggestTimer);
            this.suggestTimer = setTimeout(() => {
                this.loadSuggestions(e.target.value.trim());
            }, 300);
        });

        // Скрыть подсказки при клике вне
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#apt-client-name') && !e.target.closest('#client-suggestions')) {
                document.getElementById('client-suggestions').classList.add('hidden');
            }
        });
    }
};
