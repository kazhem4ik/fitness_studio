from sqlalchemy import Column, Integer, String, Boolean, Date
from bot_service.core.database import Base

class DailySchedule(Base):
    __tablename__ = "daily_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True, nullable=False)
    is_day_off = Column(Boolean, default=False)
    
    open_time = Column(String, nullable=True)
    close_time = Column(String, nullable=True)
    slot_duration = Column(Integer, nullable=True)
    lunch_start = Column(String, nullable=True)
    lunch_end = Column(String, nullable=True)
    custom_breaks = Column(String, nullable=True)
