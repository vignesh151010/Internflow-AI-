import os
import smtplib
import ssl
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.log import EmailLog
from app.models.intern import Intern

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.reload_config()

    def reload_config(self):
        """Reloads SMTP credentials from .env to ensure fresh credentials are used."""
        try:
            from dotenv import load_dotenv
            env_file = settings.BASE_DIR / ".env"
            if env_file.exists():
                load_dotenv(env_file, override=True)
        except Exception:
            pass
        self.server_host = os.getenv("SMTP_SERVER", settings.SMTP_SERVER)
        self.port = int(os.getenv("SMTP_PORT", str(settings.SMTP_PORT)))
        self.email = os.getenv("SMTP_EMAIL", settings.SMTP_EMAIL)
        self.password = os.getenv("SMTP_PASSWORD", settings.SMTP_PASSWORD)
        self.from_name = os.getenv("SMTP_FROM_NAME", settings.SMTP_FROM_NAME)

    def is_configured(self) -> bool:
        """Checks if SMTP credentials are fully provided in .env."""
        self.reload_config()
        return bool(self.email and self.password and self.email.strip() and self.password.strip())

    def test_connection(self) -> Dict[str, Any]:
        """Tests genuine SMTP handshake and authentication with Gmail / SMTP server."""
        if not self.is_configured():
            return {
                "success": False,
                "configured": False,
                "message": "SMTP credentials not configured in .env (SMTP_EMAIL and SMTP_PASSWORD required). Emails will be logged locally as QUEUED or FAILED."
            }

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.server_host, self.port, timeout=10) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self.email, self.password)
                return {
                    "success": True,
                    "configured": True,
                    "message": f"SMTP handshake & authentication successful with {self.server_host}:{self.port} as {self.email}."
                }
        except Exception as e:
            logger.error(f"SMTP Connection Test failed: {e}")
            return {
                "success": False,
                "configured": True,
                "message": f"SMTP connection error: {str(e)}"
            }

    def compute_idempotency_hash(self, recipient: str, subject: str, email_type: str, intern_id: Optional[int]) -> str:
        """Computes a deterministic hash to prevent accidental duplicate sends."""
        data = f"{recipient.strip().lower()}:{subject.strip()}:{email_type}:{intern_id or 0}"
        return hashlib.sha256(data.encode()).hexdigest()

    def generate_html_template(
        self,
        email_type: str,
        intern: Optional[Intern],
        context_data: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Renders 13 professional, responsive HTML email templates personalized for the intern.
        Returns: (subject, html_content)
        """
        intern_name = intern.name if intern else context_data.get("name", "Intern")
        domain = intern.domain if intern else context_data.get("domain", "Engineering")
        main_task = intern.main_task if intern else context_data.get("main_task", "Capstone Project")
        intern_code = intern.intern_code if intern else context_data.get("intern_code", "IF-2026")

        base_head = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8FAFC; margin: 0; padding: 24px; color: #0F172A; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #1E3A8A, #2563EB); color: #FFFFFF; padding: 28px; text-align: center; }}
            .badge {{ display: inline-block; background: #F97316; color: #FFFFFF; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 12px; text-transform: uppercase; margin-bottom: 8px; }}
            .content {{ padding: 28px; line-height: 1.6; font-size: 14.5px; }}
            .card {{ background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin: 18px 0; }}
            .btn {{ display: inline-block; background: #1E3A8A; color: #FFFFFF !important; text-decoration: none; padding: 10px 20px; font-weight: 600; border-radius: 6px; margin-top: 16px; }}
            .footer {{ background: #0F172A; color: #94A3B8; text-align: center; padding: 16px; font-size: 11.5px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <div class="badge">InternFlow AI Automation</div>
              <h2 style="margin: 0; font-size: 20px; font-weight: 800;">{self.from_name}</h2>
              <div style="font-size: 12px; opacity: 0.9; margin-top: 4px;">ID: {intern_code} | Domain: {domain}</div>
            </div>
            <div class="content">
        """

        base_tail = """
            </div>
            <div class="footer">
              <p style="margin: 0;">InternFlow AI Local Internship Platform &bull; Automated Dispatch</p>
              <p style="margin: 4px 0 0; opacity: 0.7;">Note: SMTP acceptance does not guarantee inbox delivery.</p>
            </div>
          </div>
        </body>
        </html>
        """

        templates = {
            # 1. Welcome Email
            "welcome": (
                f"Welcome to InternFlow AI — Getting Started ({intern_code})",
                f"""
                <h3>Welcome aboard, {intern_name}!</h3>
                <p>We are delighted to welcome you to the <strong>{domain}</strong> internship track.</p>
                <div class="card">
                  <strong>Assigned Project:</strong> {main_task}<br>
                  <strong>Duration:</strong> {context_data.get('duration_weeks', 4)} Weeks<br>
                  <strong>Portal URL:</strong> <a href="http://localhost:8000">http://localhost:8000</a>
                </div>
                <p>Your weekly roadmap and development milestones have been prepared by our AI curriculum engine. Sign in to your portal to inspect your first weekly deliverables.</p>
                <a href="http://localhost:8000" class="btn">Enter Intern Portal</a>
                """
            ),

            # 2. Internship Confirmation
            "internship_confirmation": (
                f"Official Internship Confirmation: {intern_name} ({intern_code})",
                f"""
                <h3>Official Internship Confirmation</h3>
                <p>Dear {intern_name},</p>
                <p>This email confirms your formal enrollment in the <strong>{domain}</strong> engineering internship.</p>
                <div class="card">
                  <strong>Intern Code:</strong> {intern_code}<br>
                  <strong>Primary Track:</strong> {domain}<br>
                  <strong>Main Objective:</strong> {main_task}<br>
                  <strong>Start Date:</strong> {context_data.get('start_date', 'Immediate')}<br>
                  <strong>Supervising Mentor:</strong> Lead Technical Mentor
                </div>
                <p>Please review your weekly milestone deadlines carefully. All code, reports, and deliverables must be submitted on time through the portal.</p>
                """
            ),

            # 3. Weekly Task Assignment
            "weekly_task_assignment": (
                f"New Milestone Assigned: Week {context_data.get('week_number', 1)} - {context_data.get('task_title', 'Core Task')}",
                f"""
                <h3>Week {context_data.get('week_number', 1)} Milestone Assigned</h3>
                <p>Hello {intern_name}, your development task for this week is now active.</p>
                <div class="card">
                  <h4 style="margin: 0 0 8px; color: #1E3A8A;">{context_data.get('task_title', 'Task Title')}</h4>
                  <p style="margin: 0; font-size: 13.5px;">{context_data.get('task_description', 'Detailed specs available in portal.')}</p>
                  <p style="margin: 8px 0 0; font-size: 12px; color: #64748B;"><strong>Deadline:</strong> {context_data.get('deadline', 'End of Week')}</p>
                </div>
                <p>Sign in to your portal to inspect full step-by-step instructions and recommended technology libraries.</p>
                <a href="http://localhost:8000/intern" class="btn">View Task & Instructions</a>
                """
            ),

            # 4. Detailed Task Explanation
            "detailed_task_explanation": (
                f"Technical Specifications & Guide: {context_data.get('task_title', 'Weekly Task')}",
                f"""
                <h3>Technical Guidance for Week {context_data.get('week_number', 1)}</h3>
                <p>Dear {intern_name}, here is your architectural walkthrough for <strong>{context_data.get('task_title', 'Task')}</strong>:</p>
                <div class="card">
                  <strong>Recommended Tech Stack:</strong><br>
                  <span style="color: #2563EB;">{context_data.get('technologies', 'Standard Python/Web Stack')}</span><br><br>
                  <strong>Expected Outputs:</strong><br>
                  <span>{context_data.get('expected_output', 'Functional repository with unit tests.')}</span><br><br>
                  <strong>Submission Requirements:</strong><br>
                  <span>{context_data.get('submission_requirements', 'GitHub repo URL & technical summary.')}</span>
                </div>
                <p>If you encounter syntax roadblocks or need debugging assistance, consult our built-in <strong>AI Project Mentor</strong> in your portal.</p>
                """
            ),

            # 5. Task Deadline Reminder
            "deadline_reminder": (
                f"Urgent Reminder: Milestone Deadline Approaching for {context_data.get('task_title', 'Task')}",
                f"""
                <h3 style="color: #D97706;">Deadline Approaching</h3>
                <p>Hello {intern_name},</p>
                <p>This is an automated reminder that your milestone deadline for <strong>{context_data.get('task_title', 'Task')}</strong> is approaching on <strong>{context_data.get('deadline', 'Soon')}</strong>.</p>
                <div class="card" style="border-left: 4px solid #F59E0B;">
                  Please ensure your code is pushed to Git, test coverage verified, and submission created through the portal before the deadline.
                </div>
                <a href="http://localhost:8000/intern" class="btn">Submit Deliverables Now</a>
                """
            ),

            # 6. Submission Reminder
            "submission_reminder": (
                f"Submission Pending: Week {context_data.get('week_number', 1)} Deliverables Needed",
                f"""
                <h3>Submission Reminder</h3>
                <p>Dear {intern_name},</p>
                <p>We notice you haven't submitted your deliverables for <strong>{context_data.get('task_title', 'Current Task')}</strong>.</p>
                <p>Timely submissions are required to maintain your active internship standing and calculate your final grade.</p>
                <a href="http://localhost:8000/intern" class="btn">Go to Submission Dialog</a>
                """
            ),

            # 7. Review Meeting Invitation
            "review_meeting_invitation": (
                f"Meeting Invitation: {context_data.get('meeting_title', 'Technical Review Sync')}",
                f"""
                <h3>Technical Review Sync Scheduled</h3>
                <p>Hello {intern_name}, a technical review meeting has been scheduled with your mentor.</p>
                <div class="card">
                  <strong>Title:</strong> {context_data.get('meeting_title', 'Sync')}<br>
                  <strong>Date & Time:</strong> {context_data.get('scheduled_time', 'TBD')}<br>
                  <strong>Duration:</strong> {context_data.get('duration_minutes', 45)} minutes<br>
                  <strong>Video Link:</strong> <a href="{context_data.get('meeting_link', '#')}">{context_data.get('meeting_link', 'Portal Link')}</a>
                </div>
                <p>Please prepare a brief demonstration of your latest deliverables.</p>
                <a href="{context_data.get('meeting_link', 'http://localhost:8000/intern')}" class="btn">Join Review Meeting</a>
                """
            ),

            # 8. AI Evaluation Feedback
            "evaluation_feedback": (
                f"Milestone Evaluated: {context_data.get('task_title', 'Task')} (Score: {context_data.get('score', 0)}/100)",
                f"""
                <h3>Milestone Evaluation Published</h3>
                <p>Hello {intern_name}, your submitted work for <strong>{context_data.get('task_title', 'Task')}</strong> has been reviewed.</p>
                <div class="card" style="border-left: 4px solid #10B981;">
                  <div style="font-size: 24px; font-weight: 800; color: #1E3A8A;">Score: {context_data.get('score', 0)} / 100</div>
                  <div style="font-size: 13px; color: #475569; margin-top: 4px;">Status: <strong>{context_data.get('final_status', 'Approved').upper()}</strong></div>
                  <hr style="border: 0; border-top: 1px solid #CBD5E1; margin: 12px 0;">
                  <strong>Mentor & AI Feedback:</strong><br>
                  <p style="font-size: 13.5px; margin: 6px 0;">{context_data.get('feedback', 'Great work.')}</p>
                  {f"<strong>Key Strengths:</strong> {context_data.get('strengths')}<br>" if context_data.get('strengths') else ""}
                  {f"<strong>Areas for Improvement:</strong> {context_data.get('improvements')}<br>" if context_data.get('improvements') else ""}
                </div>
                <a href="http://localhost:8000/intern" class="btn">View Full Evaluation Report</a>
                """
            ),

            # 9. Resubmission Notification
            "resubmission_notification": (
                f"Action Required: Resubmission Requested for {context_data.get('task_title', 'Task')}",
                f"""
                <h3 style="color: #DC2626;">Resubmission Requested</h3>
                <p>Dear {intern_name},</p>
                <p>Your recent submission for <strong>{context_data.get('task_title', 'Task')}</strong> requires updates before it can be certified.</p>
                <div class="card" style="border-left: 4px solid #EF4444;">
                  <strong>Required Corrections:</strong><br>
                  <p style="font-size: 13.5px; margin: 6px 0;">{context_data.get('corrections', 'Please address technical feedback.')}</p>
                </div>
                <p>The submission portal has been re-opened. You may upload a revised package (v2) with your fixes.</p>
                <a href="http://localhost:8000/intern" class="btn">Resubmit Work</a>
                """
            ),

            # 10. Next-Week Assignment
            "next_week_assignment": (
                f"Next Milestone Ready: Week {context_data.get('week_number', 2)} Curriculum",
                f"""
                <h3>Ready for Week {context_data.get('week_number', 2)}!</h3>
                <p>Great progress, {intern_name}! You have successfully completed your previous milestone.</p>
                <p>Your next weekly milestone: <strong>{context_data.get('task_title', 'Next Task')}</strong> is now unlocked.</p>
                <a href="http://localhost:8000/intern" class="btn">Open Week {context_data.get('week_number', 2)} Tasks</a>
                """
            ),

            # 11. Internship Completion Email
            "internship_completion": (
                f"Congratulations! Internship Successfully Completed ({intern_code})",
                f"""
                <h3 style="color: #10B981;">🎉 Internship Completed!</h3>
                <p>Dear {intern_name},</p>
                <p>Hearty congratulations on completing all milestones of your <strong>{domain}</strong> engineering internship!</p>
                <div class="card">
                  <strong>Final Cumulative Score:</strong> {context_data.get('total_score', '90.0')} / 100<br>
                  <strong>Project Accomplished:</strong> {main_task}<br>
                  <strong>Completion Status:</strong> Certified with Distinction
                </div>
                <p>Your official verifiable Certificate of Completion is now ready in your portal.</p>
                <a href="http://localhost:8000/intern" class="btn">View & Download Certificate</a>
                """
            ),

            # 12. Certificate Delivery
            "certificate_delivery": (
                f"Official Certificate Delivered: {intern_name} ({context_data.get('certificate_number', 'CERT-IF')})",
                f"""
                <h3 style="color: #1E3A8A;">🎓 Your Verified Certificate is Ready!</h3>
                <p>Dear {intern_name},</p>
                <p>Congratulations! Your official verifiable Certificate of Completion for the <strong>{domain}</strong> engineering track has been generated and certified.</p>
                <div class="card" style="text-align: center; border-left: 4px solid #1E3A8A;">
                  <div style="font-size: 20px; font-weight: 800; color: #1E3A8A;">{context_data.get('certificate_number', 'CERT-IF-0001')}</div>
                  <div style="font-size: 13px; font-weight: 700; color: #10B981; margin-top: 6px;">Graduated with Honors: {context_data.get('grade', 'Outstanding')} ({context_data.get('total_score', '90.0')}/100)</div>
                  <div style="font-size: 11.5px; color: #64748B; font-family: monospace; margin-top: 6px;">Verification Hash: {context_data.get('verification_hash', 'N/A')}</div>
                </div>
                <p>Your official PDF certificate with embedded verification QR code is <strong>attached to this email</strong> for your records.</p>
                <p>Public online verification link: <a href="http://localhost:8000/verify/{context_data.get('certificate_number', '')}" style="color: #2563EB; font-weight: 600;">Verify Certificate Online ↗</a></p>
                <a href="http://localhost:8000/intern" class="btn">Access Intern Portal</a>
                """
            ),

            # 13. Final Appreciation Email
            "final_appreciation": (
                f"Letter of Appreciation & Future Career Recommendations — {intern_name}",
                f"""
                <h3 style="color: #1E3A8A;">Thank You & Letter of Engineering Appreciation</h3>
                <p>Dear {intern_name},</p>
                <p>On behalf of the mentorship committee and leadership at InternFlow AI, we extend our heartfelt gratitude and congratulations on completing your internship.</p>
                
                <div class="card" style="border-left: 4px solid #F97316;">
                  <strong style="color: #1E3A8A; font-size: 15px;">🌟 Internship Achievement Summary</strong>
                  <ul style="margin: 8px 0; padding-left: 20px; font-size: 13.5px; color: #334155;">
                    <li><strong>Domain of Specialization:</strong> {domain}</li>
                    <li><strong>Capstone Deliverable:</strong> {main_task}</li>
                    <li><strong>Overall Performance Score:</strong> {context_data.get('total_score', '90.0')} / 100 ({context_data.get('grade', 'Outstanding')})</li>
                    <li><strong>Milestones Accomplished:</strong> {context_data.get('completed_milestones', 'All weekly milestones certified')}</li>
                  </ul>
                </div>

                <div class="card" style="border-left: 4px solid #10B981;">
                  <strong style="color: #065F46; font-size: 15px;">🚀 Core Skills Demonstrated & Developed</strong>
                  <p style="margin: 6px 0; font-size: 13px; color: #475569;">
                    {context_data.get('skills_summary', f'Hands-on architecture in {domain}, modular implementation, unit testing, automated deployment pipelines, and technical documentation.')}
                  </p>
                </div>

                <div class="card" style="border-left: 4px solid #2563EB;">
                  <strong style="color: #1E3A8A; font-size: 15px;">💡 Career Suggestions & Future Learning Recommendations</strong>
                  <p style="margin: 6px 0; font-size: 13px; color: #334155;">
                    Based on your demonstrated strengths:
                  </p>
                  <ul style="margin: 6px 0; padding-left: 20px; font-size: 13px; color: #475569;">
                    <li><strong>Target Roles:</strong> {context_data.get('target_roles', f'{domain} Engineer, Systems Developer, Technical Consultant')}</li>
                    <li><strong>Next Technical Milestones:</strong> Deepen production monitoring, asynchronous microservices, and distributed cloud design.</li>
                    <li><strong>Portfolio Recommendation:</strong> Publish your capstone repository to GitHub with comprehensive documentation and performance benchmarks.</li>
                  </ul>
                </div>

                <p style="font-size: 13.5px; color: #334155; margin-top: 16px;">
                  We are proud to have supported your engineering journey and look forward to hearing about your future career milestones.
                </p>
                """
            )
        }

        subject, body = templates.get(email_type, templates["welcome"])
        full_html = f"{base_head}{body}{base_tail}"
        return subject, full_html

    def send_email(
        self,
        recipient_email: str,
        email_type: str,
        intern: Optional[Intern],
        context_data: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
        attachment_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatches email via Gmail SMTP (if configured) or logs accurately as QUEUED / FAILED.
        Enforces idempotency, duplicate prevention, optional PDF attachment, and detailed status recording.
        """
        context_data = context_data or {}
        subject, html_body = self.generate_html_template(email_type, intern, context_data)
        intern_id = intern.id if intern else None
        
        # Idempotency check
        idem_hash = self.compute_idempotency_hash(recipient_email, subject, email_type, intern_id)
        if db:
            existing = (
                db.query(EmailLog)
                .filter(EmailLog.idempotency_hash == idem_hash, EmailLog.status == "SMTP_ACCEPTED")
                .first()
            )
            if existing:
                logger.info(f"Duplicate email prevented for {recipient_email} [{email_type}]")
                return {
                    "status": "DUPLICATE_PREVENTED",
                    "log_id": existing.id,
                    "message": "Email already accepted by SMTP recently. Duplicate prevented."
                }

        # Check SMTP configuration
        if not self.is_configured():
            status = "FAILED"
            error_msg = "SMTP credentials missing in .env (SMTP_EMAIL / SMTP_PASSWORD). Email queued locally."
            log_entry = self._record_log(
                db=db,
                intern_id=intern_id,
                recipient=recipient_email,
                subject=subject,
                html_body=html_body,
                email_type=email_type,
                status=status,
                error_message=error_msg,
                idem_hash=idem_hash
            )
            return {
                "status": status,
                "log_id": log_entry.id if log_entry else None,
                "error": error_msg,
                "note": "SMTP acceptance does not guarantee inbox delivery."
            }

        # Genuine SMTP Dispatch
        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.email}>"
            msg["To"] = recipient_email

            part = MIMEText(html_body, "html")
            msg.attach(part)

            # Optional attachment (e.g. PDF Certificate)
            if attachment_path and os.path.exists(attachment_path):
                from email.mime.application import MIMEApplication
                attach_name = Path(attachment_path).name
                with open(attachment_path, "rb") as f:
                    part_attach = MIMEApplication(f.read(), Name=attach_name)
                    part_attach['Content-Disposition'] = f'attachment; filename="{attach_name}"'
                    msg.attach(part_attach)

            context = ssl.create_default_context()
            with smtplib.SMTP(self.server_host, self.port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self.email, self.password)
                server.sendmail(self.email, recipient_email, msg.as_string())

            status = "SMTP_ACCEPTED"
            log_entry = self._record_log(
                db=db,
                intern_id=intern_id,
                recipient=recipient_email,
                subject=subject,
                html_body=html_body,
                email_type=email_type,
                status=status,
                error_message=None,
                idem_hash=idem_hash
            )
            return {
                "status": status,
                "log_id": log_entry.id if log_entry else None,
                "message": "Message accepted by Gmail SMTP server for delivery.",
                "note": "SMTP acceptance does not guarantee inbox delivery."
            }
        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {e}")
            status = "FAILED"
            log_entry = self._record_log(
                db=db,
                intern_id=intern_id,
                recipient=recipient_email,
                subject=subject,
                html_body=html_body,
                email_type=email_type,
                status=status,
                error_message=str(e),
                idem_hash=idem_hash
            )
            return {
                "status": status,
                "log_id": log_entry.id if log_entry else None,
                "error": str(e)
            }

    def _record_log(
        self,
        db: Optional[Session],
        intern_id: Optional[int],
        recipient: str,
        subject: str,
        html_body: str,
        email_type: str,
        status: str,
        error_message: Optional[str],
        idem_hash: str
    ) -> Optional[EmailLog]:
        if not db:
            return None
        try:
            preview = subject
            log = EmailLog(
                intern_id=intern_id,
                recipient_email=recipient,
                subject=subject,
                body_preview=preview,
                html_body=html_body,
                email_type=email_type,
                status=status,
                error_message=error_message,
                idempotency_hash=idem_hash,
                sent_at=datetime.utcnow()
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            return log
        except Exception as e:
            logger.error(f"Error saving EmailLog: {e}")
            return None

    def retry_failed_email(self, log_id: int, db: Session) -> Tuple[bool, str]:
        """Admin retry operation for failed email queue items."""
        log = db.query(EmailLog).filter(EmailLog.id == log_id).first()
        if not log:
            return False, "Email log not found."
            
        intern = db.query(Intern).filter(Intern.id == log.intern_id).first() if log.intern_id else None
        log.retry_count = (log.retry_count or 0) + 1
        
        # Bypass idempotency for deliberate manual retries
        res = self.send_email(
            recipient_email=log.recipient_email,
            email_type=log.email_type,
            intern=intern,
            db=None
        )
        
        log.status = res["status"]
        log.error_message = res.get("error")
        log.sent_at = datetime.utcnow()
        db.commit()
        
        success = res["status"] == "SMTP_ACCEPTED"
        msg = "Email accepted by SMTP." if success else f"Retry failed: {res.get('error')}"
        return success, msg

email_service = EmailService()
