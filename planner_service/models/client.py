from datetime import datetime
from typing import Optional, List
from sqlalchemy import Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from planner_service.core.database import Base


class Client(Base):
    """Карточка клиента фитнес-студии."""
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Основные данные
    full_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Заметки тренера

    # Баланс занятий (единый счётчик остатка)
    sessions_balance: Mapped[int] = mapped_column(Integer, default=0)

    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Даты
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_visit_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Связи
    packages: Mapped[List["Package"]] = relationship(
        "Package", back_populates="client", cascade="all, delete-orphan", order_by="Package.purchased_at.desc()"
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment", back_populates="client", foreign_keys="Appointment.client_id"
    )
