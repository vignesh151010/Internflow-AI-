from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, EmailStr

class InternBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    domain: str
    main_task: str
    task_description: Optional[str] = None
    start_date: date
    duration_weeks: int = 4
    end_date: date

class InternCreate(InternBase):
    pass

class InternUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    domain: Optional[str] = None
    main_task: Optional[str] = None
    task_description: Optional[str] = None
    status: Optional[str] = None
    current_week: Optional[int] = None
    total_score: Optional[float] = None

class InternResponse(InternBase):
    id: int
    user_id: Optional[int] = None
    intern_code: str
    status: str
    current_week: int
    total_score: float
    is_invited: bool
    invitation_token: Optional[str] = None
    created_at: datetime
    
    # Computed metrics
    progress_percentage: float = 0.0
    tasks_count: int = 0
    completed_tasks_count: int = 0
    pending_tasks_count: int = 0

    class Config:
        from_attributes = True

class InternStats(BaseModel):
    total_tasks: int
    submitted_tasks: int
    approved_tasks: int
    pending_tasks: int
    progress_percentage: float
    average_score: float
    current_week: int
    total_weeks: int

