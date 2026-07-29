import re

# 1. Update calendar.js
with open('planner_service/static/js/calendar.js', 'r', encoding='utf-8') as f:
    content = f.read()

old_calendar = """        if (apt.training_type) {
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
        `;"""

new_calendar = """        if (apt.training_type) {
            badges += `<span class="apt-badge training-type" style="background:${color}20;color:${color}">${apt.training_type}</span>`;
        }

        card.innerHTML = `
            <div class="apt-card-header">
                <span class="apt-client-name">${this.escapeHtml(apt.client_name)}</span>
                <span class="apt-time">${timeStart} — ${timeEnd}</span>
            </div>
            <div class="apt-card-details">
                ${badges}
            </div>
        `;"""

content = content.replace(old_calendar, new_calendar)

with open('planner_service/static/js/calendar.js', 'w', encoding='utf-8') as f:
    f.write(content)


# 2. Update clients.js
with open('planner_service/static/js/clients.js', 'r', encoding='utf-8') as f:
    content = f.read()
    
old_clients = """<div style="font-size: 12px; color: var(--text-secondary);">${item.training_type || 'Тренировка'}${item.price != null ? ' &bull; ' + item.price + ' ₽' : ''}${item.is_paid ? ' (Оплачено)' : ''}</div>"""
new_clients = """<div style="font-size: 12px; color: var(--text-secondary);">${item.training_type || 'Тренировка'}</div>"""

content = content.replace(old_clients, new_clients)

with open('planner_service/static/js/clients.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("Removed price and is_paid from JS rendering!")
