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
            
            const titleEl = document.getElementById('finance-chart-title');
            if (titleEl) {
                const titles = {
                    'day': 'Динамика выручки (сегодня)',
                    'week': 'Динамика выручки (текущая неделя)',
                    'month': 'Динамика выручки (текущий месяц)',
                    'year': 'Динамика выручки (текущий год)'
                };
                titleEl.textContent = titles[this.currentPeriod] || 'Динамика выручки';
            }
            
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
                
                expenses.forEach(e => txs.push({ id: e.id, date: e.date, title: e.category, amount: e.amount, type: 'expense', comment: e.comment }));
                incomes.forEach(i => txs.push({ id: i.id, date: i.date, title: i.category, amount: i.amount, type: 'income', comment: i.comment, is_auto: i.is_auto }));
                
                txs.sort((a, b) => {
                    const diff = new Date(b.date).getTime() - new Date(a.date).getTime();
                    return diff !== 0 ? diff : b.id - a.id;
                });
            }
            
            // Render Categories
            const catContainer = document.getElementById('finances-categories');
            if (catContainer) {
                catContainer.innerHTML = '';
                if (summary.by_category && Object.keys(summary.by_category).length > 0) {
                    for (const [cat, sum] of Object.entries(summary.by_category)) {
                        const el = document.createElement('div');
                        el.style = "display: flex; justify-content: space-between; padding: 8px 12px; background: var(--surface); border-radius: 8px;";
                        el.innerHTML = `<span>${cat}</span><span style="font-weight: 600;">${sum} ₽</span>`;
                        catContainer.appendChild(el);
                    }
                } else {
                    catContainer.innerHTML = '<p class="empty-hint">Нет данных по расходам</p>';
                }
            }

            // Render Chart
            this.renderChart(summary.monthly_chart);

            if (txs.length > 0) {
                this.transactionsList.innerHTML = '';
                txs.slice(0, 50).forEach(tx => {
                    const isIncome = tx.type === 'income';
                    const color = isIncome ? '#22c55e' : '#ef4444';
                    const sign = isIncome ? '+' : '-';
                    
                    
                    const el = document.createElement('div');
                    el.className = 'expense-item';
                    
                    let cursorStyle = 'cursor: pointer;';
                    if (tx.is_auto) {
                        cursorStyle = 'cursor: default; opacity: 0.9;';
                        el.setAttribute('title', 'Оплата от клиента (редактируется в календаре)');
                    }

                    el.style = `display: flex; justify-content: space-between; padding: 12px; background: var(--surface); border-radius: 12px; margin-bottom: 8px; ${cursorStyle}`;
                    el.innerHTML = `
                        <div>
                            <div style="font-weight: 500;">${tx.title}</div>
                            <div style="font-size: 12px; color: var(--text-secondary);">${tx.date}</div>
                        </div>
                        <div style="font-weight: 600; color: ${color};">${sign}${tx.amount} ₽</div>
                    `;
                    
                    if (!tx.is_auto) {
                        el.addEventListener('click', () => this.showEditTransactionModal(tx));
                    }
                    this.transactionsList.appendChild(el);
                });
            } else {
                this.transactionsList.innerHTML = '<p class="empty-hint">Нет операций в этом периоде</p>';
            }
            
        } catch (error) {
            console.error('Ошибка загрузки финансов:', error);
        }
    }

    renderChart(chartData) {
        if (!chartData || !window.Chart) return;
        
        const ctx = document.getElementById('finance-chart');
        if (!ctx) return;
        
        if (this.chartInstance) {
            this.chartInstance.destroy();
        }
        
        const labels = chartData.map(d => d.label);
        const income = chartData.map(d => d.income);
        const expenses = chartData.map(d => d.expenses);
        
        this.chartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Доходы',
                        data: income,
                        backgroundColor: '#22c55e',
                        borderRadius: 4,
                    },
                    {
                        label: 'Расходы',
                        data: expenses,
                        backgroundColor: '#ef4444',
                        borderRadius: 4,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#888' }
                    },
                    y: {
                        grid: { color: '#2a2a35' },
                        ticks: { color: '#888' }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#fff' }
                    }
                }
            }
        });
    }

    async showEditTransactionModal(tx) {
        const isIncome = tx.type === 'income';
        const title = isIncome ? 'Редактировать доход' : 'Редактировать расход';
        
        let categoryOptions = [];
        if (isIncome) {
            categoryOptions = [
                { value: "Продажа товара", text: "Продажа товара" },
                { value: "Аренда шкафчика", text: "Аренда шкафчика" },
                { value: "Другое", text: "Другое" }
            ];
            // Убедимся что текущая категория есть в списке, иначе добавляем
            if (!categoryOptions.find(o => o.value === tx.title)) {
                categoryOptions.push({ value: tx.title, text: tx.title });
            }
        } else {
            categoryOptions = [
                { value: "Аренда", text: "Аренда" },
                { value: "Реклама", text: "Реклама" },
                { value: "Инвентарь", text: "Инвентарь" },
                { value: "Налоги", text: "Налоги" },
                { value: "Прочее", text: "Прочее" }
            ];
            if (!categoryOptions.find(o => o.value === tx.title)) {
                categoryOptions.push({ value: tx.title, text: tx.title });
            }
        }

        const result = await window.showGenericModal(title, [
            { id: "amount", label: "Сумма (₽)", type: "number", required: true, step: "0.01", min: "0", value: tx.amount },
            { id: "category", label: "Категория", type: "select", required: true, options: categoryOptions, value: tx.title },
            { id: "comment", label: "Комментарий", type: "text", placeholder: "Необязательно", value: tx.comment || '' }
        ], true);

        if (!result) return;
        
        try {
            if (result.action === 'delete') {
                if (!confirm('Точно удалить операцию?')) return;
                if (isIncome) {
                    await API.deleteIncome(tx.id);
                } else {
                    await API.deleteExpense(tx.id);
                }
                if (window.showToast) window.showToast("Операция удалена");
            } else {
                const data = {
                    amount: parseFloat(result.amount),
                    category: result.category,
                    comment: result.comment
                };
                if (isIncome) {
                    await API.updateIncome(tx.id, data);
                } else {
                    await API.updateExpense(tx.id, data);
                }
                if (window.showToast) window.showToast("Операция обновлена");
            }
            this.loadData();
        } catch (e) {
            if (window.showToast) window.showToast("Ошибка сохранения");
            else alert("Ошибка сохранения");
        }
    }

    async showAddExpenseModal() {
        const result = await window.showGenericModal("Добавить расход", [
            { id: "amount", label: "Сумма (₽)", type: "number", required: true, step: "0.01", min: "0" },
            { id: "category", label: "Категория", type: "select", required: true, options: [
                { value: "Аренда", text: "Аренда" },
                { value: "Реклама", text: "Реклама" },
                { value: "Инвентарь", text: "Инвентарь" },
                { value: "Налоги", text: "Налоги" },
                { value: "Прочее", text: "Прочее", selected: true }
            ]},
            { id: "comment", label: "Комментарий", type: "text", placeholder: "Необязательно" }
        ]);

        if (!result) return;
        
        try {
            await API.addExpense({
                date: new Date().toISOString().split('T')[0],
                amount: parseFloat(result.amount),
                category: result.category,
                comment: result.comment
            });
            this.loadData();
            if (window.showToast) window.showToast("Расход добавлен");
            else alert("Расход добавлен");
        } catch (e) {
            if (window.showToast) window.showToast("Ошибка сохранения расхода");
            else alert("Ошибка сохранения расхода");
        }
    }

    async showAddIncomeModal() {
        const result = await window.showGenericModal("Добавить доход", [
            { id: "amount", label: "Сумма (₽)", type: "number", required: true, step: "0.01", min: "0" },
            { id: "category", label: "Категория", type: "select", required: true, options: [
                { value: "Продажа товара", text: "Продажа товара" },
                { value: "Аренда шкафчика", text: "Аренда шкафчика" },
                { value: "Другое", text: "Другое", selected: true }
            ]},
            { id: "comment", label: "Комментарий", type: "text", placeholder: "Необязательно" }
        ]);

        if (!result) return;
        
        try {
            await API.addIncome({
                date: new Date().toISOString().split('T')[0],
                amount: parseFloat(result.amount),
                category: result.category,
                comment: result.comment
            });
            this.loadData();
            if (window.showToast) window.showToast("Доход добавлен");
            else alert("Доход добавлен");
        } catch (e) {
            if (window.showToast) window.showToast("Ошибка сохранения дохода");
            else alert("Ошибка сохранения дохода");
        }
    }
}

window.financesManager = new FinancesManager();
