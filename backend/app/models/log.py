from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    intern_id = Column(Integer, ForeignKey("interns.id", ondelete="SET NULL"), nullable=True)
    recipient_email = Column(String(255), index=True, nullable=False)
    subject = Column(String(255), nullable=False)
    body_preview = Column(Text, nullable=True)
    html_body = Column(Text, nullable=True)
    email_type = Column(String(50), default="welcome")  # 13 template types
    status = Column(String(50), default="QUEUED", index=True)  # QUEUED, SMTP_ACCEPTED, FAILED
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    idempotency_hash = Column(String(64), index=True, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)  # EXCEL_IMPORT, TASK_APPROVED, EVALUATE, etc.
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")

class AutomationJob(Base):
    __tablename__ = "automation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    intern_id = Column(Integer, ForeignKey("interns.id", ondelete="CASCADE"), nullable=True, index=True)
    workflow_id = Column(String(100), nullable=True, index=True)
    job_type = Column(String(100), nullable=False, index=True)
    status = Column(String(50), default="pending", index=True)  # pending, running, completed, failed, paused, cancelled
    scheduled_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_attempt_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    idempotency_key = Column(String(128), index=True, nullable=True)
    payload = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    intern = relationship("Intern", backref="automation_jobs")

