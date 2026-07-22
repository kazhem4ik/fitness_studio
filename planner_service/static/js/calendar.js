/**
 * Calendar module — управление видами День/Неделя/Месяц.
 */
const Calendar = {
    currentDate: new Date(),
    currentView: 'month',
    appointments: [],

    // Русские названия
    MONTHS: ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'],
    MONTHS_GEN: ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'],
    DAYS_SHORT: ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'],
    DAYS_FULL: ['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'],

    // Цвета для типов тренировок
    TRAINING_COLORS: {
        'Персональная': '#7c3aed',
        'Групповая': '#3b82f6',
        'Растяжка': '#ec4899',
        'Кардио': '#f59e0b',
        'Силовая': '#ef4444',
        'Функциональная': '#22c55e',
        'Йога': '#8b5cf6',
        'Пилатес': '#06b6d4',
        'Другое': '#6b7280',
    },

    /**
     * Форматирование даты в YYYY-MM-DD.
     */
    formatDate(d) {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    },

    /**
     * Проверка — сегодня ли дата.
     */
    isToday(d) {
        const today = new Date();
        return d.getFullYear() === today.getFullYear() &&
               d.getMonth() === today.getMonth() &&
               d.getDate() === today.getDate();
    },

    /**
     * Получить день недели (0=Пн, 6=Вс).
     */
    getDayOfWeek(d) {
        return (d.getDay() + 6) % 7;
    },

    /**
     * Понедельник текущей недели.
     */
    getWeekStart(d) {
        const result = new Date(d);
        const day = this.getDayOfWeek(result);
        result.setDate(result.getDate() - day);
        return result;
    },

    /**
     * Обновление заголовка.
     */
    updateHeader() {
        const headerTitle = document.getElementById('header-title');
        const headerDate = document.getElementById('header-date');
        const today = new Date();

        if (this.isToday(this.currentDate)) {
            headerTitle.textContent = 'Сегодня';
        } else {
            headerTitle.textContent = this.DAYS_FULL[this.getDayOfWeek(this.currentDate)];
        }

        headerDate.textContent = `${today.getDate()} ${this.MONTHS_GEN[today.getMonth()]} ${today.getFullYear()}`;
    },

    // =========================================================
    //  DAY VIEW
    // =========================================================
    async renderDay() {
        const dateStr = this.formatDate(this.currentDate);
        const dayDateText = document.getElementById('day-date-text');
        const timeline = document.getElementById('day-timeline');
        const emptyState = document.getElementById('day-empty');

        // Дата в навигации
        const d = this.currentDate;
        const dayName = this.DAYS_SHORT[this.getDayOfWeek(d)];
        dayDateText.textContent = `${dayName}, ${d.getDate()} ${this.MONTHS_GEN[d.getMonth()]}`;

        // Загружаем записи
        try {
            this.appointments = await API.getAppointments({ target_date: dateStr });
        } catch (err) {
            console.error('Failed to load appointments:', err);
            this.appointments = [];
        }

        // Рендерим таймлайн
        timeline.innerHTML = '';

        if (this.appointments.length === 0) {
            timeline.classList.add('hidden');
            emptyState.classList.remove('hidden');
            return;
        }

        timeline.classList.remove('hidden');
        emptyState.classList.add('hidden');

        // Генерируем слоты с 7:00 до 22:00
        const hours = [];
        for (let h = 7; h <= 22; h++) {
            hours.push(h);
        }

        // Группируем записи по часам
        const aptsByHour = {};
        this.appointments.forEach(apt => {
            const startHour = parseInt(apt.time_start.split(':')[0]);
            if (!aptsByHour[startHour]) aptsByHour[startHour] = [];
            aptsByHour[startHour].push(apt);
        });

        hours.forEach(h => {
            const slotDiv = document.createElement('div');
            slotDiv.className = 'time-slot';

            const timeLabel = document.createElement('div');
            timeLabel.className = 'slot-time';
            timeLabel.textContent = `${String(h).padStart(2, '0')}:00`;

            const slotLine = document.createElement('div');
            slotLine.className = 'slot-line';

            if (aptsByHour[h]) {
                aptsByHour[h].forEach(apt => {
                    slotLine.appendChild(this.createAptCard(apt));
                });
            }

            slotDiv.appendChild(timeLabel);
            slotDiv.appendChild(slotLine);
            timeline.appendChild(slotDiv);
        });

        this.updateHeader();
    },

    /**
     * Создание карточки записи.
     */
    createAptCard(apt) {
        const card = document.createElement('div');
        card.className = 'apt-card';
        card.dataset.id = apt.id;

        // Цвет по типу тренировки
        const color = this.TRAINING_COLORS[apt.training_type] || '#7c3aed';
        card.style.setProperty('--apt-color', color);

        // Время
        const timeStart = apt.time_start.substring(0, 5);
        const timeEnd = apt.time_end.substring(0, 5);

        // Бейджи
        let badges = '';
        if (apt.training_type) {
            badges += `<span class="apt-badge training-type" style="background:${color}20;color:${color}">${apt.training_type}</span>`;
        }
        if (apt.price) {
            const paidClass = apt.is_paid ? 'paid' : 'unpaid';
            const paidLabel = apt.is_paid ? '✓ Оплачено' : 'Не оплачено';
            badges += `<span class="apt-badge ${paidClass}">${paidLabel}</span>`;
        }

        let priceHtml = '';
        if (apt.price) {
            priceHtml = `<span class="apt-price">${apt.price.toLocaleString('ru-RU')} ₽</span>`;
        }

        card.innerHTML = `
            <div class="apt-card-header">
                <span class="apt-client-name">${this.escapeHtml(apt.client_name)}</span>
                <span class="apt-time">${timeStart} — ${timeEnd}</span>
            </div>
            <div class="apt-card-details">
                ${badges}
                ${priceHtml}
            </div>
        `;

        // Клик — открыть модалку редактирования
        card.addEventListener('click', () => {
            Appointments.openEdit(apt);
        });

        return card;
    },



    // =========================================================
    //  MONTH VIEW
    // =========================================================
    async renderMonth() {
        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();

        // Заголовок
        const monthText = document.getElementById('month-date-text');
        monthText.textContent = `${this.MONTHS[month]} ${year}`;

        // Первый день месяца и последний
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const startDow = this.getDayOfWeek(firstDay);

        // Начало отображения (может быть конец предыдущего месяца)
        const calStart = new Date(firstDay);
        calStart.setDate(calStart.getDate() - startDow);

        // Загружаем данные за расширенный диапазон
        const calEnd = new Date(calStart);
        calEnd.setDate(calEnd.getDate() + 41); // 6 недель

        try {
            this.appointments = await API.getAppointments({
                date_from: this.formatDate(calStart),
                date_to: this.formatDate(calEnd),
            });
        } catch (err) {
            console.error('Failed to load month:', err);
            this.appointments = [];
        }

        // Группируем
        const aptsByDate = {};
        this.appointments.forEach(apt => {
            if (!aptsByDate[apt.date]) aptsByDate[apt.date] = [];
            aptsByDate[apt.date].push(apt);
        });

        const grid = document.getElementById('month-grid');
        grid.innerHTML = '';

        for (let i = 0; i < 42; i++) {
            const d = new Date(calStart);
            d.setDate(d.getDate() + i);
            const dateStr = this.formatDate(d);

            const cell = document.createElement('div');
            cell.className = 'month-cell';

            if (d.getMonth() !== month) cell.classList.add('other-month');
            if (this.isToday(d)) cell.classList.add('today');

            const numEl = document.createElement('div');
            numEl.className = 'month-cell-num';
            numEl.textContent = d.getDate();
            cell.appendChild(numEl);

            // Точки записей
            const dayApts = aptsByDate[dateStr] || [];
            if (dayApts.length > 0) {
                const dots = document.createElement('div');
                dots.className = 'month-cell-dots';
                const maxDots = Math.min(dayApts.length, 3);
                for (let j = 0; j < maxDots; j++) {
                    const dot = document.createElement('div');
                    dot.className = 'month-dot';
                    const color = this.TRAINING_COLORS[dayApts[j].training_type] || '#7c3aed';
                    dot.style.background = color;
                    dots.appendChild(dot);
                }
                cell.appendChild(dots);
            }

            // Клик — переключиться на день
            cell.addEventListener('click', () => {
                this.currentDate = new Date(d);
                this.switchView('day');
            });

            grid.appendChild(cell);
        }
    },

    // =========================================================
    //  NAVIGATION
    // =========================================================
    navigate(direction) {
        const d = this.currentDate;
        switch (this.currentView) {
            case 'day':
                d.setDate(d.getDate() + direction);
                this.renderDay();
                break;
            case 'month':
                d.setMonth(d.getMonth() + direction);
                this.renderMonth();
                break;
        }
        this.updateHeader();
    },

    goToToday() {
        this.currentDate = new Date();
        this.render();
    },

    switchView(view) {
        this.currentView = view;

        // Обновляем табы (снимаем active, если view 'day', так как вкладки 'day' больше нет)
        document.querySelectorAll('.tab').forEach(t => {
            t.classList.toggle('active', t.dataset.view === view);
        });

        // Показываем кнопку назад, если мы в 'day'
        const btnBack = document.getElementById('btn-back-month');
        if (btnBack) {
            btnBack.classList.toggle('hidden', view !== 'day');
        }

        // Обновляем виды
        document.querySelectorAll('.view').forEach(v => {
            v.classList.toggle('active', v.id === `view-${view}`);
        });

        this.render();
    },

    render() {
        switch (this.currentView) {
            case 'day': this.renderDay(); break;
            case 'month': this.renderMonth(); break;
            case 'clients': 
                if (window.clientsManager) window.clientsManager.loadClients();
                break;
            case 'finances': 
                if (window.financesManager) window.financesManager.loadData();
                break;
        }
        this.updateHeader();
    },

    /**
     * Инициализация обработчиков навигации.
     */
    init() {
        // Табы
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchView(tab.dataset.view));
        });

        // Навигация по дням
        document.getElementById('day-prev').addEventListener('click', () => this.navigate(-1));
        document.getElementById('day-next').addEventListener('click', () => this.navigate(1));

        // Навигация по месяцам
        document.getElementById('month-prev').addEventListener('click', () => this.navigate(-1));
        document.getElementById('month-next').addEventListener('click', () => this.navigate(1));

        // Кнопка назад к месяцу
        const btnBack = document.getElementById('btn-back-month');
        if (btnBack) {
            btnBack.addEventListener('click', () => this.switchView('month'));
        }

        // Кнопка "Сегодня"
        document.getElementById('btn-today').addEventListener('click', () => this.goToToday());
    },

    /**
     * Экранирование HTML.
     */
    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};
