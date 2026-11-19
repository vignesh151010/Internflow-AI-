from typing import Dict, List, Any
from pydantic import BaseModel

class AdminDashboardStats(BaseModel):
    total_interns: int
    active_interns: int
    completed_interns: int
    pending_tasks: int
    submitted_tasks: int
    pending_reviews: int
    upcoming_meetings: int
    average_performance_score: float
    domain_distribution: Dict[str, int]
    internship_completion_rate: float
    recent_activities: List[Dict[str, Any]] = []

