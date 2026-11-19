from typing import Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.intern import Intern
from app.models.roadmap import WeeklyRoadmap
from app.models.task import Task
from app.schemas.roadmap import RoadmapGenerateRequest, RoadmapUpdate
from app.schemas.task import TaskUpdate
from app.services.ollama_service import ollama_service

router = APIRouter()

@router.post("/generate")
def generate_roadmap(
    req: RoadmapGenerateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Generates personalized weekly roadmap for an intern using Ollama or Local AI."""
    intern = db.query(Intern).filter(Intern.id == req.intern_id).first()
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found.")
        
    roadmaps = ollama_service.create_roadmap_for_intern(
        intern=intern,
        db=db,
        model_name=req.model_name,
        force_regenerate=req.force_regenerate
    )
    
    return {
        "success": True,
        "intern_id": intern.id,
        "intern_name": intern.name,
        "weeks_count": len(roadmaps),
        "message": f"Successfully generated {len(roadmaps)} weekly roadmap milestones."
    }

@router.put("/{roadmap_id}/approve")
def approve_roadmap(
    roadmap_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Admin approves a roadmap."""
    roadmap = db.query(WeeklyRoadmap).filter(WeeklyRoadmap.id == roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap milestone not found.")
    
    roadmap.approved_by_admin = True
    roadmap.approved_at = datetime.utcnow()
    roadmap.status = "approved"
    db.commit()
    return {"message": "Roadmap approved successfully."}

@router.put("/{roadmap_id}")
def update_roadmap(
    roadmap_id: int,
    data: RoadmapUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Admin updates roadmap content."""
    roadmap = db.query(WeeklyRoadmap).filter(WeeklyRoadmap.id == roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap milestone not found.")
        
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(roadmap, field, val)
        
    db.commit()
    return {"message": "Roadmap updated successfully."}

@router.put("/tasks/{task_id}")
def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Admin updates task content or deadline."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
        
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(task, field, val)
        
    db.commit()
    return {"message": "Task updated successfully."}

