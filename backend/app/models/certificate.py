from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    intern_id = Column(Integer, ForeignKey("interns.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    certificate_number = Column(String(100), unique=True, index=True, nullable=False)
    issue_date = Column(Date, default=date.today, nullable=False)
    grade = Column(String(50), default="Outstanding")
    verification_hash = Column(String(128), unique=True, nullable=False)
    file_path = Column(String(500), nullable=True)
    status = Column(String(50), default="issued")  # pending, issued
    created_at = Column(DateTime, default=datetime.utcnow)

    intern = relationship("Intern", back_populates="certificate")

