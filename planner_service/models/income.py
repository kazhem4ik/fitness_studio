from datetime import date, datetime
from typing import Optional
from sqlalchemy import Integer, String, Float, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from planner_service.core.database import Base


class Income(Base):
    """Ручной доход (не из записей)."""
    __tablename__ = "incomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Тренер-владелец дохода
    trainer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("admin_users.id"), nullable=True, index=True
    )

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String, index=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

