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
        if (!this.searchInput) return;

        this.searchInput.addEventListener('input', (e) => {
            this.renderList(e.target.value);
        });

        this.btnAddClient.addEventListener('click', () => {
            this.showClientModal();
        });
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

    async showClientModal(client = null) {
        // Модалка добавления/редактирования клиента (упрощенно через prompt, в идеале сделать кастомную)
        const name = prompt("Имя клиента:", client ? client.full_name : "");
        if (!name) return;
        const phone = prompt("Телефон:", client ? (client.phone || "") : "");

        try {
            if (client) {
                await API.updateClient(client.id, { full_name: name, phone: phone });
            } else {
                await API.createClient({ full_name: name, phone: phone });
            }
            this.loadClients();
        } catch (e) {
            alert("Ошибка сохранения клиента");
        }
    }

    async showClientDetails(clientId) {
        try {
            const details = await API.getClientDetails(clientId);
            
            // Здесь должна быть модалка с деталями, истории абонементов и кнопкой "Продать абонемент"
            // Упрощенная логика:
            const action = confirm(
                `Клиент: ${details.full_name}\nБаланс: ${details.sessions_balance} занятий\n\nПродать новый абонемент?`
            );
            
            if (action) {
                const count = parseInt(prompt("Количество занятий:", "10"));
                if (!count || isNaN(count)) return;
                
                const amount = parseFloat(prompt("Сумма (₽):", ""));
                
                await API.addPackage(clientId, {
                    sessions_count: count,
                    amount_paid: isNaN(amount) ? null : amount
                });
                
                this.loadClients();
                alert("Абонемент добавлен!");
            }
        } catch (e) {
            alert("Ошибка загрузки деталей");
        }
    }
}

window.clientsManager = new ClientsManager();
