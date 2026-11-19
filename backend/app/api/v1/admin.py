from datetime import datetime, date
import json
import csv
import io
import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.intern import Intern
from app.models.task import Task
from app.models.submission import Submission
from app.models.evaluation import Evaluation
from app.models.meeting import Meeting
from app.models.attendance import Attendance
from app.models.notification import Notification
from app.models.log import AuditLog, EmailLog
from app.schemas.analytics import AdminDashboardStats
from app.schemas.intern import InternResponse, InternUpdate
from app.schemas.task import SubmissionResponse, EvaluationCreate, EvaluationResponse
from app.services.analytics_service import get_admin_dashboard_stats
from app.services.evaluation_service import evaluation_service
from app.services.email_service import email_service
from app.services.google_service import google_calendar_service
from app.services.ollama_service import ollama_service

router = APIRouter()

@router.get("/dashboard", response_model=AdminDashboardStats)
def get_dashboard(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Returns all admin dashboard analytics computed directly from SQLite database."""
    return get_admin_dashboard_stats(db)

@router.get("/interns", response_model=List[InternResponse])
def list_interns(
    domain: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Lists all interns with computed task completion metrics."""
    query = db.query(Intern)
    if domain:
        query = query.filter(Intern.domain == domain)
    if status_filter:
        query = query.filter(Intern.status == status_filter)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter((Intern.name.ilike(s)) | (Intern.email.ilike(s)) | (Intern.intern_code.ilike(s)))
        
    interns = query.order_by(Intern.created_at.desc()).all()
    results = []
    
    for i in interns:
        total_tasks = len(i.tasks)
        completed_tasks = sum(1 for t in i.tasks if t.status in ["approved", "evaluated"])
        pending_tasks = sum(1 for t in i.tasks if t.status == "pending")
        progress = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0
        
        resp = InternResponse(
            id=i.id,
            user_id=i.user_id,
            intern_code=i.intern_code,
            name=i.name,
            email=i.email,
            phone=i.phone,
            domain=i.domain,
            main_task=i.main_task,
            task_description=i.task_description,
            start_date=i.start_date,
            duration_weeks=i.duration_weeks,
            end_date=i.end_date,
            status=i.status,
            current_week=i.current_week,
            total_score=i.total_score,
            is_invited=i.is_invited,
            invitation_token=i.invitation_token,
            created_at=i.created_at,
            progress_percentage=progress,
            tasks_count=total_tasks,
            completed_tasks_count=completed_tasks,
            pending_tasks_count=pending_tasks
        )
        results.append(resp)
        
    return results

@router.get("/interns/{intern_id}")
def get_intern_details(
    intern_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Retrieves full details of a specific intern including roadmaps, tasks, and submissions."""
    intern = db.query(Intern).filter(Intern.id == intern_id).first()
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found.")
        
    roadmaps_data = []
    for r in intern.roadmaps:
        tasks_data = []
        for t in r.tasks:
            latest_sub = None
            if t.submissions:
                s = t.submissions[-1]
                latest_sub = {
                    "id": s.id,
                    "submission_link": s.submission_link,
                    "file_path": s.file_path,
                    "notes": s.notes,
                    "status": s.status,
                    "submitted_at": s.submitted_at.isoformat()
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
            "approved_by_admin": r.approved_by_admin,
            "tasks": tasks_data
        })
        
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
        "roadmaps": roadmaps_data
    }

@router.put("/interns/{intern_id}")
def update_intern(
    intern_id: int,
    data: InternUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Updates intern details."""
    intern = db.query(Intern).filter(Intern.id == intern_id).first()
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found.")
        
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(intern, field, val)
        
    db.commit()
    db.refresh(intern)
    return {"message": "Intern updated successfully.", "intern_id": intern.id}

@router.delete("/interns/{intern_id}")
def delete_intern(
    intern_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Removes an intern and associated data."""
    intern = db.query(Intern).filter(Intern.id == intern_id).first()
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found.")
    
    # Also delete linked user if exists
    if intern.user:
        db.delete(intern.user)
    db.delete(intern)
    db.commit()
    return {"message": "Intern deleted successfully."}

@router.get("/submissions")
def list_submissions(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Lists all intern submissions for review."""
    query = db.query(Submission)
    if status_filter:
        query = query.filter(Submission.status == status_filter)
    submissions = query.order_by(Submission.submitted_at.desc()).all()
    
    results = []
    for s in submissions:
        task = s.task
        intern = s.intern
        latest_eval = s.evaluations[-1] if s.evaluations else None
        
        results.append({
            "id": s.id,
            "task_id": s.task_id,
            "task_title": task.title if task else "Untitled Task",
            "week_number": task.week_number if task else 1,
            "intern_id": s.intern_id,
            "intern_name": intern.name if intern else "Unknown",
            "intern_email": intern.email if intern else "",
            "domain": intern.domain if intern else "",
            "version": s.version or 1,
            "submission_link": s.submission_link,
            "file_path": s.file_path,
            "file_type": s.file_type,
            "file_size_bytes": s.file_size_bytes,
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
        })
    return results

@router.post("/submissions/{submission_id}/ai-evaluate")
def run_ai_evaluation(
    submission_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Runs local Ollama AI evaluation on the submission and returns structured report."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")
        
    res = evaluation_service.evaluate_with_ai(submission, db)
    return res

@router.post("/submissions/{submission_id}/publish-evaluation")
def publish_evaluation_report(
    submission_id: int,
    eval_payload: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Saves reviewed evaluation into database and sends personalized email to intern."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")
        
    eval_record = evaluation_service.publish_evaluation(
        submission_id=submission.id,
        evaluation_data=eval_payload,
        evaluator_user_id=admin.id,
        db=db
    )

    # Automated Workflow Progression
    from app.services.automation_service import automation_service
    try:
        automation_service.advance_intern_workflow(
            intern_id=submission.intern_id,
            task_id=submission.task_id,
            evaluation=eval_record,
            db=db
        )
        automation_service.run_pending_jobs(db)
    except Exception as e:
        logger.error(f"Workflow progression error: {e}")

    return {
        "success": True,
        "evaluation_id": eval_record.id,
        "score": eval_record.score,
        "final_status": eval_record.final_status,
        "message": f"Evaluation published with score {eval_record.score}/100. Workflow automatically updated."
    }

@router.post("/submissions/{submission_id}/evaluate")
def evaluate_submission(
    submission_id: int,
    eval_data: EvaluationCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Scores an intern submission, updates task status and recalculates total performance."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")
        
    eval_payload = {
        "score": eval_data.score,
        "feedback_summary": eval_data.feedback,
        "strengths_summary": eval_data.strengths or "",
        "improvement_suggestions": [eval_data.improvements] if eval_data.improvements else [],
        "final_status": "approved" if eval_data.score >= 50.0 else "needs_resubmission"
    }
    
    eval_record = evaluation_service.publish_evaluation(
        submission_id=submission.id,
        evaluation_data=eval_payload,
        evaluator_user_id=admin.id,
        db=db
    )

    # Automated Workflow Progression
    from app.services.automation_service import automation_service
    try:
        automation_service.advance_intern_workflow(
            intern_id=submission.intern_id,
            task_id=submission.task_id,
            evaluation=eval_record,
            db=db
        )
        automation_service.run_pending_jobs(db)
    except Exception as e:
        logger.error(f"Workflow progression error: {e}")
    
    return {"message": "Evaluation recorded successfully.", "score": eval_record.score}

@router.get("/meetings")
def list_meetings(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Lists meetings."""
    meetings = db.query(Meeting).order_by(Meeting.scheduled_time.desc()).all()
    return [
        {
            "id": m.id,
            "title": m.title,
            "description": m.description,
            "meeting_type": m.meeting_type,
            "scheduled_time": m.scheduled_time.isoformat(),
            "duration_minutes": m.duration_minutes,
            "meeting_link": m.meeting_link,
            "status": m.status
        }
        for m in meetings
    ]

@router.post("/meetings")
def schedule_meeting(
    data: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Schedules a new meeting with interns."""
    sched_time = datetime.fromisoformat(data["scheduled_time"])
    meeting = Meeting(
        title=data["title"],
        description=data.get("description", ""),
        meeting_type=data.get("meeting_type", "weekly_sync"),
        scheduled_time=sched_time,
        duration_minutes=int(data.get("duration_minutes", 45)),
        meeting_link=data.get("meeting_link", "https://meet.internflow.local/sync"),
        host_admin_id=admin.id,
        intern_ids=data.get("intern_ids", "all"),
        status="scheduled"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return {"message": "Meeting scheduled successfully.", "id": meeting.id}

@router.get("/attendance")
def list_attendance(
    date_filter: Optional[str] = Query(None, alias="date"),
    intern_id: Optional[int] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Lists attendance records across all interns."""
    query = db.query(Attendance)
    if date_filter:
        try:
            d = datetime.strptime(date_filter, "%Y-%m-%d").date()
            query = query.filter(Attendance.date == d)
        except Exception:
            pass
    if intern_id:
        query = query.filter(Attendance.intern_id == intern_id)
        
    records = query.order_by(Attendance.date.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "intern_id": r.intern_id,
            "intern_name": r.intern.name if r.intern else "Unknown",
            "intern_code": r.intern.intern_code if r.intern else "",
            "date": r.date.isoformat(),
            "status": r.status,
            "notes": r.notes
        }
        for r in records
    ]

@router.post("/attendance/mark")
def mark_attendance(
    data: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Records or updates intern attendance."""
    intern_id = int(data["intern_id"])
    target_date = datetime.strptime(data.get("date", date.today().isoformat()), "%Y-%m-%d").date()
    status_val = data.get("status", "present")
    notes = data.get("notes", "Marked by Administrator")

    record = db.query(Attendance).filter(Attendance.intern_id == intern_id, Attendance.date == target_date).first()
    if record:
        record.status = status_val
        record.notes = notes
    else:
        record = Attendance(
            intern_id=intern_id,
            date=target_date,
            status=status_val,
            notes=notes
        )
        db.add(record)
    db.commit()
    return {"success": True, "message": f"Attendance recorded as {status_val} for {target_date}."}

@router.get("/integrations/status")
def get_integrations_status(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Returns consolidated integration monitoring status across all external connectors."""
    # 1. SMTP
    smtp_conn = email_service.test_connection()
    smtp_failed_count = db.query(EmailLog).filter(EmailLog.status == "FAILED").count()
    smtp_accepted_count = db.query(EmailLog).filter(EmailLog.status == "SMTP_ACCEPTED").count()

    # 2. Google OAuth
    google_status = google_calendar_service.get_status(db)

    # 3. Ollama Local AI
    ollama_conn = ollama_service.check_connection()

    # 4. Failed submissions / reviews needing action
    failed_evals = db.query(Evaluation).filter(Evaluation.final_status.in_(["needs_resubmission", "rejected"])).count()

    return {
        "smtp": {
            "configured": email_service.is_configured(),
            "status_text": smtp_conn["message"],
            "failed_count": smtp_failed_count,
            "accepted_count": smtp_accepted_count,
            "note": "SMTP acceptance does not guarantee inbox delivery."
        },
        "google_calendar": {
            "configured": google_status["configured"],
            "authorized": google_status["authorized"],
            "status_text": google_status["status_text"]
        },
        "ollama_ai": {
            "connected": ollama_conn["connected"],
            "status_text": ollama_conn["status_text"],
            "models": ollama_conn.get("available_models", []),
            "active_model": ollama_conn.get("active_model", "Domain Curriculum Engine")
        },
        "database": {
            "engine": "SQLite (Local On-Premise)",
            "status": "Online & Operational"
        },
        "pending_actions": {
            "needs_resubmission_count": failed_evals
        }
    }

@router.get("/interns/export")
def export_interns_csv(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Exports full intern roster, domains, milestones, and performance scores as CSV."""
    interns = db.query(Intern).order_by(Intern.intern_code.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Intern Code", "Name", "Email", "Domain", "Main Task",
        "Start Date", "Duration Weeks", "End Date", "Status", "Current Week", "Total Score"
    ])
    for i in interns:
        writer.writerow([
            i.intern_code, i.name, i.email, i.domain, i.main_task,
            i.start_date.isoformat(), i.duration_weeks, i.end_date.isoformat(),
            i.status, i.current_week, i.total_score
        ])
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=internflow_roster_{date.today().isoformat()}.csv"}
    )

@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Retrieves system audit trail."""
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": log.id,
            "action": log.action,
            "entity": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "created_at": log.created_at.isoformat()
        }
        for log in logs
    ]

