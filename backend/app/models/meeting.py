from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    meeting_type = Column(String(50), default="weekly_sync")  # orientation, weekly_sync, code_review, one_on_one
    scheduled_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=45)
    meeting_link = Column(String(500), nullable=True)
    google_event_id = Column(String(255), nullable=True)
    google_meet_url = Column(String(500), nullable=True)
    is_google_calendar_synced = Column(Boolean, default=False)
    host_admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    intern_ids = Column(Text, nullable=True)  # JSON list of intern IDs or 'all'
    status = Column(String(50), default="scheduled")  # scheduled, completed, cancelled, rescheduled
    created_at = Column(DateTime, default=datetime.utcnow)

    host = relationship("User")

