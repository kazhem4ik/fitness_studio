from datetime import datetime
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from planner_service.core.database import Base


class BookingAttempt(Base):
    """Попытка публичной записи — используется для rate limiting."""
    __tablename__ = "booking_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Форматированный номер телефона (через format_phone()) для корректного сравнения
    phone: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # IP-адрес из заголовка X-Real-IP (проставляется Nginx'ом)
    ip_address: Mapped[str] = mapped_column(String, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
