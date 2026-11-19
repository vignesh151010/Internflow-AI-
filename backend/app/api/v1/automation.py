from typing import Any, Optional, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.log import AutomationJob
from app.services.automation_service import automation_service
from app.services.analytics_service import get_advanced_admin_analytics

router = APIRouter()

@router.get("/status")
def get_automation_status(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Returns real-time status metrics for the Automation Control Center."""
    return automation_service.get_automation_overview(db)

@router.get("/jobs")
def list_automation_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    intern_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Lists persistent database-backed automation jobs with filtering."""
    query = db.query(AutomationJob)
    if status_filter:
        query = query.filter(AutomationJob.status == status_filter)
    if intern_id:
        query = query.filter(AutomationJob.intern_id == intern_id)
        
    jobs = query.order_by(AutomationJob.scheduled_at.desc()).limit(limit).all()
    return [
        {
            "id": j.id,
            "intern_id": j.intern_id,
            "intern_name": j.intern.name if j.intern else None,
            "workflow_id": j.workflow_id,
            "job_type": j.job_type,
            "status": j.status,
            "scheduled_at": j.scheduled_at.isoformat() if j.scheduled_at else None,
            "last_attempt_at": j.last_attempt_at.isoformat() if j.last_attempt_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "retry_count": j.retry_count,
            "max_retries": j.max_retries,
            "error_message": j.error_message,
            "created_at": j.created_at.isoformat()
        }
        for j in jobs
    ]

@router.post("/jobs/{job_id}/retry")
def retry_automation_job(
    job_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Forces an immediate retry of a failed or pending automation job."""
    res = automation_service.retry_job(job_id, db)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Job execution failed."))
    return res

@router.post("/run-pending")
def trigger_pending_jobs(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Manually triggers execution of all currently eligible pending automation jobs."""
    return automation_service.run_pending_jobs(db)

@router.post("/workflows/{intern_id}/pause")
def pause_intern_workflow(
    intern_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Pauses automated progression for an individual intern."""
    success = automation_service.pause_workflow(intern_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Intern not found.")
    return {"success": True, "message": f"Workflow paused for Intern ID {intern_id}."}

@router.post("/workflows/{intern_id}/resume")
def resume_intern_workflow(
    intern_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Resumes automated progression for an individual intern."""
    success = automation_service.resume_workflow(intern_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Intern not found.")
    return {"success": True, "message": f"Workflow resumed for Intern ID {intern_id}."}

@router.post("/workflows/{intern_id}/cancel")
def cancel_intern_workflow(
    intern_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Cancels automated progression and pending jobs for an individual intern."""
    success = automation_service.cancel_workflow(intern_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Intern not found.")
    return {"success": True, "message": f"Workflow cancelled for Intern ID {intern_id}."}

@router.get("/settings")
def get_automation_schedule_settings(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Retrieves configurable automation schedule parameters."""
    return automation_service.get_schedule_config(db)

@router.put("/settings")
def update_automation_schedule_settings(
    config_data: Dict[str, Any],
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Updates configurable automation schedule parameters."""
    return automation_service.update_schedule_config(config_data, db)

@router.get("/analytics/advanced")
def get_advanced_analytics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Retrieves deep analytics including at-risk intern alerts and submission delay stats."""
    return get_advanced_admin_analytics(db)

