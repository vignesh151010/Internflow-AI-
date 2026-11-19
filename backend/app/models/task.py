from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    intern_id = Column(Integer, ForeignKey("interns.id", ondelete="CASCADE"), index=True, nullable=False)
    roadmap_id = Column(Integer, ForeignKey("weekly_roadmaps.id", ondelete="SET NULL"), nullable=True)
    week_number = Column(Integer, default=1, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    instructions = Column(Text, nullable=True)  # Step-by-step
    technologies = Column(Text, nullable=True)  # Comma-separated or JSON
    expected_output = Column(Text, nullable=True)
    submission_requirements = Column(Text, nullable=True)
    evaluation_criteria = Column(Text, nullable=True)
    deadline = Column(DateTime, nullable=True)
    status = Column(String(50), default="pending", index=True)  # pending, submitted, in_review, approved, rejected
    max_score = Column(Float, default=100.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    intern = relationship("Intern", back_populates="tasks")
    roadmap = relationship("WeeklyRoadmap", back_populates="tasks")
    submissions = relationship("Submission", back_populates="task", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="task", cascade="all, delete-orphan")

