from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class TaskBase(BaseModel):
    title: str
    description: str
    instructions: Optional[str] = None
    technologies: Optional[str] = None
    expected_output: Optional[str] = None
    submission_requirements: Optional[str] = None
    evaluation_criteria: Optional[str] = None
    deadline: Optional[datetime] = None
    week_number: int = 1
    max_score: float = 100.0

class TaskCreate(TaskBase):
    intern_id: int
    roadmap_id: Optional[int] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    technologies: Optional[str] = None
    expected_output: Optional[str] = None
    submission_requirements: Optional[str] = None
    evaluation_criteria: Optional[str] = None
    deadline: Optional[datetime] = None
    status: Optional[str] = None
    max_score: Optional[float] = None

class SubmissionBase(BaseModel):
    submission_link: Optional[str] = None
    file_path: Optional[str] = None
    notes: Optional[str] = None

class SubmissionCreate(SubmissionBase):
    task_id: int

class SubmissionResponse(SubmissionBase):
    id: int
    task_id: int
    intern_id: int
    status: str
    submitted_at: datetime
    task_title: Optional[str] = None
    intern_name: Optional[str] = None
    intern_email: Optional[str] = None
    
    class Config:
        from_attributes = True

class EvaluationBase(BaseModel):
    score: float
    feedback: str
    strengths: Optional[str] = None
    improvements: Optional[str] = None

class EvaluationCreate(EvaluationBase):
    submission_id: int

class EvaluationResponse(EvaluationBase):
    id: int
    submission_id: int
    task_id: int
    intern_id: int
    evaluated_by: Optional[int] = None
    evaluated_at: datetime
    evaluator_name: Optional[str] = None

    class Config:
        from_attributes = True

class TaskResponse(TaskBase):
    id: int
    intern_id: int
    roadmap_id: Optional[int] = None
    status: str
    created_at: datetime
    latest_submission: Optional[SubmissionResponse] = None
    latest_evaluation: Optional[EvaluationResponse] = None

    class Config:
        from_attributes = True

