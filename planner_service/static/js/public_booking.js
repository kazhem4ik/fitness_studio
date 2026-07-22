document.addEventListener('DOMContentLoaded', () => {
    const dateInput = document.getElementById('date-select');
    const slotsContainer = document.getElementById('slots-container');
    const nameInput = document.getElementById('client-name');
    const phoneInput = document.getElementById('client-phone');
    const submitBtn = document.getElementById('btn-submit');
    const statusMessage = document.getElementById('status-message');
    
    let selectedTime = null;

    // Инициализация даты
    const today = new Date();
    const tzOffset = today.getTimezoneOffset() * 60000;
    const localISOTime = (new Date(Date.now() - tzOffset)).toISOString().slice(0, 10);
    dateInput.min = localISOTime;
    dateInput.value = localISOTime;

    // Загрузка слотов при смене даты
    dateInput.addEventListener('change', loadSlots);
    loadSlots(); // первичная загрузка

    async function loadSlots() {
        const date = dateInput.value;
        if (!date) return;
        
        slotsContainer.innerHTML = '<div class="loading">Загрузка слотов...</div>';
        selectedTime = null;
        validateForm();

        try {
            const response = await fetch(`/api/public/slots?d=${date}`);
            if (!response.ok) throw new Error('Ошибка сервера');
            const slots = await response.json();
            
            renderSlots(slots);
        } catch (err) {
            slotsContainer.innerHTML = '<div class="loading" style="color: var(--error);">Не удалось загрузить слоты</div>';
        }
    }

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
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    selectedTime = slot.time;
                    validateForm();
                });
            }
            slotsContainer.appendChild(btn);
        });
    }

    // Маска телефона (автоформат +7)
    phoneInput.addEventListener('input', function(e) {
        let val = this.value.replace(/\D/g, '');
        if (val.length === 0) {
            this.value = '';
            validateForm();
            return;
        }
        
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
        
        submitBtn.disabled = !(selectedTime && isPhoneValid && isNameValid);
    }

    // Отправка формы
    submitBtn.addEventListener('click', async () => {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Отправка...';
        statusMessage.className = 'message';
        statusMessage.textContent = '';

        try {
            const response = await fetch('/api/public/book', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    date: dateInput.value,
                    time: selectedTime,
                    client_name: nameInput.value.trim(),
                    client_phone: '+' + phoneInput.value.replace(/\D/g, '')
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Ошибка при записи');
            }

            // Успех
            document.getElementById('booking-form-container').style.display = 'none';
            document.getElementById('success-container').style.display = 'block';

        } catch (err) {
            statusMessage.className = 'message error';
            statusMessage.textContent = err.message;
            submitBtn.disabled = false;
            submitBtn.textContent = 'Записаться';
        }
    });
});
