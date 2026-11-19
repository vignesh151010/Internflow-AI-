from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    intern_id = Column(Integer, ForeignKey("interns.id", ondelete="CASCADE"), index=True, nullable=False)
    date = Column(Date, default=date.today, nullable=False, index=True)
    status = Column(String(50), default="present")  # present, absent, excused, late
    notes = Column(String(255), nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("intern_id", "date", name="uq_intern_attendance_date"),)

    intern = relationship("Intern", back_populates="attendance_records")

