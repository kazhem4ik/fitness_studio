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
        document.getElementById('apt-attendance-actions').classList.add('hidden');
        document.getElementById('apt-contact-method-group').style.display = 'none';
        document.getElementById('apt-confirm-actions').classList.add('hidden');
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

        const contactGroup = document.getElementById('apt-contact-method-group');
        const confirmActions = document.getElementById('apt-confirm-actions');
        if (!apt.is_confirmed) {
            contactGroup.style.display = 'block';
            document.getElementById('apt-contact-method').value = apt.contact_method || 'Не указан';
            confirmActions.classList.remove('hidden');
        } else {
            contactGroup.style.display = 'none';
            confirmActions.classList.add('hidden');
        }

        const actionsDiv = document.getElementById('apt-attendance-actions');
        
        const now = new Date();
        const aptDateTime = new Date(`${apt.date}T${apt.time_start}`);
        if (now < aptDateTime && !apt.is_attended && !apt.is_no_show) {
            actionsDiv.classList.add('hidden');
        } else {
            actionsDiv.classList.remove('hidden');
        }
        
        const btnNoShow = document.getElementById('btn-apt-no-show');
        const btnAttended = document.getElementById('btn-apt-attended');
        const btnPending = document.getElementById('btn-apt-pending');
        
        btnNoShow.className = apt.is_no_show ? 'btn-primary' : 'btn btn-outline';
        btnNoShow.style.backgroundColor = apt.is_no_show ? '#ef4444' : 'transparent';
        btnNoShow.style.borderColor = '#ef4444';
        btnNoShow.style.color = apt.is_no_show ? '#fff' : '#ef4444';
        
        btnAttended.className = apt.is_attended ? 'btn-primary' : 'btn btn-outline';
        btnAttended.style.backgroundColor = apt.is_attended ? '#22c55e' : 'transparent';
        btnAttended.style.borderColor = '#22c55e';
        btnAttended.style.color = apt.is_attended ? '#fff' : '#22c55e';
        
        if (apt.is_no_show || apt.is_attended) {
            btnPending.classList.remove('hidden');
        } else {
            btnPending.classList.add('hidden');
        }

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
            if (err.message && err.message.includes('находится в корзине')) {
                alert(err.message);
            } else {
                showToast('❌ ' + err.message);
            }
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
     * Обновить статус посещаемости
     */
    async setAttendance(status) {
        if (!this.editingId) return;
        try {
            await API.updateAttendance(this.editingId, status);
            showToast('✅ Статус обновлён');
            this.closeModal();
            Calendar.render();
        } catch (err) {
            showToast('❌ ' + err.message);
        }
    },

    /**
     * Подтверждение заявки.
     */
    async confirm() {
        if (!this.editingId) return;
        try {
            await API.updateAppointment(this.editingId, { is_confirmed: true });
            showToast('✅ Заявка подтверждена');
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

        // Сохранение
        document.getElementById('appointment-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.save();
        });

        // Удаление
        document.getElementById('btn-delete-apt').addEventListener('click', () => this.delete());
        
        // Подтверждение заявки
        document.getElementById('btn-confirm-apt').addEventListener('click', () => this.confirm());
        
        // Посещаемость
        document.getElementById('btn-apt-no-show').addEventListener('click', () => this.setAttendance('no_show'));
        document.getElementById('btn-apt-attended').addEventListener('click', () => this.setAttendance('attended'));
        document.getElementById('btn-apt-pending').addEventListener('click', () => this.setAttendance('pending'));

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
                const sugg = document.getElementById('client-suggestions');
                if (sugg) sugg.classList.add('hidden');
            }
        });

        // Модалка выбора клиента
        const btnSelect = document.getElementById('btn-select-client');
        if (btnSelect) {
            btnSelect.addEventListener('click', async () => {
                const modal = document.getElementById('client-select-modal');
                const listEl = document.getElementById('cs-list');
                const searchEl = document.getElementById('cs-search');
                
                modal.classList.remove('hidden');
                document.body.style.overflow = 'hidden';
                
                try {
                    const clients = await API.getClients();
                    
                    const renderList = (query) => {
                        listEl.innerHTML = '';
                        const q = query.toLowerCase();
                        clients.filter(c => c.full_name.toLowerCase().includes(q) || (c.phone && c.phone.includes(q)))
                        .forEach(c => {
                            const div = document.createElement('div');
                            div.className = 'client-card';
                            div.style.cursor = 'pointer';
                            div.innerHTML = `<div><div style="font-weight:600">${c.full_name}</div><div style="font-size:12px;color:gray">${c.phone||''}</div></div>`;
                            div.addEventListener('click', () => {
                                document.getElementById('apt-client-name').value = c.full_name;
                                document.getElementById('apt-client-phone').value = c.phone || '';
                                modal.classList.add('hidden');
                                document.body.style.overflow = '';
                            });
                            listEl.appendChild(div);
                        });
                    };
                    
                    renderList('');
                    searchEl.addEventListener('input', (e) => renderList(e.target.value));
                    
                } catch (e) {
                    console.error(e);
                }
            });
        }
        
        document.getElementById('cs-btn-close')?.addEventListener('click', () => {
            document.getElementById('client-select-modal').classList.add('hidden');
            document.body.style.overflow = '';
        });

        // Автоформатирование телефона
        const phoneInput = document.getElementById('apt-client-phone');
        if (phoneInput) {
            phoneInput.addEventListener('input', function(e) {
                let val = e.target.value.replace(/\D/g, '');
                if (!val) {
                    e.target.value = '';
                    return;
                }
                if (val.startsWith('7') || val.startsWith('8')) {
                    val = '7' + val.substring(1);
                } else {
                    val = '7' + val;
                }
                
                let formatted = '+7';
                if (val.length > 1) formatted += ' (' + val.substring(1, 4);
                if (val.length >= 5) formatted += ') ' + val.substring(4, 7);
                if (val.length >= 8) formatted += '-' + val.substring(7, 9);
                if (val.length >= 10) formatted += '-' + val.substring(9, 11);
                
                e.target.value = formatted;
            });
        }

        // Автоматический расчет времени окончания (+1 час)
        const timeStartInput = document.getElementById('apt-time-start');
        const timeEndInput = document.getElementById('apt-time-end');
        if (timeStartInput && timeEndInput) {
            timeStartInput.addEventListener('change', (e) => {
                if (e.target.value) {
                    const parts = e.target.value.split(':');
                    if (parts.length === 2) {
                        const start = new Date();
                        start.setHours(parseInt(parts[0], 10), parseInt(parts[1], 10), 0);
                        start.setHours(start.getHours() + 1);
                        timeEndInput.value = `${String(start.getHours()).padStart(2, '0')}:${String(start.getMinutes()).padStart(2, '0')}`;
                    }
                }
            });
        }
    }
};
