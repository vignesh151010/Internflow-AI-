from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.schemas.task import TaskResponse

class RoadmapBase(BaseModel):
    week_number: int
    title: str
    theme: Optional[str] = None
    objectives: Optional[str] = None
    key_deliverables: Optional[str] = None
    estimated_hours: int = 20

class RoadmapCreate(RoadmapBase):
    intern_id: int

class RoadmapUpdate(BaseModel):
    title: Optional[str] = None
    theme: Optional[str] = None
    objectives: Optional[str] = None
    key_deliverables: Optional[str] = None
    estimated_hours: Optional[int] = None
    status: Optional[str] = None
    approved_by_admin: Optional[bool] = None

class RoadmapResponse(RoadmapBase):
    id: int
    intern_id: int
    ai_generated: bool
    status: str
    approved_by_admin: bool
    approved_at: Optional[datetime] = None
    created_at: datetime
    tasks: List[TaskResponse] = []

    class Config:
        from_attributes = True

class RoadmapGenerateRequest(BaseModel):
    intern_id: int
    model_name: Optional[str] = None
    force_regenerate: bool = False

