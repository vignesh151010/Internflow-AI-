from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), index=True, nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    intern_id = Column(Integer, ForeignKey("interns.id", ondelete="CASCADE"), index=True, nullable=False)
    score = Column(Float, nullable=False)
    completion_percentage = Column(Float, default=0.0)
    feedback = Column(Text, nullable=False)
    strengths = Column(Text, nullable=True)
    improvements = Column(Text, nullable=True)
    requirements_fulfilled = Column(Text, nullable=True)
    missing_requirements = Column(Text, nullable=True)
    technical_mistakes = Column(Text, nullable=True)
    code_quality_observations = Column(Text, nullable=True)
    step_by_step_corrections = Column(Text, nullable=True)
    ai_model_used = Column(String(100), nullable=True)
    is_ai_generated = Column(Boolean, default=False)
    final_status = Column(String(50), default="approved")  # approved, needs_resubmission, rejected
    evaluated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    submission = relationship("Submission", back_populates="evaluations")
    task = relationship("Task", back_populates="evaluations")
    intern = relationship("Intern", back_populates="evaluations")
    evaluator = relationship("User")

