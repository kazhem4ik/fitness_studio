import re

with open('planner_service/static/js/clients.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add this.isTrashMode to constructor
content = content.replace(
    "this.clients = [];",
    "this.clients = [];\n        this.isTrashMode = false;"
)

# 2. Add event listeners for trash buttons in initEventListeners
event_listeners = """        if (this.btnAddClient) {
            this.btnAddClient.addEventListener('click', () => {
                this.showClientModal();
            });
        }"""

new_event_listeners = """        if (this.btnAddClient) {
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
                        await API.request('/api/clients/trash/empty', 'DELETE');
                        this.loadClients();
                        if (window.showToast) window.showToast('Корзина очищена');
                    } catch (e) {
                        alert('Ошибка очистки корзины');
                    }
                }
            });
        }"""

content = content.replace(event_listeners, new_event_listeners)

# 3. Handle Delete Client button in initEventListeners
delete_event_listener = """        const clientForm = document.getElementById('client-form');
        if (clientForm) {
            clientForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveClient();
            });
        }"""

new_delete_event_listener = """        const clientForm = document.getElementById('client-form');
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
                            await API.request('/api/clients/' + this.editingClientId, 'DELETE');
                            this.closeClientModal();
                            this.loadClients();
                            if (window.showToast) window.showToast('Клиент удален в корзину');
                        } catch (e) {
                            alert('Ошибка удаления клиента');
                        }
                    }
                }
            });
        }"""
        
content = content.replace(delete_event_listener, new_delete_event_listener)

# 4. Update loadClients API call
old_load = """    async loadClients() {
        try {
            const data = await API.getClients();"""

new_load = """    async loadClients() {
        try {
            const endpoint = this.isTrashMode ? '/api/clients?deleted=true' : '/api/clients';
            const data = await API.request(endpoint);"""

content = content.replace(old_load, new_load)

# 5. Show/hide delete button in showClientModal
old_show_modal = """    showClientModal(client = null) {
        this.editingClientId = client ? client.id : null;
        document.getElementById('client-modal-title').textContent = client ? 'Редактировать клиента' : 'Новый клиент';
        
        document.getElementById('client-name').value = client ? client.full_name : '';
        document.getElementById('client-phone').value = client ? (client.phone || '') : '';
        document.getElementById('client-notes').value = client ? (client.notes || '') : '';"""
        
new_show_modal = """    showClientModal(client = null) {
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
        }"""
        
content = content.replace(old_show_modal, new_show_modal)

# 6. Change click handler on client card if in trash mode
old_card_click = """            card.addEventListener('click', () => this.showClientDetails(client.id));
            this.listContainer.appendChild(card);"""
            
new_card_click = """            if (this.isTrashMode) {
                card.style.opacity = '0.7';
                card.innerHTML += `<div style="margin-top: 8px; text-align: center;"><button class="btn-outline btn-small" style="width: 100%; border-color: var(--primary); color: var(--primary);" onclick="event.stopPropagation(); window.clientsManager.restoreClient(${client.id})">Восстановить</button></div>`;
            } else {
                card.addEventListener('click', () => this.showClientDetails(client.id));
            }
            this.listContainer.appendChild(card);"""
            
content = content.replace(old_card_click, new_card_click)

# 7. Add restoreClient function
old_restore = """    async saveClient() {"""
new_restore = """    async restoreClient(clientId) {
        if (confirm('Восстановить этого клиента и все его данные?')) {
            try {
                await API.request('/api/clients/' + clientId + '/restore', 'POST');
                this.loadClients();
                if (window.showToast) window.showToast('Клиент восстановлен');
            } catch (e) {
                alert('Ошибка восстановления клиента');
            }
        }
    }

    async saveClient() {"""
    
content = content.replace(old_restore, new_restore)

with open('planner_service/static/js/clients.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("clients.js updated!")
