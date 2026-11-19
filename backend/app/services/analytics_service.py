from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.intern import Intern
from app.models.task import Task
from app.models.submission import Submission
from app.models.evaluation import Evaluation
from app.models.meeting import Meeting
from app.models.log import AuditLog
from app.schemas.analytics import AdminDashboardStats

def get_admin_dashboard_stats(db: Session) -> AdminDashboardStats:
    """Aggregates all real-time stats directly from SQLite database."""
    total_interns = db.query(Intern).count()
    active_interns = db.query(Intern).filter(Intern.status == "active").count()
    completed_interns = db.query(Intern).filter(Intern.status == "completed").count()

    total_tasks = db.query(Task).count()
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()
    submitted_tasks = db.query(Task).filter(Task.status.in_(["submitted", "in_review"])).count()
    
    # Submissions that have not been evaluated yet
    pending_reviews = (
        db.query(Submission)
        .outerjoin(Evaluation, Submission.id == Evaluation.submission_id)
        .filter(Evaluation.id == None)
        .count()
    )

    now = datetime.utcnow()
    upcoming_meetings = (
        db.query(Meeting)
        .filter(Meeting.scheduled_time >= now, Meeting.status == "scheduled")
        .count()
    )

    # Average score across all evaluations
    avg_score_res = db.query(func.avg(Evaluation.score)).scalar()
    average_score = round(float(avg_score_res), 1) if avg_score_res is not None else 0.0

    # Domain distribution
    domain_counts = (
        db.query(Intern.domain, func.count(Intern.id))
        .group_by(Intern.domain)
        .all()
    )
    domain_distribution: Dict[str, int] = {domain: count for domain, count in domain_counts}

    completion_rate = round((completed_interns / total_interns * 100), 1) if total_interns > 0 else 0.0

    # Recent activity stream
    recent_logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    activities = [
        {
            "id": log.id,
            "action": log.action,
            "entity": log.entity_type,
            "details": log.details,
            "timestamp": log.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for log in recent_logs
    ]

    return AdminDashboardStats(
        total_interns=total_interns,
        active_interns=active_interns,
        completed_interns=completed_interns,
        pending_tasks=pending_tasks,
        submitted_tasks=submitted_tasks,
        pending_reviews=pending_reviews,
        upcoming_meetings=upcoming_meetings,
        average_performance_score=average_score,
        domain_distribution=domain_distribution,
        internship_completion_rate=completion_rate,
        recent_activities=activities
    )

def get_advanced_admin_analytics(db: Session) -> Dict[str, Any]:
    """
    Computes comprehensive analytics across performance, submission turnaround,
    weekly progress, and identifies at-risk interns requiring mentor intervention.
    """
    now = datetime.utcnow()
    interns = db.query(Intern).all()

    # 1. At-Risk Interns Detection
    at_risk_interns = []
    performance_tiers = {"outstanding": 0, "proficient": 0, "needs_support": 0}

    for i in interns:
        risk_factors = []

        # Check overdue tasks
        overdue_count = 0
        for t in i.tasks:
            if t.status in ["pending", "needs_resubmission"] and t.deadline and t.deadline < now:
                overdue_count += 1
        if overdue_count > 0:
            risk_factors.append(f"{overdue_count} overdue milestone(s)")

        # Check low evaluation score
        if i.total_score > 0 and i.total_score < 60.0:
            risk_factors.append(f"Low evaluation average ({i.total_score}/100)")

        # Check active resubmission requirement
        resub_tasks = [t for t in i.tasks if t.status == "needs_resubmission"]
        if resub_tasks:
            risk_factors.append(f"{len(resub_tasks)} pending revision(s)")

        # Performance Tier classification
        if i.total_score >= 85.0:
            performance_tiers["outstanding"] += 1
        elif i.total_score >= 70.0:
            performance_tiers["proficient"] += 1
        else:
            performance_tiers["needs_support"] += 1

        if risk_factors and i.status == "active":
            at_risk_interns.append({
                "intern_id": i.id,
                "intern_code": i.intern_code,
                "name": i.name,
                "domain": i.domain,
                "current_week": i.current_week,
                "total_score": i.total_score,
                "risk_factors": risk_factors,
                "urgency": "High" if overdue_count > 1 or i.total_score < 50 else "Moderate"
            })

    # 2. Submission Delay Turnaround Analysis
    submissions = db.query(Submission).all()
    on_time_count = 0
    delayed_count = 0

    for s in submissions:
        task = s.task
        if task and task.deadline:
            if s.submitted_at <= task.deadline:
                on_time_count += 1
            else:
                delayed_count += 1
        else:
            on_time_count += 1

    total_subs = len(submissions)
    on_time_rate = round((on_time_count / total_subs * 100), 1) if total_subs > 0 else 100.0

    # 3. Weekly Progress Milestones
    total_tasks = db.query(Task).count()
    approved_tasks = db.query(Task).filter(Task.status == "approved").count()
    task_completion_rate = round((approved_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0

    # Week-by-week completion rates
    weekly_breakdown = {}
    for w in range(1, 5):
        w_tasks = db.query(Task).filter(Task.week_number == w).all()
        w_total = len(w_tasks)
        w_approved = sum(1 for t in w_tasks if t.status == "approved")
        weekly_breakdown[f"Week {w}"] = {
            "total": w_total,
            "approved": w_approved,
            "completion_percentage": round((w_approved / w_total * 100), 1) if w_total > 0 else 0.0
        }

    return {
        "at_risk_interns": at_risk_interns,
        "at_risk_count": len(at_risk_interns),
        "performance_tiers": performance_tiers,
        "task_completion_rate": task_completion_rate,
        "on_time_submission_rate": on_time_rate,
        "submission_breakdown": {
            "on_time": on_time_count,
            "delayed": delayed_count,
            "total": total_subs
        },
        "weekly_breakdown": weekly_breakdown
    }

