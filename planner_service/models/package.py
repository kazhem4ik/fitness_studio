from datetime import date, datetime
from typing import Optional
from sqlalchemy import Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from planner_service.core.database import Base


class Package(Base):
    """Покупка абонемента клиентом (история пополнений баланса)."""
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Связь с клиентом
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False, index=True)

    # Данные покупки
    purchased_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    sessions_count: Mapped[int] = mapped_column(Integer, nullable=False)     # Куплено занятий
    amount_paid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Сумма оплаты
    payment_method: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # cash/card/transfer
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связь
    client: Mapped["Client"] = relationship("Client", back_populates="packages")
