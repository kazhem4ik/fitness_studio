document.addEventListener('DOMContentLoaded', async () => {
    const trainerSelect = document.getElementById('trainer-select');
    const dateInput = document.getElementById('date-select');
    const slotsContainer = document.getElementById('slots-container');
    const nameInput = document.getElementById('client-name');
    const phoneInput = document.getElementById('client-phone');
    const websiteInput = document.getElementById('client-website'); // honeypot
    const submitBtn = document.getElementById('btn-submit');
    const statusMessage = document.getElementById('status-message');

    let selectedTime = null;
    // Момент когда пользователь кликнул на слот — для honeypot-таймера
    let slotClickedAt = null;

    // ----------------------------------------------------------------
    // Session ID: уникальный идентификатор вкладки (хранится в sessionStorage)
    // Один session_id = одна активная резервация слота
    // ----------------------------------------------------------------
    let sessionId = sessionStorage.getItem('booking_sid');
    if (!sessionId) {
        sessionId = (typeof crypto !== 'undefined' && crypto.randomUUID)
            ? crypto.randomUUID()
            : Math.random().toString(36).slice(2) + Date.now().toString(36);
        sessionStorage.setItem('booking_sid', sessionId);
    }

    // Инициализация даты
    const today = new Date();
    const tzOffset = today.getTimezoneOffset() * 60000;
    const localISOTime = (new Date(Date.now() - tzOffset)).toISOString().slice(0, 10);
    dateInput.min = localISOTime;
    dateInput.value = ''; // Изначально пусто

    // Автозаполнение из localStorage
    const savedName = localStorage.getItem('saved_client_name');
    const savedPhone = localStorage.getItem('saved_client_phone');
    const savedContact = localStorage.getItem('saved_contact_method');
    
    if (savedName) nameInput.value = savedName;
    if (savedPhone) phoneInput.value = savedPhone;
    if (savedContact) {
        const contactSelect = document.getElementById('contact-method');
        if (contactSelect) contactSelect.value = savedContact;
    }

    // Загрузка тренеров
    try {
        const response = await fetch('/api/public/trainers');
        if (!response.ok) throw new Error();
        const trainers = await response.json();

        trainerSelect.innerHTML = '<option value="" disabled selected>Выберите тренера</option>' +
            trainers.map(t => `<option value="${t.id}">${t.display_name}</option>`).join('');

        if (trainers.length === 1) {
            trainerSelect.value = trainers[0].id;
            document.getElementById('date-group').style.display = 'block';
            document.getElementById('time-group').style.display = 'block';
        }
    } catch (err) {
        trainerSelect.innerHTML = '<option value="" disabled>Ошибка загрузки</option>';
    }

    // Слушатели
    trainerSelect.addEventListener('change', () => {
        document.getElementById('date-group').style.display = 'block';
        document.getElementById('time-group').style.display = 'block';
        if (dateInput.value) {
            loadSlots();
        }
    });
    
    // Используем blur вместо change, чтобы на мобильных устройствах 
    // интерфейс не прыгал при прокрутке барабана с датами
    dateInput.addEventListener('blur', loadSlots);
    // Для десктопа добавляем change с debounce, чтобы срабатывало при выборе, но не спамило
    let dateChangeTimeout;
    dateInput.addEventListener('change', () => {
        clearTimeout(dateChangeTimeout);
        dateChangeTimeout = setTimeout(() => {
            if (document.activeElement !== dateInput) {
                loadSlots();
            }
        }, 500);
    });

    if (trainerSelect.value && dateInput.value) {
        loadSlots();
    }

    // ----------------------------------------------------------------
    // Загрузка слотов (передаём session_id чтобы бэкенд не скрывал
    // наш собственный зарезервированный слот)
    // ----------------------------------------------------------------
    async function loadSlots() {
        const date = dateInput.value;
        const trainerId = trainerSelect.value;

        if (!date || !trainerId) {
            slotsContainer.innerHTML = '<div class="loading">Выберите тренера и дату</div>';
            return;
        }

        slotsContainer.innerHTML = '<div class="loading">Загрузка слотов...</div>';
        selectedTime = null;
        validateForm();

        try {
            const url = `/api/public/slots?d=${date}&trainer_id=${trainerId}&session_id=${encodeURIComponent(sessionId)}`;
            const response = await fetch(url);
            if (!response.ok) throw new Error('Ошибка сервера');
            const slots = await response.json();
            renderSlots(slots);
        } catch (err) {
            slotsContainer.innerHTML = '<div class="loading" style="color: var(--error);">Не удалось загрузить слоты</div>';
        }
    }

    // ----------------------------------------------------------------
    // Рендер кнопок слотов
    // ----------------------------------------------------------------
    function renderSlots(slots) {
        if (slots.length === 0) {
            slotsContainer.innerHTML = '<div class="loading">На этот день нет свободных мест</div>';
            return;
        }

        slotsContainer.innerHTML = '';
        slots.forEach(slot => {
            const btn = document.createElement('button');
            btn.className = 'slot-btn';
            btn.textContent = slot.time;
            if (!slot.available) {
                btn.disabled = true;
            } else {
                btn.addEventListener('click', () => selectSlot(btn, slot.time));
            }
            slotsContainer.appendChild(btn);
        });
    }

    // ----------------------------------------------------------------
    // Выбор слота: резервируем на бэкенде, запоминаем время клика
    // ----------------------------------------------------------------
    async function selectSlot(btn, time) {
        const trainerId = trainerSelect.value;
        const date = dateInput.value;

        // Визуально активируем немедленно
        document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedTime = time;
        slotClickedAt = Date.now();
        validateForm();

        // Резервируем слот на бэкенде (fire-and-forget с обработкой конфликта)
        try {
            const res = await fetch('/api/public/slots/reserve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    trainer_id: parseInt(trainerId, 10),
                    date: date,
                    time: time,
                    session_id: sessionId,
                })
            });
            const data = await res.json();
            if (!data.ok) {
                // Слот перехватили пока мы выбирали — показываем предупреждение
                document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('active'));
                selectedTime = null;
                validateForm();
                showStatus('error', data.reason || 'Этот слот только что заняли, выберите другое время');
                // Перезагружаем актуальный список слотов
                setTimeout(loadSlots, 1500);
            }
        } catch (e) {
            // Резервация не критична: если недоступна сеть — продолжаем без неё
            console.warn('Slot reservation failed (non-critical):', e);
        }
    }

    // ----------------------------------------------------------------
    // Маска телефона
    // ----------------------------------------------------------------
    phoneInput.addEventListener('input', function() {
        let val = this.value.replace(/\D/g, '');
        if (val.length === 0) { this.value = ''; validateForm(); return; }
        if (val[0] === '8') val = '7' + val.substring(1);
        if (val[0] !== '7') val = '7' + val;

        let formatted = '+7';
        if (val.length > 1) formatted += ' (' + val.substring(1, 4);
        if (val.length >= 5) formatted += ') ' + val.substring(4, 7);
        if (val.length >= 8) formatted += '-' + val.substring(7, 9);
        if (val.length >= 10) formatted += '-' + val.substring(9, 11);

        this.value = formatted;
        validateForm();
    });

    nameInput.addEventListener('input', validateForm);

    function validateForm() {
        const phoneRaw = phoneInput.value.replace(/\D/g, '');
        const isPhoneValid = phoneRaw.length === 11;
        const isNameValid = nameInput.value.trim().length >= 2;
        const isTrainerSelected = !!trainerSelect.value;
        const contactMethod = document.getElementById('contact-method').value;
        const isContactMethodValid = contactMethod !== '';
        submitBtn.disabled = !(selectedTime && isPhoneValid && isNameValid && isTrainerSelected && isContactMethodValid);
    }
    
    document.getElementById('contact-method').addEventListener('change', validateForm);

    // ----------------------------------------------------------------
    // Отправка формы
    // ----------------------------------------------------------------
    submitBtn.addEventListener('click', async () => {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Отправка...';
        clearStatus();

        // Honeypot защита на фронте:
        // Если поле заполнено, но прошло < 200мс с момента клика на слот
        // (или вообще нет timestamp) — скорее всего автозаполнение браузера.
        // Очищаем поле, чтобы не заблокировать реального пользователя.
        let honeypotValue = websiteInput ? websiteInput.value : '';
        if (honeypotValue && slotClickedAt) {
            const elapsed = Date.now() - slotClickedAt;
            if (elapsed < 200) {
                // Автозаполнение — тихо очищаем
                honeypotValue = '';
            }
        }

        try {
            const contactMethod = document.getElementById('contact-method').value;
            const response = await fetch('/api/public/book', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    date: dateInput.value,
                    time: selectedTime,
                    client_name: nameInput.value.trim(),
                    client_phone: '+' + phoneInput.value.replace(/\D/g, ''),
                    trainer_id: parseInt(trainerSelect.value, 10),
                    website: honeypotValue,
                    session_id: sessionId,
                    contact_method: contactMethod
                })
            });

            const data = await response.json();

            if (response.ok) {
                // Сохраняем данные для автозаполнения в следующий раз
                localStorage.setItem('saved_client_name', nameInput.value.trim());
                localStorage.setItem('saved_client_phone', phoneInput.value);
                localStorage.setItem('saved_contact_method', contactMethod);

                // Форматируем дату
                const [yyyy, mm, dd] = dateInput.value.split('-');
                const formattedDate = `${dd}.${mm}.${yyyy}`;
                
                document.getElementById('success-details').innerHTML = 
                    `Вы записаны на <strong style="color: var(--primary);">${formattedDate}</strong> в <strong style="color: var(--primary);">${selectedTime}</strong>`;
                
                document.getElementById('booking-form-container').style.display = 'none';
                document.getElementById('success-container').style.display = 'block';
                window.scrollTo(0, 0);

                // Очищаем session_id чтобы следующее открытие страницы начало новую сессию
                sessionStorage.removeItem('booking_sid');
            } else {
                throw new Error(data.detail || 'Ошибка при записи');
            }

        } catch (err) {
            showStatus('error', err.message);
            submitBtn.disabled = false;
            submitBtn.textContent = 'Записаться';
        }
    });

    // ----------------------------------------------------------------
    // Утилиты
    // ----------------------------------------------------------------
    function showStatus(type, text) {
        statusMessage.className = 'message ' + type;
        statusMessage.textContent = text;
    }

    function clearStatus() {
        statusMessage.className = 'message';
        statusMessage.textContent = '';
    }
});
