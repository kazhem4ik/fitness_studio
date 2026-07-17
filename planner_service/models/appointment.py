from datetime import datetime, date, time
from typing import Optional
from sqlalchemy import Integer, String, Date, Time, DateTime, Boolean, Float, Text
from sqlalchemy.orm import Mapped, mapped_column

from planner_service.core.database import Base


class Appointment(Base):
    """Запись клиента на тренировку."""
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Клиент
    client_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    client_phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Время
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time_start: Mapped[time] = mapped_column(Time, nullable=False)
    time_end: Mapped[time] = mapped_column(Time, nullable=False)

    # Детали
    training_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Финансы
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # cash, card, transfer

    # Статус
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Мета
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
