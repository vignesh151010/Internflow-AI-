from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    intern_id = Column(Integer, ForeignKey("interns.id", ondelete="CASCADE"), index=True, nullable=False)
    submission_link = Column(String(500), nullable=True)  # GitHub/Drive link
    file_path = Column(String(500), nullable=True)        # Uploaded file path
    version = Column(Integer, default=1, nullable=False)   # Resubmission version counter
    file_type = Column(String(50), nullable=True)          # e.g. .zip, .pdf, .py
    file_size_bytes = Column(Integer, nullable=True)
    is_latest = Column(Boolean, default=True)
    extracted_text = Column(Text, nullable=True)           # Safely extracted text for AI analysis
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="submitted", index=True)  # submitted, under_review, evaluated, needs_resubmission
    
    submitted_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    task = relationship("Task", back_populates="submissions")
    intern = relationship("Intern", back_populates="submissions")
    evaluations = relationship("Evaluation", back_populates="submission", cascade="all, delete-orphan")

