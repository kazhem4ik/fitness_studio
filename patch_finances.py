import re

with open('planner_service/api/finances.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
content = content.replace(
    "from planner_service.models.appointment import Appointment",
    "from planner_service.models.appointment import Appointment\nfrom planner_service.models.package import Package\nfrom planner_service.models.client import Client"
)

# 2. Update _period_range
old_period = """def _period_range(period: str) -> tuple[dt_date, dt_date]:
    \"\"\"Возвращает (date_from, date_to) для периода day/week/month.\"\"\"
    today = dt_date.today()
    if period == "day":
        return today, today
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end
    else:  # month
        start = today.replace(day=1)
        next_month = start.replace(day=28) + timedelta(days=4)
        end = next_month - timedelta(days=next_month.day)
        return start, end"""

new_period = """def _period_range(period: str) -> tuple[dt_date, dt_date]:
    \"\"\"Возвращает (date_from, date_to) для периода day/week/month/year.\"\"\"
    today = dt_date.today()
    if period == "day":
        return today, today
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end
    elif period == "month":
        start = today.replace(day=1)
        next_month = start.replace(day=28) + timedelta(days=4)
        end = next_month - timedelta(days=next_month.day)
        return start, end
    else:  # year
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        return start, end"""
content = content.replace(old_period, new_period)

# 3. Update get_summary signature
content = content.replace('pattern="^(day|week|month)$"', 'pattern="^(day|week|month|year)$"')

# 4. Replace income_result query in get_summary
old_inc_query = """    # Доходы (оплаченные записи этого тренера)
    income_result = await db.execute(
        select(func.coalesce(func.sum(Appointment.price), 0.0)).where(
            and_(
                Appointment.date >= date_from,
                Appointment.date <= date_to,
                Appointment.is_paid == True,
                Appointment.is_cancelled == False,
                Appointment.trainer_id == trainer_id,
            )
        )
    )"""
new_inc_query = """    # Доходы (купленные абонементы клиентов этого тренера)
    income_result = await db.execute(
        select(func.coalesce(func.sum(Package.amount_paid), 0.0))
        .select_from(Package).join(Client, Package.client_id == Client.id)
        .where(
            and_(
                Package.purchased_at >= date_from,
                Package.purchased_at <= date_to,
                Client.trainer_id == trainer_id,
            )
        )
    )"""
content = content.replace(old_inc_query, new_inc_query)

# 5. Dynamic Chart Logic
old_chart = """    # Помесячная динамика (последние 12 месяцев)
    months_data = []
    for i in range(11, -1, -1):
        pivot = dt_date.today()
        m = pivot.month - i
        y = pivot.year
        while m <= 0:
            m += 12
            y -= 1
        month_start = dt_date(y, m, 1)
        if m == 12:
            month_end = dt_date(y + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = dt_date(y, m + 1, 1) - timedelta(days=1)

        inc_r = await db.execute(
            select(func.coalesce(func.sum(Appointment.price), 0.0)).where(
                and_(
                    Appointment.date >= month_start,
                    Appointment.date <= month_end,
                    Appointment.is_paid == True,
                    Appointment.is_cancelled == False,
                    Appointment.trainer_id == trainer_id,
                )
            )
        )
        inc_m_r = await db.execute(
            select(func.coalesce(func.sum(Income.amount), 0.0)).where(
                and_(
                    Income.date >= month_start,
                    Income.date <= month_end,
                    Income.trainer_id == trainer_id,
                )
            )
        )
        exp_r = await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
                and_(
                    Expense.date >= month_start,
                    Expense.date <= month_end,
                    Expense.trainer_id == trainer_id,
                )
            )
        )
        months_data.append({
            "label": month_start.strftime("%b %Y"),
            "income": float(inc_r.scalar()) + float(inc_m_r.scalar()),
            "expenses": float(exp_r.scalar()),
        })"""
new_chart = """    # Динамический график
    chart_data = []
    intervals = []
    
    if period == "day":
        intervals.append({
            "label": date_from.strftime("%d.%m"),
            "start": date_from,
            "end": date_from
        })
    elif period == "week":
        # По дням (Пн-Вс)
        for i in range(7):
            d = date_from + timedelta(days=i)
            intervals.append({
                "label": d.strftime("%d.%m"),
                "start": d,
                "end": d
            })
    elif period == "month":
        # По календарным неделям месяца
        curr = date_from
        week_num = 1
        while curr <= date_to:
            week_end = curr + timedelta(days=6 - curr.weekday())
            if week_end > date_to:
                week_end = date_to
            intervals.append({
                "label": f"Неделя {week_num}",
                "start": curr,
                "end": week_end
            })
            curr = week_end + timedelta(days=1)
            week_num += 1
    else:  # year
        # По месяцам
        for m in range(1, 13):
            m_start = date_from.replace(month=m, day=1)
            if m == 12:
                m_end = m_start.replace(year=m_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                m_end = m_start.replace(month=m + 1, day=1) - timedelta(days=1)
            intervals.append({
                "label": m_start.strftime("%b"),
                "start": m_start,
                "end": m_end
            })

    for inv in intervals:
        i_start = inv["start"]
        i_end = inv["end"]
        
        inc_r = await db.execute(
            select(func.coalesce(func.sum(Package.amount_paid), 0.0))
            .select_from(Package).join(Client, Package.client_id == Client.id)
            .where(
                and_(
                    Package.purchased_at >= i_start,
                    Package.purchased_at <= i_end,
                    Client.trainer_id == trainer_id,
                )
            )
        )
        inc_m_r = await db.execute(
            select(func.coalesce(func.sum(Income.amount), 0.0)).where(
                and_(
                    Income.date >= i_start,
                    Income.date <= i_end,
                    Income.trainer_id == trainer_id,
                )
            )
        )
        exp_r = await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
                and_(
                    Expense.date >= i_start,
                    Expense.date <= i_end,
                    Expense.trainer_id == trainer_id,
                )
            )
        )
        chart_data.append({
            "label": inv["label"],
            "income": float(inc_r.scalar()) + float(inc_m_r.scalar()),
            "expenses": float(exp_r.scalar()),
        })"""
content = content.replace(old_chart, new_chart)
content = content.replace('"monthly_chart": months_data,', '"monthly_chart": chart_data,')

# 6. /income - query packages instead of appointments
old_income_ep = """@router.get("/income")
async def get_income(
    date_from: Optional[dt_date] = None,
    date_to: Optional[dt_date] = None,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Список доходов (оплаченных записей + ручные) за период.\"\"\"
    trainer_id = int(auth["sub"])

    query = select(Appointment).where(
        and_(
            Appointment.is_paid == True,
            Appointment.is_cancelled == False,
            Appointment.trainer_id == trainer_id,
        )
    )
    if date_from:
        query = query.where(Appointment.date >= date_from)
    if date_to:
        query = query.where(Appointment.date <= date_to)
    query = query.order_by(Appointment.date.desc())
    result = await db.execute(query)
    appointments = result.scalars().all()

    inc_query = select(Income).where(Income.trainer_id == trainer_id)
    if date_from:
        inc_query = inc_query.where(Income.date >= date_from)
    if date_to:
        inc_query = inc_query.where(Income.date <= date_to)
    inc_query = inc_query.order_by(Income.date.desc())
    inc_result = await db.execute(inc_query)
    manual_incomes = inc_result.scalars().all()

    items = [
        {
            "id": a.id,
            "date": str(a.date),
            "category": "Клиент: " + a.client_name,
            "amount": a.price or 0,
            "type": "income",
            "is_auto": True
        }
        for a in appointments
    ]
    items += ["""

new_income_ep = """@router.get("/income")
async def get_income(
    date_from: Optional[dt_date] = None,
    date_to: Optional[dt_date] = None,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Список доходов (абонементы + ручные) за период.\"\"\"
    trainer_id = int(auth["sub"])

    query = select(Package, Client.full_name).join(Client, Package.client_id == Client.id).where(
        Client.trainer_id == trainer_id
    )
    if date_from:
        query = query.where(Package.purchased_at >= date_from)
    if date_to:
        query = query.where(Package.purchased_at <= date_to)
    query = query.order_by(Package.purchased_at.desc())
    result = await db.execute(query)
    packages = result.all() # returns tuples (Package, client_name)

    inc_query = select(Income).where(Income.trainer_id == trainer_id)
    if date_from:
        inc_query = inc_query.where(Income.date >= date_from)
    if date_to:
        inc_query = inc_query.where(Income.date <= date_to)
    inc_query = inc_query.order_by(Income.date.desc())
    inc_result = await db.execute(inc_query)
    manual_incomes = inc_result.scalars().all()

    items = [
        {
            "id": p.id,
            "date": str(p.purchased_at),
            "category": "Клиент: " + c_name,
            "amount": p.amount_paid or 0,
            "type": "income",
            "is_auto": True
        }
        for p, c_name in packages
    ]
    items += ["""
content = content.replace(old_income_ep, new_income_ep)

# 7. /export - same logic for exports + BOM
old_export = """@router.get("/export")
async def export_csv(
    date_from: Optional[dt_date] = None,
    date_to: Optional[dt_date] = None,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Экспорт доходов и расходов в CSV (для налоговой).\"\"\"
    trainer_id = int(auth["sub"])

    income_query = select(Appointment).where(
        and_(
            Appointment.is_paid == True,
            Appointment.is_cancelled == False,
            Appointment.trainer_id == trainer_id,
        )
    )
    if date_from:
        income_query = income_query.where(Appointment.date >= date_from)
    if date_to:
        income_query = income_query.where(Appointment.date <= date_to)
    income_res = await db.execute(income_query.order_by(Appointment.date))
    incomes = income_res.scalars().all()

    inc_manual_query = select(Income).where(Income.trainer_id == trainer_id)
    if date_from:
        inc_manual_query = inc_manual_query.where(Income.date >= date_from)
    if date_to:
        inc_manual_query = inc_manual_query.where(Income.date <= date_to)
    inc_manual_res = await db.execute(inc_manual_query.order_by(Income.date))
    manual_incomes = inc_manual_res.scalars().all()

    expense_query = select(Expense).where(Expense.trainer_id == trainer_id)
    if date_from:
        expense_query = expense_query.where(Expense.date >= date_from)
    if date_to:
        expense_query = expense_query.where(Expense.date <= date_to)
    expense_res = await db.execute(expense_query.order_by(Expense.date))
    expenses = expense_res.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== ДОХОДЫ ==="])
    writer.writerow(["Дата", "Категория/Клиент", "Сумма", "Способ оплаты", "Тренировка"])
    for a in incomes:
        writer.writerow([a.date, a.client_name, a.price or 0, a.payment_method or "", a.training_type or ""])
    for m in manual_incomes:
        writer.writerow([m.date, m.category, m.amount, "", "Ручной доход"])"""

new_export = """@router.get("/export")
async def export_csv(
    date_from: Optional[dt_date] = None,
    date_to: Optional[dt_date] = None,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    \"\"\"Экспорт доходов и расходов в CSV (для налоговой).\"\"\"
    trainer_id = int(auth["sub"])

    income_query = select(Package, Client.full_name).join(Client, Package.client_id == Client.id).where(
        Client.trainer_id == trainer_id
    )
    if date_from:
        income_query = income_query.where(Package.purchased_at >= date_from)
    if date_to:
        income_query = income_query.where(Package.purchased_at <= date_to)
    income_res = await db.execute(income_query.order_by(Package.purchased_at))
    incomes = income_res.all()

    inc_manual_query = select(Income).where(Income.trainer_id == trainer_id)
    if date_from:
        inc_manual_query = inc_manual_query.where(Income.date >= date_from)
    if date_to:
        inc_manual_query = inc_manual_query.where(Income.date <= date_to)
    inc_manual_res = await db.execute(inc_manual_query.order_by(Income.date))
    manual_incomes = inc_manual_res.scalars().all()

    expense_query = select(Expense).where(Expense.trainer_id == trainer_id)
    if date_from:
        expense_query = expense_query.where(Expense.date >= date_from)
    if date_to:
        expense_query = expense_query.where(Expense.date <= date_to)
    expense_res = await db.execute(expense_query.order_by(Expense.date))
    expenses = expense_res.scalars().all()

    output = io.StringIO()
    output.write('\ufeff') # BOM for Excel
    writer = csv.writer(output)

    writer.writerow(["=== ДОХОДЫ ==="])
    writer.writerow(["Дата", "Категория/Клиент", "Сумма", "Способ оплаты", "Занятий"])
    for p, c_name in incomes:
        writer.writerow([p.purchased_at, c_name, p.amount_paid or 0, p.payment_method or "", f"{p.sessions_count} шт."])
    for m in manual_incomes:
        writer.writerow([m.date, m.category, m.amount, "", "Ручной доход"])"""
content = content.replace(old_export, new_export)

with open('planner_service/api/finances.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done.")
