/**
 * Управление клиентами и абонементами
 */

class ClientsManager {
    constructor() {
        this.listContainer = document.getElementById('clients-list');
        this.searchInput = document.getElementById('clients-search');
        this.btnAddClient = document.getElementById('btn-add-client');
        this.clients = [];
        
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
            const data = await API.getClients();
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
            
            card.addEventListener('click', () => this.showClientDetails(client.id));
            this.listContainer.appendChild(card);
        });
    }

    showClientModal(client = null) {
        this.editingClientId = client ? client.id : null;
        document.getElementById('client-modal-title').textContent = client ? 'Редактировать клиента' : 'Новый клиент';
        
        document.getElementById('client-name').value = client ? client.full_name : '';
        document.getElementById('client-phone').value = client ? (client.phone || '') : '';
        
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

    async saveClient() {
        const name = document.getElementById('client-name').value.trim();
        const phone = document.getElementById('client-phone').value.trim();

        if (!name) return;

        try {
            if (this.editingClientId) {
                await API.updateClient(this.editingClientId, { full_name: name, phone: phone });
            } else {
                await API.createClient({ full_name: name, phone: phone });
            }
            this.closeClientModal();
            this.loadClients();
        } catch (e) {
            alert("Ошибка сохранения клиента");
        }
    }

    async showClientDetails(clientId) {
        try {
            const details = await API.getClientDetails(clientId);
            
            document.getElementById('cd-name').textContent = details.full_name;
            document.getElementById('cd-phone').textContent = details.phone || 'Нет номера';
            document.getElementById('cd-balance').textContent = details.sessions_balance || 0;
            
            const modal = document.getElementById('client-details-modal');
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
            
            const btnAdd = document.getElementById('cd-btn-add-package');
            const newBtnAdd = btnAdd.cloneNode(true);
            btnAdd.parentNode.replaceChild(newBtnAdd, btnAdd);
            
            newBtnAdd.addEventListener('click', async () => {
                const count = parseInt(prompt("Количество занятий:", "10"));
                if (!count || isNaN(count)) return;
                
                const amount = parseFloat(prompt("Сумма (₽):", ""));
                
                try {
                    await API.addPackage(clientId, {
                        sessions_count: count,
                        amount_paid: isNaN(amount) ? null : amount
                    });
                    
                    this.loadClients();
                    alert("Абонемент добавлен!");
                    document.getElementById('cd-btn-close').click();
                } catch (e) {
                    alert("Ошибка добавления абонемента");
                }
            });
            
            document.getElementById('cd-btn-close').onclick = () => {
                modal.classList.add('hidden');
                document.body.style.overflow = '';
            };
            
        } catch (e) {
            alert("Ошибка загрузки деталей");
        }
    }
}

window.clientsManager = new ClientsManager();
