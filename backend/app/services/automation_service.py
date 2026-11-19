import os
import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.models.intern import Intern
from app.models.task import Task
from app.models.roadmap import WeeklyRoadmap
from app.models.submission import Submission
from app.models.evaluation import Evaluation
from app.models.meeting import Meeting
from app.models.log import AutomationJob, AuditLog
from app.models.setting import AppSetting
from app.services.email_service import email_service
from app.services.google_service import google_calendar_service
from app.services.ollama_service import ollama_service
from app.services.certificate_service import certificate_service

logger = logging.getLogger(__name__)

SETTING_KEY_AUTOMATION_SCHEDULE = "automation_schedule_config"

DEFAULT_AUTOMATION_SCHEDULE = {
    "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "review_day": "Sunday",
    "review_time": "16:00",
    "submission_deadline_day_offset": 6,
    "task_reminder_day_offset": 5,
    "deadline_reminder_day_offset": 6,
    "resubmission_extension_days": 2,
    "timezone": "UTC",
    "auto_advance_on_approval": True,
    "auto_evaluate_on_submit": True,
    "max_job_retries": 3,
    "retry_backoff_base_seconds": 60
}

class AutomationService:
    def get_schedule_config(self, db: Session) -> Dict[str, Any]:
        """Retrieves configurable automation schedule from SQLite settings or returns defaults."""
        setting = db.query(AppSetting).filter(AppSetting.key == SETTING_KEY_AUTOMATION_SCHEDULE).first()
        if setting and setting.value:
            try:
                stored = json.loads(setting.value)
                merged = {**DEFAULT_AUTOMATION_SCHEDULE, **stored}
                return merged
            except Exception:
                pass
        return DEFAULT_AUTOMATION_SCHEDULE.copy()

    def update_schedule_config(self, new_config: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Updates automation schedule configuration in SQLite database."""
        current = self.get_schedule_config(db)
        updated = {**current, **new_config}

        setting = db.query(AppSetting).filter(AppSetting.key == SETTING_KEY_AUTOMATION_SCHEDULE).first()
        if not setting:
            setting = AppSetting(
                key=SETTING_KEY_AUTOMATION_SCHEDULE,
                value=json.dumps(updated, indent=2),
                description="Configurable timing parameters for internship lifecycle automation"
            )
            db.add(setting)
        else:
            setting.value = json.dumps(updated, indent=2)

        db.commit()
        return updated

    def enqueue_job(
        self,
        job_type: str,
        intern_id: Optional[int],
        scheduled_at: datetime,
        payload: Dict[str, Any],
        idempotency_key: str,
        db: Session,
        max_retries: int = 3
    ) -> Optional[AutomationJob]:
        """
        Enqueues a database-backed job with strict duplicate prevention and idempotency.
        """
        # Duplicate prevention check
        existing = (
            db.query(AutomationJob)
            .filter(AutomationJob.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            logger.info(f"Job with idempotency key '{idempotency_key}' already exists (status={existing.status}). Skipping.")
            return existing

        job = AutomationJob(
            intern_id=intern_id,
            workflow_id=f"workflow_intern_{intern_id}" if intern_id else "global_system_workflow",
            job_type=job_type,
            status="pending",
            scheduled_at=scheduled_at,
            max_retries=max_retries,
            idempotency_key=idempotency_key,
            payload=json.dumps(payload),
            created_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def initialize_intern_workflow(self, intern_id: int, db: Session) -> List[AutomationJob]:
        """
        Initializes the complete automated lifecycle for an intern upon admin approval:
        1. Welcome email
        2. AI Roadmap generation
        3. Week 1 Task assignment
        4. Week 1 Task assignment email
        5. Review meeting scheduling & Meet link generation
        6. Meeting invite email
        7. Submission reminders
        """
        intern = db.query(Intern).filter(Intern.id == intern_id).first()
        if not intern:
            raise ValueError(f"Intern ID {intern_id} not found.")

        cfg = self.get_schedule_config(db)
        now = datetime.utcnow()
        created_jobs = []

        intern.workflow_status = "active"
        intern.workflow_paused = False
        db.commit()

        # Job 1: Send Welcome Email immediately
        j1 = self.enqueue_job(
            job_type="send_welcome_email",
            intern_id=intern.id,
            scheduled_at=now,
            payload={"intern_id": intern.id, "email": intern.email, "name": intern.name},
            idempotency_key=f"WELCOME:{intern.id}:{intern.email}",
            db=db
        )
        if j1: created_jobs.append(j1)

        # Job 2: Generate personalized AI Roadmap immediately
        j2 = self.enqueue_job(
            job_type="generate_roadmap",
            intern_id=intern.id,
            scheduled_at=now,
            payload={"intern_id": intern.id, "domain": intern.domain, "main_task": intern.main_task},
            idempotency_key=f"ROADMAP:{intern.id}",
            db=db
        )
        if j2: created_jobs.append(j2)

        # Job 3: Assign Week 1 Milestone Task
        j3 = self.enqueue_job(
            job_type="assign_weekly_task",
            intern_id=intern.id,
            scheduled_at=now,
            payload={"intern_id": intern.id, "week_number": 1},
            idempotency_key=f"ASSIGN_TASK:{intern.id}:WEEK_1",
            db=db
        )
        if j3: created_jobs.append(j3)

        # Job 4: Send Week 1 Task Assignment Email
        j4 = self.enqueue_job(
            job_type="send_task_assignment_email",
            intern_id=intern.id,
            scheduled_at=now,
            payload={"intern_id": intern.id, "week_number": 1},
            idempotency_key=f"TASK_EMAIL:{intern.id}:WEEK_1",
            db=db
        )
        if j4: created_jobs.append(j4)

        # Job 5: Schedule Week 1 Review Meeting with Google Meet
        review_date = now + timedelta(days=cfg.get("submission_deadline_day_offset", 6))
        j5 = self.enqueue_job(
            job_type="schedule_review_meeting",
            intern_id=intern.id,
            scheduled_at=now,
            payload={"intern_id": intern.id, "week_number": 1, "meeting_time": review_date.isoformat()},
            idempotency_key=f"MEETING:{intern.id}:WEEK_1",
            db=db
        )
        if j5: created_jobs.append(j5)

        # Job 6: Send Task Deadline Reminder
        reminder_date = now + timedelta(days=cfg.get("task_reminder_day_offset", 5))
        j6 = self.enqueue_job(
            job_type="send_deadline_reminder",
            intern_id=intern.id,
            scheduled_at=reminder_date,
            payload={"intern_id": intern.id, "week_number": 1},
            idempotency_key=f"REMINDER:{intern.id}:WEEK_1",
            db=db
        )
        if j6: created_jobs.append(j6)

        logger.info(f"Initialized automated lifecycle for {intern.name} ({len(created_jobs)} jobs enqueued).")
        return created_jobs

    def advance_intern_workflow(
        self,
        intern_id: int,
        task_id: int,
        evaluation: Evaluation,
        db: Session
    ) -> List[AutomationJob]:
        """
        Executes automated workflow progression following mentor or AI evaluation:
        - If approved and more weeks remain: unlocks next week, schedules next meeting and reminders.
        - If approved and final week completed: marks completed, triggers certificate generation & appreciation email.
        - If not approved: enqueues feedback explanation, extends deadline, and awaits resubmission.
        """
        intern = db.query(Intern).filter(Intern.id == intern_id).first()
        task = db.query(Task).filter(Task.id == task_id).first()
        if not intern or not task:
            return []

        cfg = self.get_schedule_config(db)
        now = datetime.utcnow()
        enqueued = []

        is_approved = evaluation.final_status == "approved" or evaluation.score >= 50.0

        if is_approved:
            current_week = task.week_number
            next_week = current_week + 1

            if next_week <= intern.duration_weeks:
                # Progress to Next Week
                intern.current_week = next_week
                db.commit()

                # 1. Unlock next milestone task
                j1 = self.enqueue_job(
                    job_type="assign_weekly_task",
                    intern_id=intern.id,
                    scheduled_at=now,
                    payload={"intern_id": intern.id, "week_number": next_week},
                    idempotency_key=f"ASSIGN_TASK:{intern.id}:WEEK_{next_week}",
                    db=db
                )
                if j1: enqueued.append(j1)

                # 2. Send Next-Week Assignment Email
                j2 = self.enqueue_job(
                    job_type="send_task_assignment_email",
                    intern_id=intern.id,
                    scheduled_at=now,
                    payload={"intern_id": intern.id, "week_number": next_week},
                    idempotency_key=f"TASK_EMAIL:{intern.id}:WEEK_{next_week}",
                    db=db
                )
                if j2: enqueued.append(j2)

                # 3. Schedule next review meeting with Google Meet
                review_date = now + timedelta(days=cfg.get("submission_deadline_day_offset", 6))
                j3 = self.enqueue_job(
                    job_type="schedule_review_meeting",
                    intern_id=intern.id,
                    scheduled_at=now,
                    payload={"intern_id": intern.id, "week_number": next_week, "meeting_time": review_date.isoformat()},
                    idempotency_key=f"MEETING:{intern.id}:WEEK_{next_week}",
                    db=db
                )
                if j3: enqueued.append(j3)

                # 4. Schedule next deadline reminder
                reminder_date = now + timedelta(days=cfg.get("task_reminder_day_offset", 5))
                j4 = self.enqueue_job(
                    job_type="send_deadline_reminder",
                    intern_id=intern.id,
                    scheduled_at=reminder_date,
                    payload={"intern_id": intern.id, "week_number": next_week},
                    idempotency_key=f"REMINDER:{intern.id}:WEEK_{next_week}",
                    db=db
                )
                if j4: enqueued.append(j4)

            else:
                # Final Milestone Approved -> Internship Completed!
                intern.status = "completed"
                intern.workflow_status = "completed"
                db.commit()

                # 1. Generate Verified PDF Certificate with QR code
                j_cert = self.enqueue_job(
                    job_type="generate_pdf_certificate",
                    intern_id=intern.id,
                    scheduled_at=now,
                    payload={"intern_id": intern.id},
                    idempotency_key=f"CERTIFICATE:{intern.id}",
                    db=db
                )
                if j_cert: enqueued.append(j_cert)

                # 2. Dispatch Certificate Delivery Email with attached PDF
                j_cert_mail = self.enqueue_job(
                    job_type="send_certificate_email",
                    intern_id=intern.id,
                    scheduled_at=now + timedelta(seconds=10),
                    payload={"intern_id": intern.id},
                    idempotency_key=f"CERT_MAIL:{intern.id}",
                    db=db
                )
                if j_cert_mail: enqueued.append(j_cert_mail)

                # 3. Dispatch Final Letter of Appreciation & Career Recommendations
                j_apprec = self.enqueue_job(
                    job_type="send_final_appreciation_email",
                    intern_id=intern.id,
                    scheduled_at=now + timedelta(seconds=20),
                    payload={"intern_id": intern.id},
                    idempotency_key=f"APPRECIATION:{intern.id}",
                    db=db
                )
                if j_apprec: enqueued.append(j_apprec)

        else:
            # Resubmission Required
            task.status = "needs_resubmission"
            extension_days = cfg.get("resubmission_extension_days", 2)
            if task.deadline:
                task.deadline = task.deadline + timedelta(days=extension_days)
            else:
                task.deadline = now + timedelta(days=extension_days)
            db.commit()

            # Enqueue Resubmission Notification Email
            j_resub = self.enqueue_job(
                job_type="send_resubmission_notification",
                intern_id=intern.id,
                scheduled_at=now,
                payload={
                    "intern_id": intern.id,
                    "task_id": task.id,
                    "corrections": evaluation.improvements or evaluation.feedback
                },
                idempotency_key=f"RESUB_NOTIF:{intern.id}:{task.id}:{datetime.utcnow().strftime('%Y%m%d%H%M')}",
                db=db
            )
            if j_resub: enqueued.append(j_resub)

        return enqueued

    def execute_job(self, job: AutomationJob, db: Session) -> Dict[str, Any]:
        """
        Executes a single persistent database job with error handling and logging.
        """
        job.status = "running"
        job.last_attempt_at = datetime.utcnow()
        db.commit()

        payload = json.loads(job.payload or "{}")
        intern_id = job.intern_id
        intern = db.query(Intern).filter(Intern.id == intern_id).first() if intern_id else None

        result = {}
        try:
            # 1. Welcome Email
            if job.job_type == "send_welcome_email":
                if intern:
                    res = email_service.send_email(
                        recipient_email=intern.email,
                        email_type="welcome",
                        intern=intern,
                        context_data={"name": intern.name, "domain": intern.domain, "main_task": intern.main_task},
                        db=db
                    )
                    result = res

            # 2. Generate Roadmap
            elif job.job_type == "generate_roadmap":
                if intern and not intern.roadmaps:
                    weeks_data = ollama_service.generate_weekly_roadmap(
                        domain=intern.domain,
                        main_task=intern.main_task,
                        task_description=intern.task_description or "",
                        duration_weeks=intern.duration_weeks
                    )
                    for w in weeks_data:
                        roadmap = WeeklyRoadmap(
                            intern_id=intern.id,
                            week_number=w.get("week_number", 1),
                            title=w.get("title", f"Week {w.get('week_number', 1)} Focus"),
                            theme=w.get("theme", intern.domain),
                            objectives=w.get("objectives", ""),
                            key_deliverables=w.get("key_deliverables", ""),
                            estimated_hours=w.get("estimated_hours", 20),
                            status="approved"
                        )
                        db.add(roadmap)
                        db.flush()

                        for t in w.get("tasks", []):
                            deadline_dt = datetime.utcnow() + timedelta(days=w.get("week_number", 1) * 7 - 1)
                            task_obj = Task(
                                intern_id=intern.id,
                                roadmap_id=roadmap.id,
                                week_number=w.get("week_number", 1),
                                title=t.get("title", "Milestone Task"),
                                description=t.get("description", ""),
                                instructions=t.get("instructions", ""),
                                technologies=t.get("technologies", intern.domain),
                                expected_output=t.get("expected_output", ""),
                                submission_requirements=t.get("submission_requirements", ""),
                                evaluation_criteria=t.get("evaluation_criteria", ""),
                                deadline=deadline_dt,
                                status="pending"
                            )
                            db.add(task_obj)
                    db.commit()
                    result = {"roadmaps_created": len(weeks_data)}

            # 3. Assign Weekly Task
            elif job.job_type == "assign_weekly_task":
                week_num = payload.get("week_number", 1)
                task = db.query(Task).filter(Task.intern_id == intern_id, Task.week_number == week_num).first()
                if task:
                    task.status = "pending"
                    db.commit()
                    result = {"task_id": task.id, "week_number": week_num, "status": "assigned"}

            # 4. Send Task Assignment Email
            elif job.job_type == "send_task_assignment_email":
                week_num = payload.get("week_number", 1)
                task = db.query(Task).filter(Task.intern_id == intern_id, Task.week_number == week_num).first()
                if intern and task:
                    res = email_service.send_email(
                        recipient_email=intern.email,
                        email_type="weekly_task_assignment",
                        intern=intern,
                        context_data={
                            "week_number": week_num,
                            "task_title": task.title,
                            "task_description": task.description,
                            "deadline": task.deadline.isoformat() if task.deadline else "Sunday 23:59"
                        },
                        db=db
                    )
                    result = res

            # 5. Schedule Review Meeting with Google Meet
            elif job.job_type == "schedule_review_meeting":
                week_num = payload.get("week_number", 1)
                mtg_time_str = payload.get("meeting_time")
                mtg_time = datetime.fromisoformat(mtg_time_str) if mtg_time_str else (datetime.utcnow() + timedelta(days=6))

                existing_mtg = db.query(Meeting).filter(
                    Meeting.intern_ids.contains(str(intern_id)),
                    Meeting.title.contains(f"Week {week_num}")
                ).first()

                if not existing_mtg and intern:
                    mtg = Meeting(
                        title=f"Week {week_num} Technical Progress Review — {intern.name}",
                        description=f"Sprint review and code evaluation for milestone week {week_num}.",
                        meeting_type="review",
                        scheduled_time=mtg_time,
                        duration_minutes=30,
                        intern_ids=json.dumps([intern.id]),
                        status="scheduled"
                    )
                    db.add(mtg)
                    db.commit()
                    db.refresh(mtg)

                    # Trigger genuine Google Calendar & Meet generation
                    g_res = google_calendar_service.create_meeting_event(
                        meeting=mtg,
                        attendee_emails=[intern.email],
                        db=db
                    )

                    # Send meeting invite email
                    email_service.send_email(
                        recipient_email=intern.email,
                        email_type="review_meeting_invitation",
                        intern=intern,
                        context_data={
                            "meeting_title": mtg.title,
                            "scheduled_time": mtg.scheduled_time.strftime("%A, %b %d, %Y at %I:%M %p"),
                            "duration_minutes": mtg.duration_minutes,
                            "meeting_link": mtg.google_meet_url or "Link updated in portal"
                        },
                        db=db
                    )
                    result = {"meeting_id": mtg.id, "google_synced": g_res.get("google_synced", False)}

            # 6. Send Deadline Reminder
            elif job.job_type == "send_deadline_reminder":
                week_num = payload.get("week_number", 1)
                task = db.query(Task).filter(Task.intern_id == intern_id, Task.week_number == week_num).first()
                if intern and task and task.status == "pending":
                    res = email_service.send_email(
                        recipient_email=intern.email,
                        email_type="task_deadline_reminder",
                        intern=intern,
                        context_data={
                            "task_title": task.title,
                            "deadline": task.deadline.isoformat() if task.deadline else "Upcoming Sunday"
                        },
                        db=db
                    )
                    result = res
                else:
                    result = {"skipped": True, "reason": "Task already submitted or approved."}

            # 7. Send Resubmission Notification
            elif job.job_type == "send_resubmission_notification":
                task_id = payload.get("task_id")
                task = db.query(Task).filter(Task.id == task_id).first()
                if intern and task:
                    res = email_service.send_email(
                        recipient_email=intern.email,
                        email_type="resubmission_notification",
                        intern=intern,
                        context_data={
                            "task_title": task.title,
                            "corrections": payload.get("corrections", "Please update your deliverable as discussed.")
                        },
                        db=db
                    )
                    result = res

            # 8. Generate PDF Certificate
            elif job.job_type == "generate_pdf_certificate":
                if intern:
                    cert = certificate_service.issue_certificate(intern.id, db, admin_override=True)
                    result = {
                        "certificate_number": cert.certificate_number,
                        "file_path": cert.file_path,
                        "verification_hash": cert.verification_hash
                    }

            # 9. Send Certificate Email
            elif job.job_type == "send_certificate_email":
                if intern and intern.certificate:
                    res = email_service.send_email(
                        recipient_email=intern.email,
                        email_type="certificate_delivery",
                        intern=intern,
                        context_data={
                            "certificate_number": intern.certificate.certificate_number,
                            "verification_hash": intern.certificate.verification_hash,
                            "grade": intern.certificate.grade,
                            "total_score": intern.total_score
                        },
                        attachment_path=intern.certificate.file_path,
                        db=db
                    )
                    result = res

            # 10. Send Final Appreciation Email
            elif job.job_type == "send_final_appreciation_email":
                if intern:
                    res = email_service.send_email(
                        recipient_email=intern.email,
                        email_type="final_appreciation",
                        intern=intern,
                        context_data={
                            "name": intern.name,
                            "domain": intern.domain,
                            "main_task": intern.main_task,
                            "total_score": intern.total_score,
                            "grade": intern.certificate.grade if intern.certificate else "Outstanding",
                            "completed_milestones": f"{len(intern.tasks)} Milestones Certified"
                        },
                        db=db
                    )
                    result = res

            else:
                result = {"note": f"Handled generic automation job {job.job_type}"}

            job.status = "completed"
            job.finished_at = datetime.utcnow()
            job.result = json.dumps(result)
            job.error_message = None
            db.commit()
            return {"success": True, "job_id": job.id, "result": result}

        except Exception as e:
            logger.error(f"Error executing automation job #{job.id} ({job.job_type}): {e}")
            job.retry_count += 1
            job.error_message = str(e)

            if job.retry_count < job.max_retries:
                # Exponential backoff
                backoff_secs = 60 * (2 ** (job.retry_count - 1))
                job.scheduled_at = datetime.utcnow() + timedelta(seconds=backoff_secs)
                job.status = "pending"
            else:
                job.status = "failed"
                job.finished_at = datetime.utcnow()

            db.commit()
            return {"success": False, "job_id": job.id, "error": str(e)}

    def run_pending_jobs(self, db: Session, max_jobs: int = 25) -> Dict[str, Any]:
        """
        Executes eligible pending jobs in chronological order.
        Respects paused workflows and enforces recovery of missed tasks.
        """
        now = datetime.utcnow()
        pending_jobs = (
            db.query(AutomationJob)
            .filter(
                AutomationJob.status == "pending",
                AutomationJob.scheduled_at <= now
            )
            .order_by(AutomationJob.scheduled_at.asc())
            .limit(max_jobs)
            .all()
        )

        executed_count = 0
        failed_count = 0
        skipped_count = 0

        for job in pending_jobs:
            # Check if intern workflow is paused
            if job.intern_id:
                intern = db.query(Intern).filter(Intern.id == job.intern_id).first()
                if intern and (intern.workflow_paused or intern.workflow_status == "paused"):
                    skipped_count += 1
                    continue

            res = self.execute_job(job, db)
            if res.get("success"):
                executed_count += 1
            else:
                failed_count += 1

        return {
            "processed": len(pending_jobs),
            "executed": executed_count,
            "failed": failed_count,
            "skipped_paused": skipped_count,
            "timestamp": now.isoformat()
        }

    def recover_missed_jobs(self, db: Session) -> Dict[str, Any]:
        """
        Executed on application startup to safely recover missed jobs due to laptop shutdown.
        Recovers jobs stuck in 'running' state and reschedules past-due pending jobs.
        """
        now = datetime.utcnow()

        # Reset interrupted 'running' jobs back to 'pending'
        stuck_jobs = db.query(AutomationJob).filter(AutomationJob.status == "running").all()
        for j in stuck_jobs:
            j.status = "pending"
            j.error_message = "Recovered after unexpected process termination / restart."

        # Count past-due pending jobs
        missed_count = db.query(AutomationJob).filter(
            AutomationJob.status == "pending",
            AutomationJob.scheduled_at <= now
        ).count()

        db.commit()

        if stuck_jobs or missed_count > 0:
            audit = AuditLog(
                action="RECOVERY_MISSED_JOBS",
                entity_type="automation_system",
                details=f"Restart recovery executed: {len(stuck_jobs)} interrupted jobs reset, {missed_count} past-due jobs queued for dispatch."
            )
            db.add(audit)
            db.commit()

        return {
            "recovered_stuck_count": len(stuck_jobs),
            "missed_past_due_count": missed_count,
            "status": "Ready"
        }

    def pause_workflow(self, intern_id: int, db: Session) -> bool:
        """Pauses automated progression for an individual intern."""
        intern = db.query(Intern).filter(Intern.id == intern_id).first()
        if not intern:
            return False
        intern.workflow_status = "paused"
        intern.workflow_paused = True
        db.commit()
        return True

    def resume_workflow(self, intern_id: int, db: Session) -> bool:
        """Resumes automated progression for an individual intern."""
        intern = db.query(Intern).filter(Intern.id == intern_id).first()
        if not intern:
            return False
        intern.workflow_status = "active"
        intern.workflow_paused = False
        db.commit()
        return True

    def cancel_workflow(self, intern_id: int, db: Session) -> bool:
        """Cancels an intern's active workflow and pending automation jobs."""
        intern = db.query(Intern).filter(Intern.id == intern_id).first()
        if not intern:
            return False
        intern.workflow_status = "cancelled"
        intern.workflow_paused = True

        # Cancel pending jobs
        db.query(AutomationJob).filter(
            AutomationJob.intern_id == intern.id,
            AutomationJob.status == "pending"
        ).update({"status": "cancelled"})

        db.commit()
        return True

    def retry_job(self, job_id: int, db: Session) -> Dict[str, Any]:
        """Manually retries a failed or pending automation job immediately."""
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if not job:
            return {"success": False, "error": "Job not found."}

        job.status = "pending"
        job.scheduled_at = datetime.utcnow()
        db.commit()
        return self.execute_job(job, db)

    def get_automation_overview(self, db: Session) -> Dict[str, Any]:
        """Returns consolidated metrics for the Automation Control Center."""
        total_workflows = db.query(Intern).count()
        active_workflows = db.query(Intern).filter(Intern.workflow_status == "active").count()
        completed_workflows = db.query(Intern).filter(Intern.workflow_status == "completed").count()
        paused_workflows = db.query(Intern).filter(Intern.workflow_status == "paused").count()

        pending_jobs = db.query(AutomationJob).filter(AutomationJob.status == "pending").count()
        completed_jobs = db.query(AutomationJob).filter(AutomationJob.status == "completed").count()
        failed_jobs = db.query(AutomationJob).filter(AutomationJob.status == "failed").count()

        next_job = (
            db.query(AutomationJob)
            .filter(AutomationJob.status == "pending")
            .order_by(AutomationJob.scheduled_at.asc())
            .first()
        )

        last_executed_job = (
            db.query(AutomationJob)
            .filter(AutomationJob.status == "completed")
            .order_by(AutomationJob.finished_at.desc())
            .first()
        )

        return {
            "workflows": {
                "total": total_workflows,
                "active": active_workflows,
                "completed": completed_workflows,
                "paused": paused_workflows
            },
            "jobs": {
                "pending": pending_jobs,
                "completed": completed_jobs,
                "failed": failed_jobs
            },
            "next_execution": next_job.scheduled_at.isoformat() if next_job else None,
            "next_job_type": next_job.job_type if next_job else None,
            "last_execution": last_executed_job.finished_at.isoformat() if last_executed_job else None,
            "last_job_type": last_executed_job.job_type if last_executed_job else None
        }

automation_service = AutomationService()

