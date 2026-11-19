import json
import logging
from datetime import datetime, date
from typing import Any, List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_intern_user, get_current_user
from app.models.intern import Intern
from app.models.task import Task
from app.models.submission import Submission
from app.models.evaluation import Evaluation
from app.models.attendance import Attendance
from app.models.meeting import Meeting
from app.models.notification import Notification
from app.models.certificate import Certificate
from app.models.chat import ChatHistory
from app.models.user import User
from app.schemas.task import SubmissionCreate
from app.services.submission_service import submission_service
from app.services.chat_service import intern_chat_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/profile")
def get_intern_profile(
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Returns intern's own profile and progress metrics. Strictly isolated to current intern."""
    total_tasks = len(intern.tasks)
    completed_tasks = sum(1 for t in intern.tasks if t.status in ["approved", "evaluated"])
    pending_tasks = sum(1 for t in intern.tasks if t.status in ["pending", "needs_resubmission"])
    progress = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0

    return {
        "id": intern.id,
        "intern_code": intern.intern_code,
        "name": intern.name,
        "email": intern.email,
        "phone": intern.phone,
        "domain": intern.domain,
        "main_task": intern.main_task,
        "task_description": intern.task_description,
        "start_date": intern.start_date.isoformat(),
        "duration_weeks": intern.duration_weeks,
        "end_date": intern.end_date.isoformat(),
        "status": intern.status,
        "current_week": intern.current_week,
        "total_score": intern.total_score,
        "progress_percentage": progress,
        "tasks_count": total_tasks,
        "completed_tasks_count": completed_tasks,
        "pending_tasks_count": pending_tasks
    }

@router.get("/roadmap")
def get_intern_roadmap(
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Returns weekly roadmap and tasks for current authenticated intern."""
    roadmaps_data = []
    for r in intern.roadmaps:
        tasks_data = []
        for t in r.tasks:
            latest_sub = None
            if t.submissions:
                s = [sub for sub in t.submissions if sub.is_latest]
                s = s[-1] if s else t.submissions[-1]
                latest_eval = s.evaluations[-1] if s.evaluations else None
                latest_sub = {
                    "id": s.id,
                    "version": s.version,
                    "submission_link": s.submission_link,
                    "file_path": s.file_path,
                    "file_type": s.file_type,
                    "notes": s.notes,
                    "status": s.status,
                    "submitted_at": s.submitted_at.isoformat(),
                    "evaluation": {
                        "score": latest_eval.score,
                        "feedback": latest_eval.feedback,
                        "strengths": latest_eval.strengths,
                        "improvements": latest_eval.improvements,
                        "final_status": latest_eval.final_status
                    } if latest_eval else None
                }
            tasks_data.append({
                "id": t.id,
                "week_number": t.week_number,
                "title": t.title,
                "description": t.description,
                "instructions": t.instructions,
                "technologies": t.technologies,
                "expected_output": t.expected_output,
                "submission_requirements": t.submission_requirements,
                "evaluation_criteria": t.evaluation_criteria,
                "deadline": t.deadline.isoformat() if t.deadline else None,
                "status": t.status,
                "max_score": t.max_score,
                "latest_submission": latest_sub
            })

        roadmaps_data.append({
            "id": r.id,
            "week_number": r.week_number,
            "title": r.title,
            "theme": r.theme,
            "objectives": r.objectives,
            "key_deliverables": r.key_deliverables,
            "estimated_hours": r.estimated_hours,
            "status": r.status,
            "tasks": tasks_data
        })
    return roadmaps_data

@router.get("/tasks")
def get_intern_tasks(
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Returns all assigned tasks with submission status for current intern."""
    tasks = db.query(Task).filter(Task.intern_id == intern.id).order_by(Task.week_number).all()
    results = []
    for t in tasks:
        subs = [s for s in t.submissions if s.is_latest]
        latest_sub = subs[-1] if subs else (t.submissions[-1] if t.submissions else None)
        latest_eval = latest_sub.evaluations[-1] if (latest_sub and latest_sub.evaluations) else None
        
        results.append({
            "id": t.id,
            "week_number": t.week_number,
            "title": t.title,
            "description": t.description,
            "instructions": t.instructions,
            "technologies": t.technologies,
            "expected_output": t.expected_output,
            "submission_requirements": t.submission_requirements,
            "evaluation_criteria": t.evaluation_criteria,
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "status": t.status,
            "max_score": t.max_score,
            "submission": {
                "id": latest_sub.id,
                "version": latest_sub.version,
                "submission_link": latest_sub.submission_link,
                "file_path": latest_sub.file_path,
                "file_type": latest_sub.file_type,
                "notes": latest_sub.notes,
                "status": latest_sub.status,
                "submitted_at": latest_sub.submitted_at.isoformat()
            } if latest_sub else None,
            "evaluation": {
                "score": latest_eval.score,
                "feedback": latest_eval.feedback,
                "strengths": latest_eval.strengths,
                "improvements": latest_eval.improvements,
                "final_status": latest_eval.final_status
            } if latest_eval else None
        })
    return results

@router.post("/tasks/{task_id}/submit")
async def submit_task(
    task_id: int,
    request: Request,
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Submits milestone deliverables with support for:
    - File upload (ZIP, PDF, DOCX, PPTX, Source code)
    - GitHub / Live Demo URL
    - Technical summary notes
    - Automatic versioning (v1, v2, v3) for resubmissions
    """
    # Strict cross-intern isolation check upfront
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.intern_id != intern.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot submit deliverables for another intern's task."
        )

    content_type = request.headers.get("content-type", "")

    submission_link = None
    notes = None
    file = None

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        submission_link = form.get("submission_link")
        notes = form.get("notes")
        file_val = form.get("file")
        if hasattr(file_val, "filename") and getattr(file_val, "filename", None):
            file = file_val
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                submission_link = body.get("submission_link")
                notes = body.get("notes")
        except Exception:
            pass

    if not submission_link and not file and not notes:
        raise HTTPException(
            status_code=400,
            detail="Please provide at least a deliverable file upload or repository URL."
        )

    submission = submission_service.process_task_submission(
        task_id=task_id,
        intern=intern,
        submission_link=submission_link,
        notes=notes,
        file=file,
        db=db
    )

    return {
        "success": True,
        "message": f"Milestone deliverables submitted successfully (Version {submission.version}).",
        "submission_id": submission.id,
        "version": submission.version,
        "file_type": submission.file_type
    }

@router.get("/tasks/{task_id}/submissions")
def get_task_submission_versions(
    task_id: int,
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Returns version history of all submissions for a specific task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.intern_id != intern.id:
        raise HTTPException(status_code=403, detail="Forbidden.")

    subs = (
        db.query(Submission)
        .filter(Submission.task_id == task_id, Submission.intern_id == intern.id)
        .order_by(Submission.version.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "version": s.version,
            "is_latest": s.is_latest,
            "submission_link": s.submission_link,
            "file_path": s.file_path,
            "file_type": s.file_type,
            "notes": s.notes,
            "status": s.status,
            "submitted_at": s.submitted_at.isoformat()
        }
        for s in subs
    ]

@router.get("/submissions")
def get_intern_submissions(
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Returns the authenticated intern's submission and evaluation history."""
    subs = db.query(Submission).filter(Submission.intern_id == intern.id).order_by(Submission.submitted_at.desc()).all()
    results = []
    for s in subs:
        t = s.task
        e = s.evaluations[-1] if s.evaluations else None
        results.append({
            "id": s.id,
            "task_id": s.task_id,
            "task_title": t.title if t else "",
            "week_number": t.week_number if t else 1,
            "version": s.version,
            "submission_link": s.submission_link,
            "file_path": s.file_path,
            "notes": s.notes,
            "status": s.status,
            "submitted_at": s.submitted_at.isoformat(),
            "evaluation": {
                "score": e.score,
                "feedback": e.feedback,
                "strengths": e.strengths,
                "improvements": e.improvements,
                "final_status": e.final_status,
                "evaluated_at": e.evaluated_at.isoformat()
            } if e else None
        })
    return results

@router.get("/attendance")
def get_intern_attendance(
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Returns attendance records for authenticated intern."""
    records = db.query(Attendance).filter(Attendance.intern_id == intern.id).order_by(Attendance.date.desc()).all()
    return [
        {
            "id": r.id,
            "date": r.date.isoformat(),
            "status": r.status,
            "notes": r.notes
        }
        for r in records
    ]

@router.post("/attendance/check-in")
def intern_check_in_today(
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Intern logs daily attendance."""
    today = date.today()
    record = db.query(Attendance).filter(Attendance.intern_id == intern.id, Attendance.date == today).first()
    if record:
        return {"success": True, "message": "Attendance already confirmed for today.", "date": today.isoformat()}

    record = Attendance(
        intern_id=intern.id,
        date=today,
        status="present",
        notes="Intern daily portal check-in"
    )
    db.add(record)
    db.commit()
    return {"success": True, "message": "Daily check-in successful. Attendance recorded as Present.", "date": today.isoformat()}

@router.get("/meetings")
def get_intern_meetings(
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Returns upcoming review meetings scheduled for this intern."""
    meetings = db.query(Meeting).filter(Meeting.status != "cancelled").order_by(Meeting.scheduled_time.asc()).all()
    results = []
    for m in meetings:
        is_invited = False
        if m.intern_ids == "all":
            is_invited = True
        elif m.intern_ids:
            try:
                ids = json.loads(m.intern_ids)
                if intern.id in ids:
                    is_invited = True
            except Exception:
                pass
                
        if is_invited:
            results.append({
                "id": m.id,
                "title": m.title,
                "description": m.description,
                "meeting_type": m.meeting_type,
                "scheduled_time": m.scheduled_time.isoformat(),
                "duration_minutes": m.duration_minutes,
                "meeting_link": m.meeting_link,
                "google_meet_url": m.google_meet_url,
                "status": m.status
            })
    return results

@router.get("/certificate")
def get_intern_certificate(
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Returns certificate details or eligibility criteria."""
    from app.services.certificate_service import certificate_service

    cert = db.query(Certificate).filter(Certificate.intern_id == intern.id).first()
    if cert:
        return {
            "eligible": True,
            "issued": True,
            "certificate_number": cert.certificate_number,
            "issue_date": cert.issue_date.isoformat(),
            "grade": cert.grade,
            "verification_hash": cert.verification_hash,
            "domain": intern.domain,
            "name": intern.name,
            "download_url": f"/api/v1/certificates/{cert.certificate_number}/download"
        }

    total_tasks = len(intern.tasks)
    approved_tasks = sum(1 for t in intern.tasks if t.status == "approved")
    eligible = (total_tasks > 0 and approved_tasks == total_tasks) or intern.status == "completed"

    if eligible and not cert:
        try:
            cert = certificate_service.issue_certificate(intern.id, db, admin_override=True)
            return {
                "eligible": True,
                "issued": True,
                "certificate_number": cert.certificate_number,
                "issue_date": cert.issue_date.isoformat(),
                "grade": cert.grade,
                "verification_hash": cert.verification_hash,
                "domain": intern.domain,
                "name": intern.name,
                "download_url": f"/api/v1/certificates/{cert.certificate_number}/download"
            }
        except Exception as e:
            logger.error(f"Error generating certificate: {e}")

    return {
        "eligible": False,
        "issued": False,
        "message": f"Complete and receive approvals on all {total_tasks} weekly tasks to unlock your verified Certificate of Completion.",
        "tasks_completed": approved_tasks,
        "tasks_total": total_tasks
    }

@router.get("/notifications")
def get_intern_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Returns notifications for logged-in intern user."""
    notifs = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(20).all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.type,
            "is_read": n.is_read,
            "link": n.link,
            "created_at": n.created_at.isoformat()
        }
        for n in notifs
    ]

@router.get("/chat/history")
def get_intern_chat_history(
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Retrieves conversation history strictly isolated to this intern."""
    return intern_chat_service.get_conversation_history(intern.id, db)

@router.delete("/chat/history")
def clear_intern_chat_history(
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Clears previous conversation history to start a fresh discussion."""
    deleted_count = intern_chat_service.clear_conversation_history(intern.id, db)
    return {"success": True, "message": "Conversation history cleared.", "count": deleted_count}

@router.post("/chat")
def intern_ai_chat_assistant(
    data: dict,
    intern: Intern = Depends(get_current_intern_user),
    db: Session = Depends(get_db)
) -> Any:
    """Personalized AI Mentor chat assistant with full intern context memory."""
    user_msg = data.get("message", "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message is required.")

    return intern_chat_service.generate_mentor_response(user_msg, intern, db)
