const ScheduleUI = {
    weekdays: ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
    weekdayShort: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
    schedule: null,
    exceptions: [],
    trainerId: null,
    initialized: false,
    calendarStart: null,
    calendarEnd: null,
    calendarMonth: null,
    selectedDate: null,

    init() {
        if (this.initialized) return;
        this.initialized = true;

        document.getElementById('schedule-save').addEventListener('click', () => this.saveSchedule());
        document.getElementById('schedule-add-exception').addEventListener('click', () => this.showExceptionForm());
        document.getElementById('schedule-cancel-exception').addEventListener('click', () => this.hideExceptionForm());
        document.getElementById('schedule-exception-type').addEventListener('change', event => {
            this.toggleExceptionHours(event.target.value === 'custom');
        });
        document.getElementById('schedule-exception-form').addEventListener('submit', event => {
            event.preventDefault();
            this.saveException();
        });
        document.getElementById('schedule-calendar-prev').addEventListener('click', () => this.changeCalendarMonth(-1));
        document.getElementById('schedule-calendar-next').addEventListener('click', () => this.changeCalendarMonth(1));
        document.getElementById('schedule-calendar-current').addEventListener('click', () => {
            this.calendarMonth = this.firstDayOfMonth(this.calendarStart);
            this.renderCalendar();
        });
        document.getElementById('schedule-trainer-select').addEventListener('change', event => {
            this.trainerId = Number(event.target.value);
            this.loadData();
        });

        document.getElementById('schedule-weekly-list').addEventListener('click', event => {
            const action = event.target.closest('[data-schedule-action]')?.dataset.scheduleAction;
            if (!action) return;
            const plan = event.target.closest('.schedule-day-plan');
            if (action === 'add-break') this.addSuggestedBreak(plan);
            if (action === 'remove-break') event.target.closest('.schedule-break-row').remove();
        });
        document.getElementById('schedule-weekly-list').addEventListener('change', event => {
            if (!event.target.classList.contains('schedule-day-enabled')) return;
            const day = event.target.closest('.schedule-day');
            day.querySelector('.schedule-day-body').classList.toggle('hidden', !event.target.checked);
            day.querySelector('.schedule-day-status').textContent = event.target.checked ? 'Рабочий день' : 'Выходной';
        });

        document.getElementById('schedule-exception-day-plan').addEventListener('click', event => {
            const action = event.target.closest('[data-schedule-action]')?.dataset.scheduleAction;
            const plan = event.target.closest('.schedule-day-plan');
            if (action === 'add-break') this.addSuggestedBreak(plan);
            if (action === 'remove-break') event.target.closest('.schedule-break-row').remove();
        });
        document.getElementById('schedule-date-calendar').addEventListener('click', event => {
            const button = event.target.closest('.schedule-calendar-day[data-date]');
            if (button) this.showExceptionForm(button.dataset.date);
        });
        document.getElementById('schedule-exceptions-list').addEventListener('click', event => {
            const button = event.target.closest('.schedule-delete-exception');
            if (button) this.deleteException(button.dataset.start, button.dataset.end, false);
        });
    },

    async open() {
        this.init();
        if (Auth.currentUser.role === 'admin') {
            await this.loadTrainerOptions();
        } else {
            document.getElementById('schedule-trainer-group').classList.add('hidden');
            this.trainerId = null;
        }
        await this.loadData();
    },

    async loadTrainerOptions() {
        const group = document.getElementById('schedule-trainer-group');
        const select = document.getElementById('schedule-trainer-select');
        const users = await API.admin.getTrainers();
        const trainers = users.filter(user => user.role === 'trainer' && user.is_active);
        group.classList.remove('hidden');
        select.innerHTML = '';
        trainers.forEach(trainer => {
            const option = document.createElement('option');
            option.value = trainer.id;
            option.textContent = trainer.display_name;
            select.appendChild(option);
        });
        if (!trainers.length) {
            this.trainerId = null;
            throw new Error('Нет активных тренеров');
        }
        if (!this.trainerId || !trainers.some(item => item.id === this.trainerId)) {
            this.trainerId = trainers[0].id;
        }
        select.value = String(this.trainerId);
    },

    setCalendarRange() {
        const start = new Date();
        start.setHours(12, 0, 0, 0);
        const end = new Date(start);
        end.setMonth(end.getMonth() + 3);
        end.setDate(end.getDate() - 1);
        this.calendarStart = this.localISO(start);
        this.calendarEnd = this.localISO(end);
        const firstAllowedMonth = this.firstDayOfMonth(this.calendarStart);
        const lastAllowedMonth = this.firstDayOfMonth(this.calendarEnd);
        if (!this.calendarMonth || this.calendarMonth < firstAllowedMonth || this.calendarMonth > lastAllowedMonth) {
            this.calendarMonth = firstAllowedMonth;
        }
    },

    async loadData() {
        try {
            this.setCalendarRange();
            [this.schedule, this.exceptions] = await Promise.all([
                API.schedule.get(this.trainerId),
                API.schedule.getExceptions(this.calendarStart, this.calendarEnd, this.trainerId),
            ]);
            this.renderSchedule();
            this.renderCalendar();
            this.renderExceptions();
        } catch (error) {
            showToast('Ошибка загрузки графика: ' + error.message);
        }
    },

    renderSchedule() {
        document.getElementById('schedule-duration').value = this.schedule.duration_minutes;
        document.getElementById('schedule-booking-horizon').value = this.schedule.booking_horizon_days;
        const container = document.getElementById('schedule-weekly-list');
        container.innerHTML = '';

        this.schedule.weekly.forEach(day => {
            const enabled = day.intervals.length > 0;
            const element = document.createElement('section');
            element.className = 'schedule-day';
            element.dataset.weekday = day.weekday;
            element.innerHTML = `
                <div class="schedule-day-header">
                    <label class="check-label">
                        <input class="schedule-day-enabled" type="checkbox" ${enabled ? 'checked' : ''}>
                        <span class="checkmark"></span>
                        <strong>${this.weekdays[day.weekday]}</strong>
                    </label>
                    <span class="schedule-day-status">${enabled ? 'Рабочий день' : 'Выходной'}</span>
                </div>
                <div class="schedule-day-body ${enabled ? '' : 'hidden'}">
                    <div class="schedule-day-plan"></div>
                </div>`;
            container.appendChild(element);
            this.renderDayPlan(
                element.querySelector('.schedule-day-plan'),
                enabled ? this.intervalsToPlan(day.intervals) : { start: '09:00', end: '19:00', breaks: [] },
            );
        });
    },

    renderDayPlan(container, plan) {
        container.innerHTML = `
            <div class="schedule-shift-row">
                <label><span>Начало дня</span><input class="schedule-shift-start" type="time" step="1800" value="${plan.start}" required></label>
                <span class="schedule-time-separator">—</span>
                <label><span>Конец дня</span><input class="schedule-shift-end" type="time" step="1800" value="${plan.end}" required></label>
            </div>
            <div class="schedule-breaks"></div>
            <button type="button" class="btn btn-outline btn-small schedule-add-break" data-schedule-action="add-break">+ Добавить перерыв</button>`;
        const breaks = container.querySelector('.schedule-breaks');
        plan.breaks.forEach(item => this.addBreakRow(breaks, item.start, item.end));
    },

    addBreakRow(container, start, end) {
        const row = document.createElement('div');
        row.className = 'schedule-break-row';
        row.innerHTML = `
            <span class="schedule-break-label">Перерыв</span>
            <input class="schedule-break-start" type="time" step="1800" value="${start}" required>
            <span>—</span>
            <input class="schedule-break-end" type="time" step="1800" value="${end}" required>
            <button type="button" class="btn-icon" data-schedule-action="remove-break" title="Удалить перерыв">×</button>`;
        container.appendChild(row);
    },

    addSuggestedBreak(plan) {
        if (!plan) return;
        const start = plan.querySelector('.schedule-shift-start').value || '09:00';
        const end = plan.querySelector('.schedule-shift-end').value || '19:00';
        const startMinutes = this.timeToMinutes(start);
        const endMinutes = this.timeToMinutes(end);
        let breakStart = Math.floor(((startMinutes + endMinutes) / 2) / 30) * 30;
        let breakEnd = breakStart + 60;
        if (breakEnd >= endMinutes) {
            breakEnd = endMinutes - 30;
            breakStart = breakEnd - 30;
        }
        if (breakStart <= startMinutes || breakEnd >= endMinutes) {
            showToast('Рабочий день слишком короткий для перерыва');
            return;
        }
        this.addBreakRow(
            plan.querySelector('.schedule-breaks'),
            this.minutesToTime(breakStart),
            this.minutesToTime(breakEnd),
        );
    },

    intervalsToPlan(intervals) {
        if (!intervals.length) return { start: '09:00', end: '19:00', breaks: [] };
        const breaks = [];
        for (let index = 0; index < intervals.length - 1; index += 1) {
            if (intervals[index].end !== intervals[index + 1].start) {
                breaks.push({ start: intervals[index].end, end: intervals[index + 1].start });
            }
        }
        return {
            start: intervals[0].start,
            end: intervals[intervals.length - 1].end,
            breaks,
        };
    },

    collectDayPlan(container) {
        const shiftStart = container.querySelector('.schedule-shift-start').value;
        const shiftEnd = container.querySelector('.schedule-shift-end').value;
        if (!shiftStart || !shiftEnd || shiftStart >= shiftEnd) {
            throw new Error('Начало рабочего дня должно быть раньше окончания');
        }

        const breaks = [...container.querySelectorAll('.schedule-break-row')]
            .map(row => ({
                start: row.querySelector('.schedule-break-start').value,
                end: row.querySelector('.schedule-break-end').value,
            }))
            .sort((left, right) => left.start.localeCompare(right.start));

        let cursor = shiftStart;
        const intervals = [];
        breaks.forEach(item => {
            if (!item.start || !item.end || item.start >= item.end) {
                throw new Error('Проверьте начало и конец перерыва');
            }
            if (item.start <= shiftStart || item.end >= shiftEnd) {
                throw new Error('Перерыв должен находиться внутри рабочего дня');
            }
            if (item.start < cursor) {
                throw new Error('Перерывы не должны пересекаться');
            }
            if (cursor < item.start) intervals.push({ start: cursor, end: item.start });
            cursor = item.end;
        });
        if (cursor < shiftEnd) intervals.push({ start: cursor, end: shiftEnd });
        return intervals;
    },

    collectWeekly() {
        return [...document.querySelectorAll('.schedule-day')].map(day => ({
            weekday: Number(day.dataset.weekday),
            intervals: day.querySelector('.schedule-day-enabled').checked
                ? this.collectDayPlan(day.querySelector('.schedule-day-plan'))
                : [],
        }));
    },

    async saveSchedule(confirmConflicts = false) {
        try {
            const payload = {
                duration_minutes: Number(document.getElementById('schedule-duration').value),
                booking_horizon_days: Number(document.getElementById('schedule-booking-horizon').value),
                weekly: this.collectWeekly(),
                confirm_conflicts: confirmConflicts,
            };
            const result = await API.schedule.save(payload, this.trainerId);
            if (result.requires_confirmation) {
                if (window.confirm(this.conflictMessage(result.conflicts))) await this.saveSchedule(true);
                return;
            }
            this.schedule = result.schedule;
            this.renderSchedule();
            this.renderCalendar();
            showToast('Настройки и обычный график сохранены');
        } catch (error) {
            showToast('Не удалось сохранить график: ' + error.message);
        }
    },

    showExceptionForm(selectedDate = null, selectedEndDate = null) {
        const form = document.getElementById('schedule-exception-form');
        const targetDate = selectedDate || this.calendarStart || this.localISO(new Date());
        this.selectedDate = targetDate;
        this.calendarMonth = this.firstDayOfMonth(targetDate);
        this.renderCalendar();
        const existing = this.exceptions.find(item => item.date === targetDate);
        document.getElementById('schedule-exception-start').value = targetDate;
        document.getElementById('schedule-exception-end').value = selectedEndDate || targetDate;
        document.getElementById('schedule-exception-start').min = this.calendarStart;
        document.getElementById('schedule-exception-end').min = this.calendarStart;
        document.getElementById('schedule-exception-start').max = this.calendarEnd;
        document.getElementById('schedule-exception-end').max = this.calendarEnd;
        document.getElementById('schedule-exception-title').textContent = selectedDate
            ? (selectedEndDate && selectedEndDate !== targetDate
                ? `${this.formatDate(targetDate)} — ${this.formatDate(selectedEndDate)}`
                : this.formatLongDate(targetDate))
            : 'Настроить диапазон дат';

        const type = existing ? (existing.is_day_off ? 'day_off' : 'custom') : (selectedDate ? 'base' : 'day_off');
        document.getElementById('schedule-exception-type').value = type;
        if (type === 'custom') {
            this.renderDayPlan(
                document.getElementById('schedule-exception-day-plan'),
                this.intervalsToPlan(existing.intervals),
            );
        } else {
            const effective = this.effectiveIntervals(targetDate);
            this.renderDayPlan(
                document.getElementById('schedule-exception-day-plan'),
                this.intervalsToPlan(effective.length ? effective : [{ start: '09:00', end: '19:00' }]),
            );
        }
        this.toggleExceptionHours(type === 'custom');
        form.classList.remove('hidden');
        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    },

    hideExceptionForm() {
        document.getElementById('schedule-exception-form').classList.add('hidden');
    },

    toggleExceptionHours(visible) {
        document.getElementById('schedule-exception-hours').classList.toggle('hidden', !visible);
    },

    async saveException(confirmConflicts = false) {
        const type = document.getElementById('schedule-exception-type').value;
        const startDate = document.getElementById('schedule-exception-start').value;
        const endDate = document.getElementById('schedule-exception-end').value;
        try {
            let result;
            if (type === 'base') {
                result = await API.schedule.deleteExceptions(startDate, endDate, confirmConflicts, this.trainerId);
            } else {
                result = await API.schedule.saveException({
                    start_date: startDate,
                    end_date: endDate,
                    is_day_off: type === 'day_off',
                    intervals: type === 'custom'
                        ? this.collectDayPlan(document.getElementById('schedule-exception-day-plan'))
                        : [],
                    confirm_conflicts: confirmConflicts,
                }, this.trainerId);
            }
            if (result.requires_confirmation) {
                if (window.confirm(this.conflictMessage(result.conflicts))) await this.saveException(true);
                return;
            }
            this.hideExceptionForm();
            await this.loadData();
            showToast(type === 'base' ? 'Возвращён обычный график' : 'Расписание по датам сохранено');
        } catch (error) {
            showToast('Не удалось сохранить расписание: ' + error.message);
        }
    },

    exceptionMap() {
        return new Map(this.exceptions.map(item => [item.date, item]));
    },

    effectiveIntervals(dateValue) {
        const override = this.exceptionMap().get(dateValue);
        if (override) return override.is_day_off ? [] : override.intervals;
        const dateObject = new Date(dateValue + 'T12:00:00');
        const weekday = (dateObject.getDay() + 6) % 7;
        return this.schedule.weekly.find(day => day.weekday === weekday)?.intervals || [];
    },

    renderCalendar() {
        const container = document.getElementById('schedule-date-calendar');
        container.innerHTML = '';
        const start = new Date(this.calendarStart + 'T12:00:00');
        const end = new Date(this.calendarEnd + 'T12:00:00');
        const overrides = this.exceptionMap();
        const month = new Date(this.calendarMonth + 'T12:00:00');
        const firstAllowedMonth = this.firstDayOfMonth(this.calendarStart);
        const lastAllowedMonth = this.firstDayOfMonth(this.calendarEnd);
        const previousButton = document.getElementById('schedule-calendar-prev');
        const nextButton = document.getElementById('schedule-calendar-next');
        previousButton.disabled = this.calendarMonth <= firstAllowedMonth;
        nextButton.disabled = this.calendarMonth >= lastAllowedMonth;

        document.getElementById('schedule-calendar-month-title').textContent = month.toLocaleDateString('ru-RU', {
            month: 'long',
            year: 'numeric',
        });
        const currentHint = document.querySelector('#schedule-calendar-current span');
        currentHint.textContent = this.calendarMonth === firstAllowedMonth
            ? 'Текущий месяц'
            : 'Вернуться к текущему месяцу';

        const firstWeekday = (month.getDay() + 6) % 7;
        for (let index = 0; index < firstWeekday; index += 1) {
            const empty = document.createElement('span');
            empty.className = 'schedule-calendar-empty';
            container.appendChild(empty);
        }

        const nextMonth = new Date(month.getFullYear(), month.getMonth() + 1, 1, 12);
        for (let current = new Date(month); current < nextMonth; current.setDate(current.getDate() + 1)) {
            const iso = this.localISO(current);
            const allowed = current >= start && current <= end;
            const override = allowed ? overrides.get(iso) : null;
            const intervals = allowed ? this.effectiveIntervals(iso) : [];
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'schedule-calendar-day';
            button.dataset.date = iso;
            button.disabled = !allowed;

            if (!allowed) button.classList.add('is-unavailable');
            else if (override?.is_day_off) button.classList.add('is-off');
            else if (override) button.classList.add('is-custom');
            else button.classList.add('is-base');
            if (iso === this.calendarStart) button.classList.add('is-today');
            if (iso === this.selectedDate) button.classList.add('is-selected');

            let label = 'Недоступно';
            if (allowed && !intervals.length) label = 'Выходной';
            if (allowed && intervals.length) {
                const plan = this.intervalsToPlan(intervals);
                label = `${this.shortTime(plan.start)}–${this.shortTime(plan.end)}`;
            }
            button.innerHTML = `
                <span class="schedule-calendar-day-number">${current.getDate()}</span>
                <small>${label}</small>
                ${override ? `<i>${override.is_day_off ? 'выходной' : 'изменено'}</i>` : ''}`;
            button.title = allowed
                ? `${this.formatLongDate(iso)}: ${this.intervalsDescription(intervals)}`
                : 'Эта дата недоступна для планирования';
            container.appendChild(button);
        }
    },

    changeCalendarMonth(offset) {
        const current = new Date(this.calendarMonth + 'T12:00:00');
        current.setMonth(current.getMonth() + offset);
        const nextValue = this.localISO(current);
        const firstAllowedMonth = this.firstDayOfMonth(this.calendarStart);
        const lastAllowedMonth = this.firstDayOfMonth(this.calendarEnd);
        if (nextValue < firstAllowedMonth || nextValue > lastAllowedMonth) return;
        this.calendarMonth = nextValue;
        this.renderCalendar();
    },

    firstDayOfMonth(value) {
        const date = new Date(value + 'T12:00:00');
        return this.localISO(new Date(date.getFullYear(), date.getMonth(), 1, 12));
    },

    shortTime(value) {
        return value.endsWith(':00') ? value.slice(0, 2) : value;
    },

    groupExceptions() {
        const groups = [];
        this.exceptions.forEach(item => {
            const signature = JSON.stringify({ dayOff: item.is_day_off, intervals: item.intervals });
            const previous = groups[groups.length - 1];
            const previousNextDate = previous ? new Date(previous.end + 'T12:00:00') : null;
            if (previousNextDate) previousNextDate.setDate(previousNextDate.getDate() + 1);
            if (previous && previous.signature === signature && this.localISO(previousNextDate) === item.date) {
                previous.end = item.date;
            } else {
                groups.push({ start: item.date, end: item.date, signature, item });
            }
        });
        return groups;
    },

    renderExceptions() {
        const container = document.getElementById('schedule-exceptions-list');
        const groups = this.groupExceptions();
        if (!groups.length) {
            container.innerHTML = '<p class="schedule-empty">Изменений на ближайшие три месяца пока нет.</p>';
            return;
        }
        container.innerHTML = '';
        groups.forEach(group => {
            const item = group.item;
            const row = document.createElement('div');
            row.className = 'schedule-exception-row';
            const range = group.start === group.end
                ? this.formatLongDate(group.start)
                : `${this.formatDate(group.start)} — ${this.formatDate(group.end)}`;
            const description = item.is_day_off ? 'Выходной / отпуск' : this.intervalsDescription(item.intervals);
            row.innerHTML = `
                <button type="button" class="schedule-exception-edit" data-date="${group.start}">
                    <strong>${range}</strong><span>${description}</span>
                </button>
                <button type="button" class="btn-icon schedule-delete-exception" data-start="${group.start}" data-end="${group.end}" title="Вернуть обычный график">×</button>`;
            row.querySelector('.schedule-exception-edit').addEventListener('click', () => {
                this.showExceptionForm(group.start, group.end);
            });
            container.appendChild(row);
        });
    },

    async deleteException(startDate, endDate, confirmConflicts) {
        if (!confirmConflicts && !window.confirm('Вернуть для этих дат обычный график?')) return;
        try {
            const result = await API.schedule.deleteExceptions(startDate, endDate, confirmConflicts, this.trainerId);
            if (result.requires_confirmation) {
                if (window.confirm(this.conflictMessage(result.conflicts))) {
                    await this.deleteException(startDate, endDate, true);
                }
                return;
            }
            await this.loadData();
            showToast('Возвращён обычный график');
        } catch (error) {
            showToast('Не удалось изменить расписание: ' + error.message);
        }
    },

    intervalsDescription(intervals) {
        if (!intervals.length) return 'Выходной';
        const plan = this.intervalsToPlan(intervals);
        const breaks = plan.breaks.length
            ? ` · перерыв ${plan.breaks.map(item => `${item.start}–${item.end}`).join(', ')}`
            : ' · без перерыва';
        return `${plan.start}–${plan.end}${breaks}`;
    },

    conflictMessage(conflicts) {
        const lines = conflicts.slice(0, 10).map(item =>
            `${this.formatDate(item.date)} ${item.time_start} — ${item.client_name}`
        );
        const rest = conflicts.length > 10 ? `\nИ ещё: ${conflicts.length - 10}` : '';
        return `Новый график пересекается с существующими записями:\n\n${lines.join('\n')}${rest}\n\nЗаписи останутся на месте. Всё равно сохранить?`;
    },

    timeToMinutes(value) {
        const [hours, minutes] = value.split(':').map(Number);
        return hours * 60 + minutes;
    },

    minutesToTime(value) {
        const hours = Math.floor(value / 60).toString().padStart(2, '0');
        const minutes = (value % 60).toString().padStart(2, '0');
        return `${hours}:${minutes}`;
    },

    localISO(value) {
        const date = value instanceof Date ? value : new Date(value);
        const offset = date.getTimezoneOffset() * 60000;
        return new Date(date.getTime() - offset).toISOString().slice(0, 10);
    },

    formatDate(value) {
        return new Date(value + 'T12:00:00').toLocaleDateString('ru-RU');
    },

    formatLongDate(value) {
        return new Date(value + 'T12:00:00').toLocaleDateString('ru-RU', {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
        });
    },
};

window.ScheduleUI = ScheduleUI;
