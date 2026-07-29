/**
 * Управление клиентами и абонементами
 */

class ClientsManager {
    constructor() {
        this.listContainer = document.getElementById('clients-list');
        this.searchInput = document.getElementById('clients-search');
        this.btnAddClient = document.getElementById('btn-add-client');
        this.clients = [];
        this.isTrashMode = false;
        
        this.initEventListeners();
    }

    initEventListeners() {
        if (this.searchInput) {
            this.searchInput.addEventListener('input', (e) => {
                this.renderList(e.target.value);
            });
        }

        if (this.btnAddClient) {
            this.btnAddClient.addEventListener('click', () => {
                this.showClientModal();
            });
        }
        
        const trashBtn = document.getElementById('btn-clients-trash');
        if (trashBtn) {
            trashBtn.addEventListener('click', () => {
                this.isTrashMode = !this.isTrashMode;
                trashBtn.style.color = this.isTrashMode ? 'var(--primary)' : 'var(--text-secondary)';
                
                const btnAdd = document.getElementById('btn-add-client');
                const btnEmpty = document.getElementById('btn-empty-trash');
                if (this.isTrashMode) {
                    if (btnAdd) btnAdd.classList.add('hidden');
                    if (btnEmpty) btnEmpty.classList.remove('hidden');
                } else {
                    if (btnAdd) btnAdd.classList.remove('hidden');
                    if (btnEmpty) btnEmpty.classList.add('hidden');
                }
                this.loadClients();
            });
        }

        const emptyBtn = document.getElementById('btn-empty-trash');
        if (emptyBtn) {
            emptyBtn.addEventListener('click', async () => {
                if (confirm('Вы уверены, что хотите НАВСЕГДА удалить всех клиентов из корзины? Это действие необратимо.')) {
                    try {
                        await API.request('DELETE', '/clients/trash/empty');
                        this.loadClients();
                        if (window.showToast) window.showToast('Корзина очищена');
                    } catch (e) {
                        alert('Ошибка очистки корзины');
                    }
                }
            });
        }

        const modalCloseBtn = document.getElementById('client-modal-close');
        if (modalCloseBtn) {
            modalCloseBtn.addEventListener('click', () => this.closeClientModal());
        }

        const clientForm = document.getElementById('client-form');
        if (clientForm) {
            clientForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveClient();
            });
        }
        
        const btnDeleteClient = document.getElementById('btn-delete-client');
        if (btnDeleteClient) {
            btnDeleteClient.addEventListener('click', async () => {
                if (this.editingClientId) {
                    if (confirm('Вы уверены? Клиент и все его данные отправятся в корзину.')) {
                        try {
                            await API.request('DELETE', '/clients/' + this.editingClientId);
                            this.closeClientModal();
                            this.loadClients();
                            if (window.showToast) window.showToast('Клиент удален в корзину');
                        } catch (e) {
                            alert('Ошибка удаления клиента');
                        }
                    }
                }
            });
        }

        const phoneInput = document.getElementById('client-phone');
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
    }

    async loadClients() {
        try {
            const endpoint = this.isTrashMode ? '/clients?deleted=true' : '/clients';
            const data = await API.request('GET', endpoint);
            this.clients = data;
            this.renderList();
        } catch (error) {
            console.error('Ошибка загрузки клиентов:', error);
            alert('Не удалось загрузить список клиентов');
        }
    }

    renderList(searchQuery = '') {
        if (!this.listContainer) return;
        this.listContainer.innerHTML = '';

        const query = searchQuery.toLowerCase();
        const filtered = this.clients.filter(c => 
            c.full_name.toLowerCase().includes(query) || 
            (c.phone && c.phone.includes(query))
        );

        if (filtered.length === 0) {
            this.listContainer.innerHTML = '<div class="empty-state">Клиенты не найдены</div>';
            return;
        }

        filtered.forEach(client => {
            const card = document.createElement('div');
            card.className = 'client-card';
            
            // Красный/зеленый индикатор баланса
            const balanceClass = client.sessions_balance > 0 ? 'balance-positive' : 'balance-empty';
            
            card.innerHTML = `
                <div class="client-info">
                    <h3 class="client-name">${client.full_name}</h3>
                    <p class="client-phone">${client.phone || 'Нет номера'}</p>
                </div>
                <div class="client-balance">
                    <span class="balance-badge ${balanceClass}">
                        ${client.sessions_balance} занятий
                    </span>
                </div>
            `;
            
            if (this.isTrashMode) {
                card.style.opacity = '0.7';
                card.innerHTML += `<div style="margin-top: 8px; text-align: center;"><button class="btn-outline btn-small" style="width: 100%; border-color: var(--primary); color: var(--primary);" onclick="event.stopPropagation(); window.clientsManager.restoreClient(${client.id})">Восстановить</button></div>`;
            } else {
                card.addEventListener('click', () => this.showClientDetails(client.id));
            }
            this.listContainer.appendChild(card);
        });
    }

    showClientModal(client = null) {
        this.editingClientId = client ? client.id : null;
        document.getElementById('client-modal-title').textContent = client ? 'Редактировать клиента' : 'Новый клиент';
        
        document.getElementById('client-name').value = client ? client.full_name : '';
        document.getElementById('client-phone').value = client ? (client.phone || '') : '';
        document.getElementById('client-notes').value = client ? (client.notes || '') : '';
        
        const btnDelete = document.getElementById('btn-delete-client');
        if (btnDelete) {
            if (client) {
                btnDelete.classList.remove('hidden');
            } else {
                btnDelete.classList.add('hidden');
            }
        }
        
        document.getElementById('client-modal').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    closeClientModal() {
        const modal = document.getElementById('client-modal');
        const sheet = modal.querySelector('.modal-sheet');

        sheet.style.animation = 'none';
        sheet.offsetHeight; // reflow
        sheet.style.animation = 'slideDown 0.25s var(--ease-out) forwards';

        setTimeout(() => {
            modal.classList.add('hidden');
            sheet.style.animation = '';
            document.body.style.overflow = '';
        }, 250);
    }

    async restoreClient(clientId) {
        if (confirm('Восстановить этого клиента и все его данные?')) {
            try {
                await API.request('POST', '/clients/' + clientId + '/restore');
                this.loadClients();
                if (window.showToast) window.showToast('Клиент восстановлен');
            } catch (e) {
                alert('Ошибка восстановления клиента');
            }
        }
    }

    async saveClient() {
        const name = document.getElementById('client-name').value.trim();
        const phone = document.getElementById('client-phone').value.trim();
        const notes = document.getElementById('client-notes').value.trim();

        if (!name) return;

        try {
            if (this.editingClientId) {
                await API.updateClient(this.editingClientId, { full_name: name, phone: phone, notes: notes });
            } else {
                await API.createClient({ full_name: name, phone: phone, notes: notes });
            }
            this.closeClientModal();
            this.loadClients();
        } catch (e) {
            if (e.message) {
                alert(e.message);
            } else {
                alert("Ошибка сохранения клиента");
            }
        }
    }

    async showClientDetails(clientId) {
        try {
            const details = await API.getClientDetails(clientId);
            
            document.getElementById('cd-name').textContent = details.full_name;
            document.getElementById('cd-phone').textContent = details.phone || 'Нет номера';
            document.getElementById('cd-notes').textContent = details.notes || '';
            document.getElementById('cd-balance').textContent = details.sessions_balance || 0;
            
            const modal = document.getElementById('client-details-modal');
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
            
            // Загрузка истории
            const historyContainer = document.getElementById('cd-history');
            if (historyContainer) {
                historyContainer.innerHTML = '<div style="color: var(--text-secondary); font-size: 14px;">Загрузка...</div>';
                API.getClientAppointments(clientId).then(history => {
                    if (!history || history.length === 0) {
                        historyContainer.innerHTML = '<div style="color: var(--text-secondary); font-size: 14px;">Записей пока нет</div>';
                        return;
                    }
                    historyContainer.innerHTML = '';
                    history.forEach(item => {
                        let statusHtml = '';
                        let opacity = '1';
                        
                        if (item.is_cancelled) {
                            statusHtml = '<span style="color: var(--text-secondary); font-size: 12px; margin-left: auto;">Отменено</span>';
                            opacity = '0.6';
                        } else if (item.is_no_show) {
                            statusHtml = '<span style="color: #ef4444; font-size: 12px; margin-left: auto;">Не пришёл</span>';
                        } else if (item.is_attended) {
                            statusHtml = '<span style="color: #22c55e; font-size: 12px; margin-left: auto;">Пришёл</span>';
                        } else {
                            statusHtml = '<span style="color: var(--text-secondary); font-size: 12px; margin-left: auto;">Запланировано</span>';
                        }
                        
                        const el = document.createElement('div');
                        el.style = `display: flex; align-items: center; padding: 10px; background: var(--surface); border-radius: 8px; opacity: ${opacity};`;
                        el.innerHTML = `
                            <div>
                                <div style="font-weight: 500; font-size: 14px;">${item.date} ${item.time_start}</div>
                                <div style="font-size: 12px; color: var(--text-secondary);">${item.training_type || 'Тренировка'}</div>
                            </div>
                            ${statusHtml}
                        `;
                        historyContainer.appendChild(el);
                    });
                }).catch(err => {
                    console.error("Ошибка загрузки истории:", err);
                    historyContainer.innerHTML = '<div style="color: #ef4444; font-size: 14px;">Ошибка загрузки</div>';
                });
            }
            
            const btnAdd = document.getElementById('cd-btn-add-package');
            const newBtnAdd = btnAdd.cloneNode(true);
            btnAdd.parentNode.replaceChild(newBtnAdd, btnAdd);
            
            newBtnAdd.addEventListener('click', async () => {
                const result = await window.showGenericModal("Добавить абонемент", [
                    { id: "count", label: "Количество занятий", type: "number", required: true, min: "1", value: "10" },
                    { id: "amount", label: "Сумма (₽)", type: "number", required: true, min: "0", step: "100" },
                    { id: "payment_method", label: "Оплата", type: "select", required: true, options: [
                        { value: "cash", text: "Наличные", selected: true },
                        { value: "card", text: "Карта" },
                        { value: "transfer", text: "Перевод" }
                    ]}
                ]);

                if (!result) return;
                
                const count = parseInt(result.count);
                const amount = parseFloat(result.amount);
                
                if (isNaN(count)) return;
                
                try {
                    await API.addPackage(clientId, {
                        sessions_count: count,
                        amount_paid: isNaN(amount) ? null : amount,
                        payment_method: result.payment_method
                    });
                    
                    this.loadClients();
                    if (window.showToast) window.showToast("Абонемент добавлен!");
                    else alert("Абонемент добавлен!");
                    document.getElementById('cd-btn-close').click();
                } catch (e) {
                    if (window.showToast) window.showToast("Ошибка добавления абонемента");
                    else alert("Ошибка добавления абонемента");
                }
            });
            
            document.getElementById('cd-btn-close').onclick = () => {
                modal.classList.add('hidden');
                document.body.style.overflow = '';
            };
            
            const btnDelete = document.getElementById('cd-btn-delete');
            if (btnDelete) {
                const newBtnDelete = btnDelete.cloneNode(true);
                btnDelete.parentNode.replaceChild(newBtnDelete, btnDelete);
                
                newBtnDelete.addEventListener('click', async () => {
                    if (confirm('Вы уверены? Клиент и все его данные отправятся в корзину.')) {
                        try {
                            await API.request('DELETE', '/clients/' + clientId);
                            document.getElementById('cd-btn-close').click();
                            this.loadClients();
                            if (window.showToast) window.showToast('Клиент удален в корзину');
                        } catch (e) {
                            alert('Ошибка удаления клиента');
                        }
                    }
                });
            }
            
        } catch (e) {
            alert("Ошибка загрузки деталей");
        }
    }
}

window.clientsManager = new ClientsManager();
