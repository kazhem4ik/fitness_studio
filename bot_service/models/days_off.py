from sqlalchemy import Column, Integer, Date
from bot_service.core.database import Base

class DayOff(Base):
    __tablename__ = "days_off"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True, nullable=False)
