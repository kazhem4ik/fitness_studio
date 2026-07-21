/**
 * Управление финансами (сводка, расходы)
 */

class FinancesManager {
    constructor() {
        this.periodTabs = document.querySelectorAll('.ftab');
        this.incomeEl = document.getElementById('finance-income');
        this.expensesEl = document.getElementById('finance-expenses');
        this.profitEl = document.getElementById('finance-profit');
        this.transactionsList = document.getElementById('finances-transactions');
        this.btnAddExpense = document.getElementById('btn-add-expense');
        this.btnExport = document.getElementById('btn-export-csv');
        
        this.currentPeriod = 'month';
        
        this.initEventListeners();
    }

    initEventListeners() {
        this.periodTabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.periodTabs.forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');
                this.currentPeriod = e.target.dataset.fperiod;
                this.loadData();
            });
        });

        if (this.btnAddExpense) {
            this.btnAddExpense.addEventListener('click', () => this.showAddExpenseModal());
        }

        if (this.btnExport) {
            this.btnExport.addEventListener('click', () => {
                window.open('/clients/api/finances/export', '_blank');
            });
        }
    }

    async loadData() {
        try {
            const summary = await API.getFinanceSummary(this.currentPeriod);
            
            // Обновляем плашки
            if (this.incomeEl) this.incomeEl.textContent = `${summary.income} ₽`;
            if (this.expensesEl) this.expensesEl.textContent = `${summary.expenses} ₽`;
            
            if (this.profitEl) {
                this.profitEl.textContent = `${summary.profit} ₽`;
                if (summary.profit < 0) {
                    this.profitEl.style.color = '#ef4444';
                } else if (summary.profit > 0) {
                    this.profitEl.style.color = '#22c55e';
                } else {
                    this.profitEl.style.color = 'inherit';
                }
            }
            
            // Здесь в идеале загружать список последних транзакций (доходы + расходы),
            // сейчас для прототипа оставим пустым или загрузим только расходы
            this.transactionsList.innerHTML = '<p class="empty-hint">История загружается...</p>';
            
        } catch (error) {
            console.error('Ошибка загрузки финансов:', error);
        }
    }

    async showAddExpenseModal() {
        const amountStr = prompt("Сумма расхода (₽):");
        if (!amountStr) return;
        
        const amount = parseFloat(amountStr);
        if (isNaN(amount)) {
            alert("Неверная сумма");
            return;
        }
        
        const category = prompt("Категория (rent, ads, inventory, taxes, other):", "other");
        if (!category) return;
        
        const comment = prompt("Комментарий (необязательно):", "");
        
        try {
            await API.addExpense({
                date: new Date().toISOString().split('T')[0],
                amount: amount,
                category: category,
                comment: comment
            });
            this.loadData();
            alert("Расход добавлен");
        } catch (e) {
            alert("Ошибка сохранения расхода");
        }
    }
}

window.financesManager = new FinancesManager();
