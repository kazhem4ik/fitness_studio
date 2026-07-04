from datetime import datetime
from typing import List, Optional
from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from bot_service.core.database import Base

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    max_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fitness_goal: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    nutrition_plan_active: Mapped[bool] = mapped_column(Boolean, default=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="user", cascade="all, delete-orphan")
    measurements: Mapped[List["Progress"]] = relationship("Progress", back_populates="user", cascade="all, delete-orphan")
