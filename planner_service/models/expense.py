from datetime import date, datetime
from typing import Optional
from sqlalchemy import Integer, String, Float, Date, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from planner_service.core.database import Base


class Expense(Base):
    """Расход студии (аренда, инвентарь, реклама и т.д.)."""
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)  # rent/inventory/ads/utilities/taxes/other
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Повторяющиеся расходы
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # день месяца (1-28)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
