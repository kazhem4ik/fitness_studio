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
        this.isBlockedMode = false;

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
                if (this.isTrashMode) this.isBlockedMode = false; // сбрасываем другой режим
                trashBtn.style.color = this.isTrashMode ? 'var(--accent-purple)' : 'var(--text-secondary)';
                const blockedBtn = document.getElementById('btn-clients-blocked');
                if (blockedBtn) blockedBtn.style.color = 'var(--text-secondary)';

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

        // Кнопка режима заблокированных
        const blockedBtn = document.getElementById('btn-clients-blocked');
        if (blockedBtn) {
            blockedBtn.addEventListener('click', () => {
                this.isBlockedMode = !this.isBlockedMode;
                if (this.isBlockedMode) {
                    // Сбрасываем trash-режим
                    this.isTrashMode = false;
                    trashBtn && (trashBtn.style.color = 'var(--text-secondary)');
                    const btnEmpty = document.getElementById('btn-empty-trash');
                    if (btnEmpty) btnEmpty.classList.add('hidden');
                    const btnAdd = document.getElementById('btn-add-client');
                    if (btnAdd) btnAdd.classList.add('hidden');
                }
                blockedBtn.style.color = this.isBlockedMode ? 'var(--color-danger)' : 'var(--text-secondary)';
                if (!this.isBlockedMode) {
                    const btnAdd = document.getElementById('btn-add-client');
                    if (btnAdd) btnAdd.classList.remove('hidden');
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
        const modalCloseIcon = document.getElementById('client-modal-close-icon');
        if (modalCloseIcon) {
            modalCloseIcon.addEventListener('click', () => this.closeClientModal());
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
            let endpoint;
            if (this.isBlockedMode) {
                endpoint = '/clients?blocked=true';
            } else if (this.isTrashMode) {
                endpoint = '/clients?deleted=true';
            } else {
                endpoint = '/clients';
            }
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
            this.listContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">👥</div>
                    <p class="empty-text">Клиенты не найдены</p>
                </div>`;
            return;
        }

        filtered.forEach(client => {
            const card = document.createElement('div');
            card.className = 'client-card';

            const avatarClass = this._avatarVariant(client.full_name);
            const initials = this._initials(client.full_name);

            if (this.isBlockedMode) {
                card.classList.add('client-blocked');
                card.innerHTML = `
                    <div class="client-avatar ${avatarClass}">${initials}</div>
                    <div class="client-card-body">
                        <div class="client-name">${client.full_name}</div>
                        <div class="client-phone">${client.phone || 'Нет номера'}</div>
                        <button class="btn btn-outline btn-small client-restore-btn"
                            style="border-color: var(--accent-purple); color: var(--accent-purple);"
                            onclick="event.stopPropagation(); window.clientsManager.unblockClient(${client.id})">Разблокировать</button>
                    </div>
                    <div class="client-card-meta">
                        <span class="balance-badge balance-empty">Заблок</span>
                    </div>`;
            } else {
                const balance = client.sessions_balance || 0;
                let badgeClass = balance > 2 ? 'balance-positive' : balance > 0 ? 'balance-low' : 'balance-empty';
                const badgeText = balance > 0 ? `${balance} зан.` : '0 зан.';

                card.innerHTML = `
                    <div class="client-avatar ${avatarClass}">${initials}</div>
                    <div class="client-card-body">
                        <div class="client-name">${client.full_name}</div>
                        <div class="client-phone">${client.phone || 'Нет номера'}</div>
                    </div>
                    <div class="client-card-meta">
                        <span class="balance-badge ${badgeClass}">${badgeText}</span>
                    </div>
                    <svg class="client-card-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <polyline points="9 6 15 12 9 18"/>
                    </svg>`;

                if (this.isTrashMode) {
                    card.classList.add('client-deleted');
                    card.querySelector('.client-card-meta').innerHTML += `
                        <button class="btn btn-outline btn-small"
                            style="border-color: var(--accent-purple); color: var(--accent-purple); margin-top: 4px; font-size: 11px; padding: 4px 8px;"
                            onclick="event.stopPropagation(); window.clientsManager.restoreClient(${client.id})">Восстановить</button>`;
                    // Remove click-to-detail in trash mode
                } else {
                    card.addEventListener('click', () => this.showClientDetails(client.id));
                }
            }

            this.listContainer.appendChild(card);
        });

        // Update stats when not in trash/blocked mode
        if (!this.isTrashMode && !this.isBlockedMode) {
            this._updateStats(this.clients);
        }
    }

    /** Compute avatar initials (up to 2 letters) */
    _initials(name) {
        const parts = name.trim().split(/\s+/);
        if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
        return name.slice(0, 2).toUpperCase();
    }

    /** Pick one of 6 avatar colour variants based on name hash */
    _avatarVariant(name) {
        let hash = 0;
        for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) | 0;
        return 'av-' + ((Math.abs(hash) % 6) + 1);
    }

    /** Update stats bar */
    _updateStats(clients) {
        const total = clients.length;
        const active = clients.filter(c => (c.sessions_balance || 0) > 0).length;
        const expiring = clients.filter(c => { const b = c.sessions_balance || 0; return b === 1 || b === 2; }).length;

        const elTotal = document.getElementById('stat-total');
        const elActive = document.getElementById('stat-active');
        const elExpiring = document.getElementById('stat-expiring');
        if (elTotal) elTotal.textContent = total;
        if (elActive) elActive.textContent = active;
        if (elExpiring) elExpiring.textContent = expiring;
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
                if (window.showToast) window.showToast('Данные клиента обновлены');
            } else {
                await API.createClient({ full_name: name, phone: phone, notes: notes });
                if (window.showToast) window.showToast('Клиент добавлен');
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
            const balanceEl = document.getElementById('cd-balance');
            const balance = details.sessions_balance || 0;
            balanceEl.textContent = balance;
            balanceEl.className = 'client-balance-value' + (balance === 0 ? ' balance-zero' : '');

            // Set avatar
            const avatarEl = document.getElementById('cd-avatar');
            if (avatarEl) {
                avatarEl.textContent = this._initials(details.full_name);
                avatarEl.className = 'client-details-avatar ' + this._avatarVariant(details.full_name);
            }
            
                        // Загрузка истории
            const historyContainer = document.getElementById('cd-history');
            if (historyContainer) {
                historyContainer.innerHTML = '<div style="color: var(--text-secondary); font-size: 14px; padding: 12px 0;">Загрузка...</div>';
                API.getClientAppointments(clientId).then(history => {
                    if (!history || history.length === 0) {
                        historyContainer.innerHTML = '<div style="color: var(--text-secondary); font-size: 14px; padding: 12px 0;">Записей пока нет</div>';
                        return;
                    }
                    historyContainer.innerHTML = '';
                    history.forEach(item => {
                        let dotClass = 'dot-planned';
                        let statusText = 'Запланировано';
                        let statusColor = 'var(--text-secondary)';

                        if (item.is_cancelled) {
                            dotClass = 'dot-cancelled';
                            statusText = 'Отменено';
                            statusColor = 'var(--text-secondary)';
                        } else if (item.is_no_show) {
                            dotClass = 'dot-no-show';
                            statusText = 'Не пришёл';
                            statusColor = 'var(--color-danger)';
                        } else if (item.is_attended) {
                            dotClass = 'dot-attended';
                            statusText = 'Пришёл';
                            statusColor = 'var(--color-success)';
                        }

                        const el = document.createElement('div');
                        el.className = 'client-history-item';
                        if (item.is_cancelled) el.style.opacity = '0.5';
                        el.innerHTML = `
                            <div class="client-history-dot ${dotClass}"></div>
                            <div class="client-history-info">
                                <div class="client-history-date">${item.date} ${item.time_start}</div>
                                <div class="client-history-type">${item.training_type || 'Тренировка'}</div>
                            </div>
                            <div class="client-history-status" style="color: ${statusColor};">${statusText}</div>`;
                        historyContainer.appendChild(el);
                    });
                }).catch(err => {
                    console.error('Ошибка загрузки истории:', err);
                    historyContainer.innerHTML = '<div style="color: var(--color-danger); font-size: 14px; padding: 12px 0;">Ошибка загрузки</div>';
                });
            }

            const modal = document.getElementById('client-details-modal');
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';

            const btnEdit = document.getElementById('cd-btn-edit');
            if (btnEdit) {
                const newBtnEdit = btnEdit.cloneNode(true);
                btnEdit.parentNode.replaceChild(newBtnEdit, btnEdit);
                newBtnEdit.addEventListener('click', () => {
                    modal.classList.add('hidden');
                    document.body.style.overflow = '';
                    this.showClientModal(details);
                });
            }

            const btnRemove = document.getElementById('cd-btn-remove-session');
            if (btnRemove) {
                const newBtnRemove = btnRemove.cloneNode(true);
                btnRemove.parentNode.replaceChild(newBtnRemove, btnRemove);
                newBtnRemove.addEventListener('click', async () => {
                    if (details.sessions_balance <= 0) {
                        if (window.showToast) window.showToast("Баланс уже равен нулю", "error");
                        else alert("Баланс уже равен нулю");
                        return;
                    }
                    if (confirm(`Списать одно занятие вручную у ${details.full_name}?`)) {
                        try {
                            const newBalance = details.sessions_balance - 1;
                            await API.updateClient(details.id, { sessions_balance: newBalance });
                            document.getElementById('cd-balance').textContent = newBalance;
                            details.sessions_balance = newBalance;
                            this.renderList();
                            if (window.showToast) window.showToast("Занятие успешно списано!");
                        } catch (err) {
                            console.error(err);
                            if (window.showToast) window.showToast("Ошибка при списании", "error");
                        }
                    }
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
            
            const closeDetailsModal = () => {
                modal.classList.add('hidden');
                document.body.style.overflow = '';
            };
            document.getElementById('cd-btn-close').onclick = closeDetailsModal;
            const cdCloseIcon = document.getElementById('cd-modal-close-icon');
            if (cdCloseIcon) cdCloseIcon.onclick = closeDetailsModal;
            
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

            // Кнопка блокировки / разблокировки
            const btnBlock = document.getElementById('cd-btn-block');
            if (btnBlock) {
                if (details.phone) {
                    // Показываем кнопку только если есть номер (блокировка по номеру)
                    btnBlock.classList.remove('hidden');

                    if (details.is_blocked) {
                        btnBlock.textContent = 'Разблокировать';
                        btnBlock.style.borderColor = 'var(--accent-purple)';
                        btnBlock.style.color = 'var(--accent-purple)';
                    } else {
                        btnBlock.textContent = 'Заблокировать';
                        btnBlock.style.borderColor = 'var(--color-danger)';
                        btnBlock.style.color = 'var(--color-danger)';
                    }

                    const newBtnBlock = btnBlock.cloneNode(true);
                    btnBlock.parentNode.replaceChild(newBtnBlock, btnBlock);

                    newBtnBlock.addEventListener('click', async () => {
                        const newBlockedState = !details.is_blocked;
                        const confirmMsg = newBlockedState
                            ? `Заблокировать ${details.full_name}? Номер не сможет записаться на тренировку через форму записи.`
                            : `Разблокировать ${details.full_name}?`;

                        if (!confirm(confirmMsg)) return;

                        try {
                            await API.updateClient(clientId, { is_blocked: newBlockedState });
                            document.getElementById('cd-btn-close').click();
                            this.loadClients();
                            const msg = newBlockedState ? 'Клиент заблокирован' : 'Клиент разблокирован';
                            if (window.showToast) window.showToast(msg);
                        } catch (e) {
                            alert('Ошибка обновления статуса');
                        }
                    });
                } else {
                    btnBlock.classList.add('hidden');
                }
            }

        } catch (e) {
            alert("Ошибка загрузки деталей");
        }
    }

    async unblockClient(clientId) {
        if (!confirm('Разблокировать клиента? Он снова сможет записаться через форму.')) return;
        try {
            await API.updateClient(clientId, { is_blocked: false });
            this.loadClients();
            if (window.showToast) window.showToast('Клиент разблокирован');
        } catch (e) {
            alert('Ошибка разблокировки');
        }
    }
}

window.clientsManager = new ClientsManager();
