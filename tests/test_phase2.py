import os
import io
import sys
import json
from pathlib import Path

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models import User, Intern, Task, Submission, Evaluation, Attendance, EmailLog, ChatHistory
from app.services.email_service import email_service
from app.services.google_service import google_calendar_service

def test_phase2_complete_suite():
    print("\n" + "=" * 65)
    print(" >>> RUNNING COMPREHENSIVE INTERNFLOW AI PHASE 2 TEST SUITE <<<")
    print("=" * 65)

    with TestClient(app) as client:
        # ---------------------------------------------------------
        # 1. Admin Authentication
        # ---------------------------------------------------------
        print("\n[Stage 1] Authenticating Admin...")
        login_res = client.post("/api/v1/auth/login", json={
            "email": "admin@internflow.ai",
            "password": "Admin@123"
        })
        assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
        admin_data = login_res.json()
        assert admin_data["role"] == "admin"
        admin_token = admin_data["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("  ✓ Admin authenticated successfully.")

        # ---------------------------------------------------------
        # 2. Intern Authentication & Setup
        # ---------------------------------------------------------
        print("\n[Stage 2] Authenticating Intern User...")
        interns_res = client.get("/api/v1/admin/interns", headers=admin_headers)
        assert interns_res.status_code == 200
        interns_list = interns_res.json()
        assert len(interns_list) > 0, "No interns found. Run Phase 1 tests first."
        target_intern = interns_list[0]

        temp_pwd = f"Intern@{target_intern['intern_code'][-4:]}"
        intern_login_res = client.post("/api/v1/auth/login", json={
            "email": target_intern["email"],
            "password": temp_pwd
        })
        assert intern_login_res.status_code == 200, f"Intern login failed: {intern_login_res.text}"
        intern_token = intern_login_res.json()["access_token"]
        intern_headers = {"Authorization": f"Bearer {intern_token}"}
        print(f"  ✓ Intern {target_intern['name']} ({target_intern['intern_code']}) authenticated.")

        # ---------------------------------------------------------
        # 3. Gmail SMTP Integration & Reliability
        # ---------------------------------------------------------
        print("\n[Stage 3] Testing Gmail SMTP Status & Reliable Email Delivery...")
        email_status_res = client.get("/api/v1/email/status", headers=admin_headers)
        assert email_status_res.status_code == 200
        email_status = email_status_res.json()
        print(f"  ✓ SMTP Server: {email_status['server']}:{email_status['port']}")
        print(f"  ✓ Configured: {email_status['configured']}, Sender: {email_status['sender_email']}")

        # Test connection endpoint
        conn_test = client.post("/api/v1/email/test-connection", headers=admin_headers)
        assert conn_test.status_code == 200
        print(f"  ✓ Connection probe result: {conn_test.json()['message']}")

        # Test duplicate email prevention
        db = SessionLocal()
        import random
        intern_obj = db.query(Intern).filter(Intern.id == target_intern["id"]).first()
        test_week = random.randint(100, 99999)
        res1 = email_service.send_email(
            recipient_email=target_intern["email"],
            email_type="weekly_task_assignment",
            intern=intern_obj,
            context_data={"week_number": test_week, "task_title": f"Test Milestone {test_week}"},
            db=db
        )
        assert res1["status"] in ["SMTP_ACCEPTED", "FAILED", "QUEUED"]
        print(f"  ✓ Initial dispatch record created: status={res1['status']}")

        # Mark log as SMTP_ACCEPTED to simulate accepted delivery and verify duplicate rejection
        log_entry = db.query(EmailLog).filter(EmailLog.id == res1["log_id"]).first()
        if log_entry:
            log_entry.status = "SMTP_ACCEPTED"
            db.commit()

        # Second dispatch with exact same parameters must be prevented
        res2 = email_service.send_email(
            recipient_email=target_intern["email"],
            email_type="weekly_task_assignment",
            intern=intern_obj,
            context_data={"week_number": test_week, "task_title": f"Test Milestone {test_week}"},
            db=db
        )
        assert res2["status"] == "DUPLICATE_PREVENTED", f"Duplicate prevention failed: {res2}"
        print("  ✓ Duplicate email prevention confirmed (status: DUPLICATE_PREVENTED).")

        # Verify email logs endpoint
        logs_res = client.get("/api/v1/email/logs", headers=admin_headers)
        assert logs_res.status_code == 200
        logs = logs_res.json()
        assert len(logs) > 0
        print(f"  ✓ Admin email monitoring: {len(logs)} email log records verified in SQLite.")
        db.close()

        # ---------------------------------------------------------
        # 4. Google Calendar & Meet Integration Probes
        # ---------------------------------------------------------
        print("\n[Stage 4] Testing Google Calendar & Meet Integration...")
        g_status_res = client.get("/api/v1/google/status", headers=admin_headers)
        assert g_status_res.status_code == 200
        g_status = g_status_res.json()
        print(f"  ✓ Google OAuth Status: configured={g_status['configured']}, authorized={g_status['authorized']} ({g_status['status_text']})")
        
        # Check OAuth Auth URL endpoint (handles unconfigured state without fake mock URLs)
        auth_url_res = client.get("/api/v1/google/auth-url", headers=admin_headers)
        if not g_status["configured"]:
            assert auth_url_res.status_code == 400
            print(f"  ✓ Properly reports setup requirement: '{auth_url_res.json()['detail']}'")
        else:
            assert auth_url_res.status_code == 200
            assert "auth_url" in auth_url_res.json()
            print("  ✓ Genuine Google OAuth authorization URL generated.")

        # Check genuine Meet generation behavior (must never produce fake URLs)
        db = SessionLocal()
        from app.models.meeting import Meeting
        import datetime
        test_meeting = Meeting(
            title="Design Review",
            description="Sprint Milestone Check",
            scheduled_time=datetime.datetime.utcnow() + datetime.timedelta(days=2),
            duration_minutes=30,
            status="scheduled"
        )
        meet_res = google_calendar_service.create_meeting_event(
            meeting=test_meeting,
            attendee_emails=[target_intern["email"]],
            db=db
        )
        # Should gracefully return error explaining setup required if credentials not configured
        if not g_status["authorized"]:
            assert meet_res.get("google_meet_url") is None, "Fake Google Meet URL generated! Rule violation."
            print("  ✓ Verified: Never generates fake Meet URLs when OAuth is unconfigured.")
        db.close()

        # ---------------------------------------------------------
        # 5. Task Submission System (Files, Validation & Versioning)
        # ---------------------------------------------------------
        print("\n[Stage 5] Testing Task Submission System & File Uploads...")
        intern_tasks = client.get("/api/v1/intern/tasks", headers=intern_headers).json()
        assert len(intern_tasks) > 0
        test_task = next((t for t in intern_tasks if not t.get("submission")), intern_tasks[-1])
        base_ver = test_task["submission"]["version"] if test_task.get("submission") else 0

        # 5.1 Block forbidden executable extensions
        fake_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00")
        blocked_res = client.post(
            f"/api/v1/intern/tasks/{test_task['id']}/submit",
            files={"file": ("malicious_payload.exe", fake_exe, "application/octet-stream")},
            data={"notes": "Exploit attempt"},
            headers=intern_headers
        )
        assert blocked_res.status_code == 400, "Security issue: Executable file was not blocked!"
        print(f"  ✓ Security check passed: .exe upload blocked with 400 ({blocked_res.json()['detail']})")

        # 5.2 Submit genuine Python code file (Version increment)
        valid_code = io.BytesIO(b"# InternFlow Project Milestone\ndef process_embeddings(docs):\n    return [len(d) for d in docs]\n")
        submit_v1_res = client.post(
            f"/api/v1/intern/tasks/{test_task['id']}/submit",
            files={"file": ("milestone_pipeline.py", valid_code, "text/x-python")},
            data={
                "submission_link": "https://github.com/intern/project-repo",
                "notes": "Version 1 Initial Implementation of document processing engine."
            },
            headers=intern_headers
        )
        assert submit_v1_res.status_code == 200, f"Submit v1 failed: {submit_v1_res.text}"
        v1_data = submit_v1_res.json()
        sub_id_v1 = v1_data["submission_id"]
        assert v1_data["version"] == base_ver + 1
        print(f"  ✓ Version {v1_data['version']} submitted successfully. Submission ID: {sub_id_v1}")

        # 5.3 Submit Revision (Version increment + 1)
        valid_zip = io.BytesIO(b"PK\x03\x04\x14\x00\x00\x00\x08\x00FakeZipHeaderContentsForTesting")
        submit_v2_res = client.post(
            f"/api/v1/intern/tasks/{test_task['id']}/submit",
            files={"file": ("project_revision_v2.zip", valid_zip, "application/zip")},
            data={
                "submission_link": "https://github.com/intern/project-repo/releases/v2.0",
                "notes": "Version 2 Enhanced with unit tests and error handling."
            },
            headers=intern_headers
        )
        assert submit_v2_res.status_code == 200, f"Submit v2 failed: {submit_v2_res.text}"
        v2_data = submit_v2_res.json()
        sub_id_v2 = v2_data["submission_id"]
        assert v2_data["version"] == base_ver + 2
        print(f"  ✓ Version {v2_data['version']} resubmitted successfully. Submission ID: {sub_id_v2}")

        # 5.4 Check Version History Endpoint
        versions_res = client.get(f"/api/v1/intern/tasks/{test_task['id']}/submissions", headers=intern_headers)
        assert versions_res.status_code == 200
        versions = versions_res.json()
        assert len(versions) >= 2
        assert versions[0]["version"] == base_ver + 2
        assert versions[0]["is_latest"] is True
        print(f"  ✓ Version history confirmed: {len(versions)} versions tracked in SQLite.")

        # ---------------------------------------------------------
        # 6. Local AI Task Evaluation (9-Point Rubric)
        # ---------------------------------------------------------
        print("\n[Stage 6] Testing Ollama Local AI Task Evaluation (9-Point Rubric)...")
        eval_ai_res = client.post(
            f"/api/v1/admin/submissions/{sub_id_v2}/ai-evaluate",
            headers=admin_headers
        )
        assert eval_ai_res.status_code == 200, f"AI evaluation failed: {eval_ai_res.text}"
        ai_res = eval_ai_res.json()
        ai_report = ai_res.get("report", ai_res)
        
        # Verify 9-point rubric attributes
        expected_keys = [
            "score",
            "completion_percentage",
            "requirements_fulfilled",
            "missing_requirements",
            "technical_mistakes",
            "code_quality_observations",
            "improvement_suggestions",
            "step_by_step_corrections",
            "final_status"
        ]
        for key in expected_keys:
            assert key in ai_report, f"Missing required 9-point rubric field: {key}"

        print(f"  ✓ AI 9-point evaluation generated successfully [{ai_res.get('model_used', 'Local AI')}]:")
        print(f"    - Score: {ai_report['score']}/100")
        print(f"    - Completion: {ai_report['completion_percentage']}%")
        print(f"    - Status: {ai_report['final_status']}")
        print(f"    - Code Quality: {str(ai_report['code_quality_observations'])[:70]}...")

        # ---------------------------------------------------------
        # 7. Admin Review, Score Modification & Publishing
        # ---------------------------------------------------------
        print("\n[Stage 7] Testing Mentor Review & Score Modification Flow...")
        publish_res = client.post(
            f"/api/v1/admin/submissions/{sub_id_v2}/publish-evaluation",
            json={
                "submission_id": sub_id_v2,
                "score": 88.5,
                "feedback": "Outstanding architectural improvement in v2. Production ready.",
                "strengths": "Modular pipeline, well formatted code, error resilience.",
                "improvements": "Add automated benchmarking suite for large PDF batches.",
                "final_status": "approved"
            },
            headers=admin_headers
        )
        assert publish_res.status_code == 200, f"Publish evaluation failed: {publish_res.text}"
        eval_record = publish_res.json()
        assert eval_record["score"] == 88.5
        print(f"  ✓ Mentor adjusted score to {eval_record['score']} and published evaluation.")

        # Verify intern's updated total score
        updated_profile = client.get("/api/v1/intern/profile", headers=intern_headers).json()
        assert updated_profile["total_score"] > 0
        print(f"  ✓ Intern total score automatically updated: {updated_profile['total_score']}")

        # ---------------------------------------------------------
        # 8. Daily Attendance Check-In System
        # ---------------------------------------------------------
        print("\n[Stage 8] Testing Daily Attendance Check-In System...")
        checkin_res = client.post("/api/v1/intern/attendance/check-in", headers=intern_headers)
        assert checkin_res.status_code == 200
        print(f"  ✓ Attendance check-in 1: {checkin_res.json()['message']}")

        # Second check-in today should report already confirmed
        checkin_dup = client.post("/api/v1/intern/attendance/check-in", headers=intern_headers)
        assert checkin_dup.status_code == 200
        assert "already confirmed" in checkin_dup.json()["message"].lower()
        print("  ✓ Duplicate check-in handled gracefully.")

        # Admin attendance view
        admin_att_res = client.get("/api/v1/admin/attendance", headers=admin_headers)
        assert admin_att_res.status_code == 200
        att_records = admin_att_res.json()
        assert len(att_records) > 0
        print(f"  ✓ Admin verified {len(att_records)} attendance logs in SQLite.")

        # ---------------------------------------------------------
        # 9. Personalized AI Intern Chatbot & Isolated Memory
        # ---------------------------------------------------------
        print("\n[Stage 9] Testing Personalized AI Intern Assistant & Memory Isolation...")
        # Send query
        chat_q = client.post(
            "/api/v1/intern/chat",
            json={"message": "Can you explain how to benchmark the response latency of our project?"},
            headers=intern_headers
        )
        assert chat_q.status_code == 200
        reply_data = chat_q.json()
        assert "reply" in reply_data and len(reply_data["reply"]) > 10
        print(f"  ✓ AI Mentor Response: {reply_data['reply'][:90]}...")

        # Verify chat history persistence
        chat_hist = client.get("/api/v1/intern/chat/history", headers=intern_headers).json()
        assert len(chat_hist) >= 2  # user + assistant
        print(f"  ✓ Conversation history persisted: {len(chat_hist)} messages.")

        # Test conversation reset (clean context)
        del_chat = client.delete("/api/v1/intern/chat/history", headers=intern_headers)
        assert del_chat.status_code == 200
        cleared_hist = client.get("/api/v1/intern/chat/history", headers=intern_headers).json()
        assert len(cleared_hist) == 0
        print("  ✓ AI Chat Memory successfully reset and cleared.")

        # ---------------------------------------------------------
        # 10. Admin Integrations Health Monitor
        # ---------------------------------------------------------
        print("\n[Stage 10] Testing Admin Integrations Health Status Probes...")
        integ_res = client.get("/api/v1/admin/integrations/status", headers=admin_headers)
        assert integ_res.status_code == 200
        integ = integ_res.json()
        assert "smtp" in integ
        assert "google_calendar" in integ
        assert "ollama_ai" in integ
        assert "database" in integ
        print(f"  ✓ SMTP Configured: {integ['smtp']['configured']} ({integ['smtp']['status_text'][:50]}...)")
        print(f"  ✓ Google Calendar Status: {integ['google_calendar']['status_text']}")
        print(f"  ✓ Ollama Local AI: connected={integ['ollama_ai']['connected']} ({integ['ollama_ai']['active_model']})")
        print(f"  ✓ SQLite Database: {integ['database']['status']}")

        print("\n" + "=" * 65)
        print(" >>> ALL 10 PHASE 2 SUITE STAGES PASSED WITH 100% SUCCESS! <<<")
        print("=" * 65)

if __name__ == "__main__":
    test_phase2_complete_suite()
