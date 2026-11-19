from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class WeeklyRoadmap(Base):
    __tablename__ = "weekly_roadmaps"

    id = Column(Integer, primary_key=True, index=True)
    intern_id = Column(Integer, ForeignKey("interns.id", ondelete="CASCADE"), index=True, nullable=False)
    week_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    theme = Column(String(255), nullable=True)
    objectives = Column(Text, nullable=True)  # JSON or bullet list
    key_deliverables = Column(Text, nullable=True)
    estimated_hours = Column(Integer, default=20)
    ai_generated = Column(Boolean, default=True)
    status = Column(String(50), default="draft")  # draft, approved, active, completed
    approved_by_admin = Column(Boolean, default=False)
    approved_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    intern = relationship("Intern", back_populates="roadmaps")
    tasks = relationship("Task", back_populates="roadmap", cascade="all, delete-orphan")

