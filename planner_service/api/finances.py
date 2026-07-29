import csv
import io
from datetime import date as dt_date, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.database import get_db
from planner_service.core.security import decode_access_token
from planner_service.models.appointment import Appointment
from planner_service.models.expense import Expense
from planner_service.models.income import Income
from planner_service.models.package import Package
from planner_service.models.client import Client

router = APIRouter(prefix="/api/finances", tags=["finances"])

COOKIE_NAME = "planner_token"

EXPENSE_CATEGORIES = {
    "rent": "Аренда",
    "inventory": "Инвентарь",
    "ads": "Реклама",
    "utilities": "Коммуналка",
    "taxes": "Налоги / самозанятость",
    "other": "Прочее",
}


async def require_auth(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Токен истёк")
    return payload


# --- Schemas ---

class ExpenseCreate(BaseModel):
    date: dt_date
    amount: float
    category: str
    comment: Optional[str] = None
    is_recurring: bool = False
    recurrence_day: Optional[int] = None

class IncomeCreate(BaseModel):
    date: dt_date
    amount: float
    category: str
    comment: Optional[str] = None

class IncomeResponse(BaseModel):
    id: int
    date: dt_date
    amount: float
    category: str
    comment: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class IncomeUpdate(BaseModel):
    date: Optional[dt_date] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    comment: Optional[str] = None

class ExpenseUpdate(BaseModel):
    date: Optional[dt_date] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    comment: Optional[str] = None
    is_recurring: Optional[bool] = None
    recurrence_day: Optional[int] = None

class ExpenseResponse(BaseModel):
    id: int
    date: dt_date
    amount: float
    category: str
    comment: Optional[str]
    is_recurring: bool
    recurrence_day: Optional[int]
    created_at: datetime
    model_config = {"from_attributes": True}


def _period_range(period: str) -> tuple[dt_date, dt_date]:
    """Возвращает (date_from, date_to) для периода day/week/month/year."""
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
        return start, end


# --- Endpoints ---

@router.get("/summary")
async def get_summary(
    period: str = Query("month", pattern="^(day|week|month|year)$"),
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Сводка: доходы / расходы / прибыль за период для текущего тренера."""
    trainer_id = int(auth["sub"])
    date_from, date_to = _period_range(period)

    # Доходы (купленные абонементы клиентов этого тренера)
    income_result = await db.execute(
        select(func.coalesce(func.sum(Package.amount_paid), 0.0))
        .select_from(Package).join(Client, Package.client_id == Client.id)
        .where(
            and_(
                Package.purchased_at >= date_from,
                Package.purchased_at <= date_to,
                Client.trainer_id == trainer_id,
                Client.deleted_at.is_(None),
            )
        )
    )
    income_auto = float(income_result.scalar())

    income_manual_result = await db.execute(
        select(func.coalesce(func.sum(Income.amount), 0.0)).where(
            and_(
                Income.date >= date_from,
                Income.date <= date_to,
                Income.trainer_id == trainer_id,
            )
        )
    )
    income_manual = float(income_manual_result.scalar())
    income = income_auto + income_manual

    # Расходы этого тренера
    expense_result = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
            and_(
                Expense.date >= date_from,
                Expense.date <= date_to,
                Expense.trainer_id == trainer_id,
            )
        )
    )
    expenses = float(expense_result.scalar())

    # Разбивка расходов по категориям
    cat_result = await db.execute(
        select(Expense.category, func.sum(Expense.amount)).where(
            and_(
                Expense.date >= date_from,
                Expense.date <= date_to,
                Expense.trainer_id == trainer_id,
            )
        ).group_by(Expense.category)
    )
    by_category = {
        EXPENSE_CATEGORIES.get(row[0], row[0]): float(row[1])
        for row in cat_result.all()
    }

    # Динамический график
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
                Client.deleted_at.is_(None),
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
        })

    return {
        "period": period,
        "date_from": str(date_from),
        "date_to": str(date_to),
        "income": income,
        "expenses": expenses,
        "profit": income - expenses,
        "by_category": by_category,
        "monthly_chart": chart_data,
    }


@router.get("/income")
async def get_income(
    date_from: Optional[dt_date] = None,
    date_to: Optional[dt_date] = None,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Список доходов (абонементы + ручные) за период."""
    trainer_id = int(auth["sub"])

    query = select(Package, Client.full_name).join(Client, Package.client_id == Client.id).where(
        and_(Client.trainer_id == trainer_id, Client.deleted_at.is_(None))
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
        if (p.amount_paid or 0) > 0
    ]
    items += [
        {
            "id": m.id,
            "date": str(m.date),
            "category": m.category,
            "amount": m.amount,
            "type": "income",
            "is_auto": False,
            "comment": m.comment
        }
        for m in manual_incomes
    ]
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


@router.get("/expenses", response_model=List[ExpenseResponse])
async def get_expenses(
    date_from: Optional[dt_date] = None,
    date_to: Optional[dt_date] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Список расходов текущего тренера."""
    trainer_id = int(auth["sub"])
    query = select(Expense).where(Expense.trainer_id == trainer_id)
    if date_from:
        query = query.where(Expense.date >= date_from)
    if date_to:
        query = query.where(Expense.date <= date_to)
    if category:
        query = query.where(Expense.category == category)
    query = query.order_by(Expense.date.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/expenses", response_model=ExpenseResponse, status_code=201)
async def create_expense(
    data: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Добавить расход."""
    trainer_id = int(auth["sub"])
    expense = Expense(trainer_id=trainer_id, **data.model_dump())
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.post("/incomes", response_model=IncomeResponse, status_code=201)
async def create_income(
    data: IncomeCreate,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Добавить ручной доход."""
    trainer_id = int(auth["sub"])
    income = Income(trainer_id=trainer_id, **data.model_dump())
    db.add(income)
    await db.commit()
    await db.refresh(income)
    return income


@router.put("/incomes/{income_id}", response_model=IncomeResponse)
async def update_income(
    income_id: int,
    data: IncomeUpdate,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Редактировать ручной доход."""
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Income).where(Income.id == income_id, Income.trainer_id == trainer_id)
    )
    income = result.scalar_one_or_none()
    if not income:
        raise HTTPException(status_code=404, detail="Доход не найден")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(income, key, value)
    await db.commit()
    await db.refresh(income)
    return income


@router.delete("/incomes/{income_id}")
async def delete_income(
    income_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Удалить ручной доход."""
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Income).where(Income.id == income_id, Income.trainer_id == trainer_id)
    )
    income = result.scalar_one_or_none()
    if not income:
        raise HTTPException(status_code=404, detail="Доход не найден")
    await db.delete(income)
    await db.commit()
    return {"success": True}


@router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Редактировать расход."""
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.trainer_id == trainer_id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Расход не найден")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(expense, key, value)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Удалить расход."""
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.trainer_id == trainer_id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Расход не найден")
    await db.delete(expense)
    await db.commit()
    return {"success": True}


@router.get("/export")
async def export_csv(
    date_from: Optional[dt_date] = None,
    date_to: Optional[dt_date] = None,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Экспорт доходов и расходов в CSV (для налоговой)."""
    trainer_id = int(auth["sub"])

    income_query = select(Package, Client.full_name).join(Client, Package.client_id == Client.id).where(
        and_(Client.trainer_id == trainer_id, Client.deleted_at.is_(None))
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
    writer = csv.writer(output, lineterminator='\n')

    writer.writerow(["=== ДОХОДЫ ==="])
    writer.writerow(["Дата", "Категория/Клиент", "Сумма", "Способ оплаты", "Занятий"])
    for p, c_name in incomes:
        writer.writerow([p.purchased_at, c_name, p.amount_paid or 0, p.payment_method or "", f"{p.sessions_count} шт."])
    for m in manual_incomes:
        writer.writerow([m.date, m.category, m.amount, "", "Ручной доход"])

    writer.writerow([])
    writer.writerow(["=== РАСХОДЫ ==="])
    writer.writerow(["Дата", "Категория", "Сумма", "Комментарий"])
    for e in expenses:
        writer.writerow([e.date, EXPENSE_CATEGORIES.get(e.category, e.category), e.amount, e.comment or ""])

    output.seek(0)
    filename = f"finances_{date_from or 'all'}_{date_to or 'now'}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
