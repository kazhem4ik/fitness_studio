import csv
import io
from datetime import date, datetime, timedelta
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
    date: date
    amount: float
    category: str
    comment: Optional[str] = None
    is_recurring: bool = False
    recurrence_day: Optional[int] = None

class ExpenseUpdate(BaseModel):
    date: Optional[date] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    comment: Optional[str] = None
    is_recurring: Optional[bool] = None
    recurrence_day: Optional[int] = None

class ExpenseResponse(BaseModel):
    id: int
    date: date
    amount: float
    category: str
    comment: Optional[str]
    is_recurring: bool
    recurrence_day: Optional[int]
    created_at: datetime
    model_config = {"from_attributes": True}


def _period_range(period: str) -> tuple[date, date]:
    """Возвращает (date_from, date_to) для периода day/week/month."""
    today = date.today()
    if period == "day":
        return today, today
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        return start, today
    else:  # month
        start = today.replace(day=1)
        return start, today


# --- Endpoints ---

@router.get("/summary")
async def get_summary(
    period: str = Query("month", pattern="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Сводка: доходы / расходы / прибыль за период."""
    date_from, date_to = _period_range(period)

    # Доходы (оплаченные записи)
    income_result = await db.execute(
        select(func.coalesce(func.sum(Appointment.price), 0.0)).where(
            and_(
                Appointment.date >= date_from,
                Appointment.date <= date_to,
                Appointment.is_paid == True,
                Appointment.is_cancelled == False,
            )
        )
    )
    income = float(income_result.scalar())

    # Расходы
    expense_result = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
            and_(Expense.date >= date_from, Expense.date <= date_to)
        )
    )
    expenses = float(expense_result.scalar())

    # Разбивка расходов по категориям
    cat_result = await db.execute(
        select(Expense.category, func.sum(Expense.amount)).where(
            and_(Expense.date >= date_from, Expense.date <= date_to)
        ).group_by(Expense.category)
    )
    by_category = {
        EXPENSE_CATEGORIES.get(row[0], row[0]): float(row[1])
        for row in cat_result.all()
    }

    # Помесячная динамика (последние 12 месяцев)
    months_data = []
    for i in range(11, -1, -1):
        # i месяцев назад
        pivot = date.today()
        m = pivot.month - i
        y = pivot.year
        while m <= 0:
            m += 12
            y -= 1
        month_start = date(y, m, 1)
        # конец месяца
        if m == 12:
            month_end = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(y, m + 1, 1) - timedelta(days=1)

        inc_r = await db.execute(
            select(func.coalesce(func.sum(Appointment.price), 0.0)).where(
                and_(
                    Appointment.date >= month_start,
                    Appointment.date <= month_end,
                    Appointment.is_paid == True,
                    Appointment.is_cancelled == False,
                )
            )
        )
        exp_r = await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
                and_(Expense.date >= month_start, Expense.date <= month_end)
            )
        )
        months_data.append({
            "label": month_start.strftime("%b %Y"),
            "income": float(inc_r.scalar()),
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
        "monthly_chart": months_data,
    }


@router.get("/income")
async def get_income(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Список доходов (оплаченных записей) за период."""
    query = select(Appointment).where(
        and_(Appointment.is_paid == True, Appointment.is_cancelled == False)
    )
    if date_from:
        query = query.where(Appointment.date >= date_from)
    if date_to:
        query = query.where(Appointment.date <= date_to)
    query = query.order_by(Appointment.date.desc())
    result = await db.execute(query)
    appointments = result.scalars().all()
    return [
        {
            "id": a.id,
            "date": str(a.date),
            "client_name": a.client_name,
            "amount": a.price,
            "payment_method": a.payment_method,
            "training_type": a.training_type,
        }
        for a in appointments
    ]


@router.get("/expenses", response_model=List[ExpenseResponse])
async def get_expenses(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Список расходов."""
    query = select(Expense)
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
    _auth: dict = Depends(require_auth),
):
    """Добавить расход."""
    expense = Expense(**data.model_dump())
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Редактировать расход."""
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
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
    _auth: dict = Depends(require_auth),
):
    """Удалить расход."""
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Расход не найден")
    await db.delete(expense)
    await db.commit()
    return {"success": True}


@router.get("/export")
async def export_csv(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Экспорт доходов и расходов в CSV (для налоговой)."""
    # Доходы
    income_query = select(Appointment).where(
        and_(Appointment.is_paid == True, Appointment.is_cancelled == False)
    )
    if date_from:
        income_query = income_query.where(Appointment.date >= date_from)
    if date_to:
        income_query = income_query.where(Appointment.date <= date_to)
    income_res = await db.execute(income_query.order_by(Appointment.date))
    incomes = income_res.scalars().all()

    # Расходы
    expense_query = select(Expense)
    if date_from:
        expense_query = expense_query.where(Expense.date >= date_from)
    if date_to:
        expense_query = expense_query.where(Expense.date <= date_to)
    expense_res = await db.execute(expense_query.order_by(Expense.date))
    expenses = expense_res.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== ДОХОДЫ ==="])
    writer.writerow(["Дата", "Клиент", "Сумма", "Способ оплаты", "Тип тренировки"])
    for a in incomes:
        writer.writerow([a.date, a.client_name, a.price or 0, a.payment_method or "", a.training_type or ""])

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
