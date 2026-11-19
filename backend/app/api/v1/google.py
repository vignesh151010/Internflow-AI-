import json
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.meeting import Meeting
from app.models.intern import Intern
from app.services.google_service import google_calendar_service
from app.services.email_service import email_service

router = APIRouter()

@router.get("/status")
def get_google_status(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Returns Google Calendar OAuth status and connection readiness."""
    return google_calendar_service.get_status(db)

@router.get("/auth-url")
def get_google_auth_url(
    admin: User = Depends(get_current_admin)
) -> Any:
    """Generates the Google OAuth 2.0 authorization URL."""
    url, error = google_calendar_service.get_authorization_url()
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"auth_url": url}

@router.get("/oauth2callback", response_class=HTMLResponse)
def handle_google_oauth_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> Any:
    """Handles OAuth 2.0 callback from Google and persists credentials."""
    if error:
        return f"""
        <html><body style="font-family: sans-serif; padding: 40px; text-align: center;">
          <h2 style="color: #EF4444;">Google Authorization Cancelled</h2>
          <p>{error}</p>
          <a href="/admin">Return to Admin Portal</a>
        </body></html>
        """
        
    if not code:
        return """
        <html><body style="font-family: sans-serif; padding: 40px; text-align: center;">
          <h2 style="color: #EF4444;">Missing Authorization Code</h2>
          <a href="/admin">Return to Admin Portal</a>
        </body></html>
        """

    success, msg = google_calendar_service.handle_auth_callback(code, db)
    if success:
        return """
        <html><body style="font-family: sans-serif; padding: 40px; text-align: center;">
          <h2 style="color: #10B981;">Google Calendar Successfully Authorized!</h2>
          <p>InternFlow AI can now automatically generate genuine Google Meet conferences for reviews.</p>
          <a href="/admin" style="display: inline-block; padding: 10px 20px; background: #1E3A8A; color: white; text-decoration: none; border-radius: 6px;">Return to Admin Dashboard</a>
          <script>setTimeout(() => window.location.href = '/admin', 2500);</script>
        </body></html>
        """
    else:
        return f"""
        <html><body style="font-family: sans-serif; padding: 40px; text-align: center;">
          <h2 style="color: #EF4444;">Authorization Failed</h2>
          <p>{msg}</p>
          <a href="/admin">Return to Admin Portal</a>
        </body></html>
        """

@router.post("/meetings/{meeting_id}/sync-calendar")
def sync_meeting_with_google(
    meeting_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Syncs a scheduled review meeting to Google Calendar, generating a genuine Google Meet link."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")

    # Find attendee emails
    attendee_emails = []
    interns = []
    if meeting.intern_ids == "all":
        interns = db.query(Intern).filter(Intern.status == "active").all()
        attendee_emails = [i.email for i in interns]
    elif meeting.intern_ids:
        try:
            ids = json.loads(meeting.intern_ids)
            interns = db.query(Intern).filter(Intern.id.in_(ids)).all()
            attendee_emails = [i.email for i in interns]
        except Exception:
            pass

    res = google_calendar_service.create_meeting_event(meeting, attendee_emails, db)
    
    # If Google Meet was generated, send invitation email to attendees
    if res.get("success") and meeting.meeting_link:
        for intern in interns:
            email_service.send_email(
                recipient_email=intern.email,
                email_type="review_meeting_invitation",
                intern=intern,
                context_data={
                    "meeting_title": meeting.title,
                    "scheduled_time": meeting.scheduled_time.strftime("%A, %B %d, %Y at %I:%M %p UTC"),
                    "duration_minutes": meeting.duration_minutes,
                    "meeting_link": meeting.meeting_link
                },
                db=db
            )

    return res

@router.delete("/meetings/{meeting_id}/cancel")
def cancel_google_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Cancels Google Calendar event and updates meeting record."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")

    cancelled = google_calendar_service.cancel_meeting_event(meeting, db)
    return {"success": cancelled, "message": "Meeting cancelled."}
