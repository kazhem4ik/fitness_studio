from sqlalchemy import Column, Integer, String
from bot_service.core.database import Base

class StudioSettings(Base):
    __tablename__ = "studio_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    open_time = Column(String, default="10:00")
    close_time = Column(String, default="20:00")
    slot_duration = Column(Integer, default=75)
    lunch_start = Column(String, default="14:00")
    lunch_end = Column(String, default="15:00")
