from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Intern(Base):
    __tablename__ = "interns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=True)
    intern_code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=True)
    domain = Column(String(100), nullable=False, index=True)
    main_task = Column(String(255), nullable=False)
    task_description = Column(Text, nullable=True)
    start_date = Column(Date, nullable=False)
    duration_weeks = Column(Integer, default=4, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(50), default="active", index=True, nullable=False)  # active, completed, on_leave
    current_week = Column(Integer, default=1)
    total_score = Column(Float, default=0.0)
    workflow_status = Column(String(50), default="active", index=True)
    workflow_paused = Column(Boolean, default=False)
    
    # Invitation & onboarding
    invitation_token = Column(String(100), unique=True, index=True, nullable=True)
    is_invited = Column(Boolean, default=False)
    invitation_sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="intern_profile")
    roadmaps = relationship("WeeklyRoadmap", back_populates="intern", cascade="all, delete-orphan", order_by="WeeklyRoadmap.week_number")
    tasks = relationship("Task", back_populates="intern", cascade="all, delete-orphan", order_by="Task.week_number")
    submissions = relationship("Submission", back_populates="intern", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="intern", cascade="all, delete-orphan")
    attendance_records = relationship("Attendance", back_populates="intern", cascade="all, delete-orphan")
    certificate = relationship("Certificate", back_populates="intern", uselist=False, cascade="all, delete-orphan")
    chat_messages = relationship("ChatHistory", back_populates="intern", cascade="all, delete-orphan")

