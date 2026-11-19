import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.intern import Intern
from app.models.chat import ChatHistory
from app.models.task import Task
from app.models.evaluation import Evaluation
from app.models.roadmap import WeeklyRoadmap
from app.services.ollama_service import ollama_service

logger = logging.getLogger(__name__)

class InternChatService:
    def get_conversation_history(self, intern_id: int, db: Session, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieves conversational memory strictly isolated to this intern."""
        messages = (
            db.query(ChatHistory)
            .filter(ChatHistory.intern_id == intern_id)
            .order_by(ChatHistory.created_at.asc())
            .all()
        )
        return [
            {
                "id": m.id,
                "role": m.role,
                "message": m.message,
                "model_used": m.model_used,
                "created_at": m.created_at.isoformat()
            }
            for m in messages[-limit:]
        ]

    def clear_conversation_history(self, intern_id: int, db: Session) -> int:
        """Starts a fresh new conversation for the intern."""
        count = db.query(ChatHistory).filter(ChatHistory.intern_id == intern_id).delete()
        db.commit()
        return count

    def generate_mentor_response(
        self,
        user_message: str,
        intern: Intern,
        db: Session
    ) -> Dict[str, Any]:
        """
        Generates deep, personalized AI guidance using Ollama,
        injecting the intern's actual database context and history.
        """
        # Save user turn into SQLite
        user_turn = ChatHistory(
            intern_id=intern.id,
            role="user",
            message=user_message,
            created_at=datetime.utcnow()
        )
        db.add(user_turn)
        db.commit()

        # Build deep intern-specific context
        # 1. Current Active Task
        active_task = (
            db.query(Task)
            .filter(Task.intern_id == intern.id, Task.status.in_(["pending", "submitted", "needs_resubmission"]))
            .order_by(Task.week_number.asc())
            .first()
        )
        current_task_info = f"Week {active_task.week_number}: {active_task.title} - {active_task.description}" if active_task else "All milestones submitted."

        # 2. Roadmap Summary
        roadmaps = db.query(WeeklyRoadmap).filter(WeeklyRoadmap.intern_id == intern.id).order_by(WeeklyRoadmap.week_number.asc()).all()
        roadmap_summary = "; ".join([f"Week {r.week_number} ({r.title})" for r in roadmaps]) or "Standard Track"

        # 3. Latest Evaluation / Feedback
        latest_eval = (
            db.query(Evaluation)
            .filter(Evaluation.intern_id == intern.id)
            .order_by(Evaluation.evaluated_at.desc())
            .first()
        )
        eval_context = (
            f"Latest Score: {latest_eval.score}/100. Feedback: {latest_eval.feedback}. Improvements advised: {latest_eval.improvements}"
            if latest_eval else "No evaluations yet."
        )

        # 4. Previous conversation turns (last 5)
        recent_chats = (
            db.query(ChatHistory)
            .filter(ChatHistory.intern_id == intern.id, ChatHistory.id != user_turn.id)
            .order_by(ChatHistory.created_at.desc())
            .limit(6)
            .all()
        )
        recent_chats.reverse()
        history_text = "\n".join([f"{c.role.upper()}: {c.message}" for c in recent_chats])

        # Construct Comprehensive System Prompt
        system_prompt = f"""
You are the dedicated Senior Technical Mentor for intern {intern.name} at InternFlow AI.
You have complete access to the intern's profile, domain context, assigned tasks, and review history.

INTERN CONTEXT:
- Name: {intern.name} (Code: {intern.intern_code})
- Domain: {intern.domain}
- Capstone Project: {intern.main_task}
- Total Duration: {intern.duration_weeks} Weeks
- Current Week: Week {intern.current_week}
- Current Active Milestone: {current_task_info}
- Curriculum Milestones: {roadmap_summary}
- Latest Evaluation: {eval_context}

PREVIOUS CONVERSATION CONTEXT:
{history_text if history_text else "Starting new conversation session."}

MENTORING GUIDELINES:
1. Provide concrete, actionable technical guidance, code snippets, syntax explanations, or step-by-step debugging.
2. Align your recommendations directly with the intern's domain ({intern.domain}) and assigned project ({intern.main_task}).
3. Explain technical concepts clearly without assuming advanced prior knowledge.
4. If the intern asks about an error, explain why it happened and provide the corrected code structure.
5. Encourage clean architecture, unit testing, and Git best practices.
"""

        conn = ollama_service.check_connection()
        ai_reply = ""
        model_name = "Ollama Local LLM"

        if conn["connected"] and conn.get("available_models"):
            resp = ollama_service.generate_completion(user_message, system_prompt=system_prompt)
            if resp:
                ai_reply = resp
                model_name = conn.get("active_model", "llama3")

        # Fallback intelligent local mentor guidance
        if not ai_reply:
            model_name = "InternFlow AI Local Mentor (Autonomous Memory)"
            ai_reply = self._build_contextual_fallback(user_message, intern, active_task, latest_eval)

        # Save assistant message into SQLite
        ai_turn = ChatHistory(
            intern_id=intern.id,
            role="assistant",
            message=ai_reply,
            model_used=model_name,
            created_at=datetime.utcnow()
        )
        db.add(ai_turn)
        db.commit()

        return {
            "reply": ai_reply,
            "model": model_name,
            "intern_name": intern.name,
            "domain": intern.domain
        }

    def _build_contextual_fallback(
        self,
        query: str,
        intern: Intern,
        task: Optional[Task],
        evaluation: Optional[Evaluation]
    ) -> str:
        q_lower = query.lower()
        task_title = task.title if task else intern.main_task

        if "error" in q_lower or "bug" in q_lower or "failed" in q_lower:
            return (
                f"Hello {intern.name}! Regarding the issue in your '{task_title}' milestone:\n\n"
                f"1. **Trace Analysis**: Check the stack trace top-to-bottom. Most errors in {intern.domain} stem from type mismatches, unhandled None/null values, or missing environment variables.\n"
                f"2. **Isolation Strategy**: Add debug logging around the failing function to inspect the exact input arguments before execution.\n"
                f"3. **Dependency Check**: Ensure your local packages match requirements.txt.\n\n"
                f"Paste the exact error traceback here and I will diagnose the line-by-line fix for you!"
            )
        elif "test" in q_lower or "eval" in q_lower:
            return (
                f"Hello {intern.name}! For testing '{task_title}' in {intern.domain}:\n\n"
                f"1. **Unit Testing**: Structure your test functions with Arrange-Act-Assert blocks.\n"
                f"2. **Edge Cases**: Test boundary conditions (empty input, invalid formats, extreme numbers).\n"
                f"3. **Coverage Target**: Aim for at least 80% test coverage before submitting your deliverable.\n"
                f"Your latest evaluation feedback highlighted: '{evaluation.improvements if evaluation else 'Focus on code modularity'}'. Let's ensure this is addressed!"
            )
        else:
            return (
                f"Hello {intern.name}! For your '{task_title}' project in {intern.domain}:\n\n"
                f"Regarding your query: *\"{query}\"*\n\n"
                f"• **Architectural Recommendation**: Keep your service layer independent of your presentation/API routes. This ensures testability and clean separation of concerns.\n"
                f"• **Step-by-Step Focus**: Complete your milestone deliverables for Week {intern.current_week} first before adding extra dependencies.\n"
                f"• **Submission Check**: Double check that your Git commit history is clean and descriptive.\n\n"
                f"Feel free to ask for specific code structures, algorithms, or API designs!"
            )

intern_chat_service = InternChatService()
