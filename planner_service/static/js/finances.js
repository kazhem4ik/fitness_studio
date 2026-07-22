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
        this.btnAddIncome = document.getElementById('btn-add-income');
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

        if (this.btnAddIncome) {
            this.btnAddIncome.addEventListener('click', () => this.showAddIncomeModal());
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
            
            // Загружаем список операций
            let txs = [];
            if (summary.date_from && summary.date_to) {
                const expenses = await API.getExpenses(summary.date_from, summary.date_to);
                const incomes = await API.getIncome(summary.date_from, summary.date_to);
                
                expenses.forEach(e => txs.push({ date: e.date, title: e.category, amount: e.amount, type: 'expense' }));
                incomes.forEach(i => txs.push({ date: i.date, title: i.category, amount: i.amount, type: 'income' }));
                
                txs.sort((a, b) => new Date(b.date) - new Date(a.date));
            }
            
            if (txs.length > 0) {
                this.transactionsList.innerHTML = '';
                txs.slice(0, 50).forEach(tx => {
                    const isIncome = tx.type === 'income';
                    const color = isIncome ? '#22c55e' : '#ef4444';
                    const sign = isIncome ? '+' : '-';
                    
                    const el = document.createElement('div');
                    el.className = 'expense-item';
                    el.style = "display: flex; justify-content: space-between; padding: 12px; background: var(--surface); border-radius: 12px; margin-bottom: 8px;";
                    el.innerHTML = `
                        <div>
                            <div style="font-weight: 500;">${tx.title}</div>
                            <div style="font-size: 12px; color: var(--text-secondary);">${tx.date}</div>
                        </div>
                        <div style="font-weight: 600; color: ${color};">${sign}${tx.amount} ₽</div>
                    `;
                    this.transactionsList.appendChild(el);
                });
            } else {
                this.transactionsList.innerHTML = '<p class="empty-hint">Нет операций в этом периоде</p>';
            }
            
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
        
        const category = prompt("Категория (Аренда, Реклама, Инвентарь, Налоги, Прочее):", "Прочее");
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

    async showAddIncomeModal() {
        const amountStr = prompt("Сумма дохода (₽):");
        if (!amountStr) return;
        
        const amount = parseFloat(amountStr);
        if (isNaN(amount)) {
            alert("Неверная сумма");
            return;
        }
        
        const category = prompt("Категория (например: Продажа товара, Другое):", "Другое");
        if (!category) return;
        
        const comment = prompt("Комментарий (необязательно):", "");
        
        try {
            await API.addIncome({
                date: new Date().toISOString().split('T')[0],
                amount: amount,
                category: category,
                comment: comment
            });
            this.loadData();
            alert("Доход добавлен");
        } catch (e) {
            alert("Ошибка сохранения дохода");
        }
    }
}

window.financesManager = new FinancesManager();
