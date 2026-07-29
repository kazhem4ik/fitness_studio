from datetime import datetime
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from planner_service.core.database import Base


class AdminUser(Base):
    """Пользователь системы: admin (управляет) или trainer (работает со своими данными)."""
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, default="Тренер")
    role: Mapped[str] = mapped_column(String, default="trainer")  # 'admin' | 'trainer'
    is_active: Mapped[bool] = mapped_column(Integer, default=1)  # 1=True, 0=False
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
