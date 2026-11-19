from app.core.database import Base
from app.models.user import User
from app.models.intern import Intern
from app.models.roadmap import WeeklyRoadmap
from app.models.task import Task
from app.models.submission import Submission
from app.models.evaluation import Evaluation
from app.models.meeting import Meeting
from app.models.attendance import Attendance
from app.models.notification import Notification
from app.models.certificate import Certificate
from app.models.chat import ChatHistory
from app.models.log import EmailLog, AuditLog, AutomationJob
from app.models.setting import AppSetting

__all__ = [
    "Base",
    "User",
    "Intern",
    "WeeklyRoadmap",
    "Task",
    "Submission",
    "Evaluation",
    "Meeting",
    "Attendance",
    "Notification",
    "Certificate",
    "ChatHistory",
    "EmailLog",
    "AuditLog",
    "AutomationJob",
    "AppSetting"
]

