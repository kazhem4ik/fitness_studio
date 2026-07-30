from datetime import datetime, date, time
from sqlalchemy import Integer, String, Date, Time, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from planner_service.core.database import Base


class SlotReservation(Base):
    """Временная резервация слота пользователем до отправки формы.

    Один session_id имеет не более одной активной резервации.
    При смене выбора — запись обновляется (upsert).
    Просроченные резервации удаляются при чтении слотов.
    """
    __tablename__ = "slot_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    trainer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admin_users.id"), nullable=False, index=True
    )

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time_start: Mapped[time] = mapped_column(Time, nullable=False)

    # Уникальный идентификатор сессии вкладки (из sessionStorage)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True, unique=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
