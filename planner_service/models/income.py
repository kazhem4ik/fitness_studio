from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Date, DateTime, Boolean, Text
from planner_service.core.database import Base

class Income(Base):
    __tablename__ = "incomes"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    category = Column(String, index=True)  # например "manual" или "other"
    comment = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
