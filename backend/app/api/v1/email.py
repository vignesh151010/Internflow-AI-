from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.intern import Intern
from app.models.log import EmailLog
from app.services.email_service import email_service

router = APIRouter()

@router.get("/status")
def get_email_status(
    admin: User = Depends(get_current_admin)
) -> Any:
    """Returns SMTP configuration and connection readiness."""
    return {
        "configured": email_service.is_configured(),
        "server": email_service.server_host,
        "port": email_service.port,
        "sender_email": email_service.email or "Not set in .env",
        "sender_name": email_service.from_name,
        "note": "SMTP acceptance does not guarantee inbox delivery."
    }

@router.post("/test-connection")
def test_smtp_connection(
    admin: User = Depends(get_current_admin)
) -> Any:
    """Performs genuine SSL/TLS handshake and login test with SMTP server."""
    return email_service.test_connection()

@router.post("/send-test")
def send_test_email(
    data: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Sends a sample test email using configured SMTP."""
    recipient = data.get("recipient_email", "").strip()
    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient email is required.")
        
    template_type = data.get("template_type", "welcome")
    res = email_service.send_email(
        recipient_email=recipient,
        email_type=template_type,
        intern=None,
        context_data={
            "name": "Test Recipient",
            "domain": "Software Engineering",
            "main_task": "Email Delivery Verification",
            "intern_code": "TEST-001"
        },
        db=db
    )
    return res

@router.get("/logs")
def get_email_logs(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Retrieves email dispatch history and tracking statuses."""
    query = db.query(EmailLog)
    if status_filter:
        query = query.filter(EmailLog.status == status_filter)
    logs = query.order_by(EmailLog.sent_at.desc()).limit(limit).all()
    
    return [
        {
            "id": l.id,
            "recipient_email": l.recipient_email,
            "subject": l.subject,
            "email_type": l.email_type,
            "status": l.status,
            "error_message": l.error_message,
            "retry_count": l.retry_count,
            "sent_at": l.sent_at.isoformat()
        }
        for l in logs
    ]

@router.post("/retry/{log_id}")
def retry_failed_email(
    log_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Retries dispatching a failed email."""
    success, msg = email_service.retry_failed_email(log_id, db)
    return {"success": success, "message": msg}

@router.post("/trigger/{intern_id}")
def trigger_template_email(
    intern_id: int,
    data: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Manually triggers any of the 13 personalized email templates for an intern."""
    intern = db.query(Intern).filter(Intern.id == intern_id).first()
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found.")
        
    template_type = data.get("template_type", "welcome")
    context_data = data.get("context_data", {})
    
    res = email_service.send_email(
        recipient_email=intern.email,
        email_type=template_type,
        intern=intern,
        context_data=context_data,
        db=db
    )
    return res
