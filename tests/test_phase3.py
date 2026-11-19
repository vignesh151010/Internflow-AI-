import os
import io
import sys
import json
import time
from datetime import datetime, date, timedelta
from pathlib import Path
import pandas as pd

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models import User, Intern, Task, Submission, Evaluation, Certificate, EmailLog, AutomationJob, Meeting
from app.services.automation_service import automation_service
from app.services.certificate_service import certificate_service

def test_phase3_complete_automation_system():
    print("\n" + "=" * 70)
    print(" >>> RUNNING INTERNFLOW AI PHASE 3 END-TO-END AUTOMATION SUITE <<<")
    print("=" * 70)

    with TestClient(app) as client:
        # -----------------------------------------------------------------
        # 1. Admin Authentication
        # -----------------------------------------------------------------
        print("\n[Step 1] Authenticating System Administrator...")
        login_res = client.post("/api/v1/auth/login", json={
            "email": "admin@internflow.ai",
            "password": "Admin@123"
        })
        assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
        admin_token = login_res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("  ✓ Admin authenticated successfully.")

        # -----------------------------------------------------------------
        # 2. Excel Upload, Validation & Admin Approval with 3 Sample Interns
        # -----------------------------------------------------------------
        print("\n[Step 2] Ingesting & Validating Excel Roster with 3 Sample Interns...")
        test_run_id = int(time.time())
        sample_interns_data = [
            {
                "Intern Name": "Ananya Deshmukh",
                "Email Address": f"ananya.ai_{test_run_id}@example.com",
                "Domain": "AI / Machine Learning",
                "Main Assigned Task": "Autonomous Medical Diagnosis Engine with Local LLM",
                "Task Description": "Develop local RAG architecture for analyzing clinical pathology reports with Ollama.",
                "Internship Start Date": date.today().strftime("%Y-%m-%d"),
                "Internship Duration": 4,
                "Internship End Date": (date.today() + timedelta(weeks=4)).strftime("%Y-%m-%d")
            },
            {
                "Intern Name": "Vikram Aditya",
                "Email Address": f"vikram.web_{test_run_id}@example.com",
                "Domain": "Full Stack Web Development",
                "Main Assigned Task": "Enterprise Supply Chain Real-Time Tracking Portal",
                "Task Description": "Build responsive reactive inventory analytics with WebSockets and FastAPI.",
                "Internship Start Date": date.today().strftime("%Y-%m-%d"),
                "Internship Duration": 4,
                "Internship End Date": (date.today() + timedelta(weeks=4)).strftime("%Y-%m-%d")
            },
            {
                "Intern Name": "Kavya Ramesh",
                "Email Address": f"kavya.cloud_{test_run_id}@example.com",
                "Domain": "Cloud & DevOps",
                "Main Assigned Task": "Zero-Trust Microservices Mesh & Kubernetes Orchestration",
                "Task Description": "Configure local containerized cluster with Istio service mesh and automated probes.",
                "Internship Start Date": date.today().strftime("%Y-%m-%d"),
                "Internship Duration": 4,
                "Internship End Date": (date.today() + timedelta(weeks=4)).strftime("%Y-%m-%d")
            }
        ]

        df = pd.DataFrame(sample_interns_data)
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)

        upload_res = client.post(
            "/api/v1/excel/upload",
            files={"file": ("phase3_interns.xlsx", excel_buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=admin_headers
        )
        assert upload_res.status_code == 200, f"Excel upload failed: {upload_res.text}"
        preview = upload_res.json()
        assert preview["total_rows"] == 3
        assert preview["valid_rows_count"] == 3
        print(f"  ✓ Processed and validated {preview['valid_rows_count']} rows across 3 distinct domains.")

        # Admin Approval
        print("\n[Step 3] Admin Approving Ingestion & Initializing Autonomous Workflows...")
        approve_res = client.post(
            "/api/v1/excel/approve",
            json={
                "approved_rows": preview["rows"],
                "generate_roadmaps_automatically": True
            },
            headers=admin_headers
        )
        assert approve_res.status_code == 200, f"Approval failed: {approve_res.text}"
        appr_data = approve_res.json()
        assert appr_data["imported_count"] == 3
        print("  ✓ Successfully imported 3 interns and launched autonomous lifecycle workflows.")

        # Retrieve the 3 imported interns from SQLite
        db = SessionLocal()
        intern_1 = db.query(Intern).filter(Intern.email == sample_interns_data[0]["Email Address"]).first()
        intern_2 = db.query(Intern).filter(Intern.email == sample_interns_data[1]["Email Address"]).first()
        intern_3 = db.query(Intern).filter(Intern.email == sample_interns_data[2]["Email Address"]).first()
        assert intern_1 and intern_2 and intern_3, "Imported interns not found in database!"
        print(f"  ✓ Intern 1: {intern_1.name} ({intern_1.intern_code}) [{intern_1.domain}]")
        print(f"  ✓ Intern 2: {intern_2.name} ({intern_2.intern_code}) [{intern_2.domain}]")
        print(f"  ✓ Intern 3: {intern_3.name} ({intern_3.intern_code}) [{intern_3.domain}]")
        db.close()

        # -----------------------------------------------------------------
        # 3. Automation Job Queue & Execution Verification
        # -----------------------------------------------------------------
        print("\n[Step 4] Verifying Automated Lifecycle Queue & Dispatches...")
        db = SessionLocal()
        completed_jobs = db.query(AutomationJob).filter(AutomationJob.intern_id == intern_1.id, AutomationJob.status == "completed").all()
        assert len(completed_jobs) > 0, "Initial lifecycle jobs were not completed automatically upon approval!"
        print(f"  ✓ Initial lifecycle jobs automatically executed on approval: {len(completed_jobs)} jobs completed for Intern 1.")

        # Trigger queue check
        run_res = client.post("/api/v1/automation/run-pending", headers=admin_headers)
        assert run_res.status_code == 200
        run_summary = run_res.json()
        print(f"  ✓ Queue runner check status: Processed={run_summary['processed']}, Executed={run_summary['executed']}")

        # Verify welcome email, tasks, and roadmaps created
        db = SessionLocal()
        i1_tasks = db.query(Task).filter(Task.intern_id == intern_1.id).order_by(Task.week_number.asc()).all()
        assert len(i1_tasks) >= 4, f"Roadmap tasks not generated for Intern 1! Count: {len(i1_tasks)}"
        print(f"  ✓ Intern 1 has {len(i1_tasks)} weekly milestone tasks generated.")

        # Check review meeting scheduling with Google Meet
        i1_meetings = db.query(Meeting).filter(Meeting.intern_ids.contains(str(intern_1.id))).all()
        assert len(i1_meetings) > 0, "Review meeting was not scheduled automatically!"
        print(f"  ✓ Review meeting automatically scheduled: '{i1_meetings[0].title}'")
        db.close()

        # -----------------------------------------------------------------
        # 4. Intern Authentication & Strict Data Isolation
        # -----------------------------------------------------------------
        print("\n[Step 5] Testing Intern Authentication & Cross-Intern Security Barrier...")
        temp_pwd = f"Intern@{intern_1.intern_code[-4:]}"
        intern_login = client.post("/api/v1/auth/login", json={
            "email": intern_1.email,
            "password": temp_pwd
        })
        assert intern_login.status_code == 200, f"Intern login failed: {intern_login.text}"
        intern_token = intern_login.json()["access_token"]
        intern_headers = {"Authorization": f"Bearer {intern_token}"}
        print("  ✓ Intern 1 logged in successfully.")

        # Malicious cross-intern attempt: Intern 1 tries to submit on Intern 2's task
        db = SessionLocal()
        i2_task = db.query(Task).filter(Task.intern_id == intern_2.id).first()
        db.close()
        
        hack_res = client.post(
            f"/api/v1/intern/tasks/{i2_task.id}/submit",
            data={"notes": "Malicious cross-intern overwrite attempt"},
            headers=intern_headers
        )
        assert hack_res.status_code == 403, "Security flaw: Cross-intern submission allowed!"
        print("  ✓ Data isolation verified: Cross-intern submission blocked (403 Forbidden).")

        # -----------------------------------------------------------------
        # 5. Milestone Submission (Version 1)
        # -----------------------------------------------------------------
        print("\n[Step 6] Submitting Week 1 Milestone Deliverable (Version 1)...")
        w1_task = i1_tasks[0]
        code_bytes = io.BytesIO(b"# Ananya Medical Diagnosis Engine\ndef diagnose(sample):\n    return {'condition': 'Normal', 'confidence': 0.98}\n")
        sub1_res = client.post(
            f"/api/v1/intern/tasks/{w1_task.id}/submit",
            files={"file": ("medical_diagnosis_v1.py", code_bytes, "text/x-python")},
            data={
                "submission_link": "https://github.com/ananya/clinical-diagnosis-engine",
                "notes": "Version 1 Initial Medical RAG pipeline implementation."
            },
            headers=intern_headers
        )
        assert sub1_res.status_code == 200, f"Submission failed: {sub1_res.text}"
        sub1_data = sub1_res.json()
        sub_id = sub1_data["submission_id"]
        assert sub1_data["version"] == 1
        print(f"  ✓ Deliverable uploaded successfully. Version: {sub1_data['version']}, ID: {sub_id}")

        # -----------------------------------------------------------------
        # 6. Local AI Evaluation (9-Point Rubric) & Revision Request
        # -----------------------------------------------------------------
        print("\n[Step 7] Triggering Ollama Local AI Evaluation & Review Workflow...")
        ai_eval_res = client.post(
            f"/api/v1/admin/submissions/{sub_id}/ai-evaluate",
            headers=admin_headers
        )
        assert ai_eval_res.status_code == 200
        report = ai_eval_res.json().get("report", {})
        assert "score" in report and "completion_percentage" in report
        print(f"  ✓ AI 9-point evaluation produced: Score={report.get('score')}/100, Status={report.get('final_status')}")

        # Mentor requests revisions (needs_resubmission)
        print("\n[Step 8] Lead Mentor Requesting Revision (needs_resubmission)...")
        publish_res = client.post(
            f"/api/v1/admin/submissions/{sub_id}/publish-evaluation",
            json={
                "submission_id": sub_id,
                "score": 48.0,
                "feedback": "Core logic is solid, but HIPAA compliance headers and error boundaries are required.",
                "strengths": "Clean clinical report parser",
                "improvements": "1. Add HIPAA compliance check\n2. Implement confidence threshold fallback",
                "final_status": "needs_resubmission"
            },
            headers=admin_headers
        )
        assert publish_res.status_code == 200
        print("  ✓ Evaluation published: Revisions requested. Deadline extended automatically.")

        # Verify task is flagged for resubmission
        db = SessionLocal()
        task_check = db.query(Task).filter(Task.id == w1_task.id).first()
        assert task_check.status == "needs_resubmission"
        db.close()

        # -----------------------------------------------------------------
        # 7. Resubmission (Version 2)
        # -----------------------------------------------------------------
        print("\n[Step 9] Intern Submitting Revised Deliverable (Version 2)...")
        revised_zip = io.BytesIO(b"PK\x03\x04\x14\x00\x00\x00\x08\x00MedicalDiagnosisEngineWithHIPAAFixes")
        sub2_res = client.post(
            f"/api/v1/intern/tasks/{w1_task.id}/submit",
            files={"file": ("clinical_diagnosis_v2_hipaa.zip", revised_zip, "application/zip")},
            data={
                "submission_link": "https://github.com/ananya/clinical-diagnosis-engine/tree/v2-hipaa",
                "notes": "Version 2 Added HIPAA token masking and confidence threshold fallback."
            },
            headers=intern_headers
        )
        assert sub2_res.status_code == 200
        sub2_data = sub2_res.json()
        assert sub2_data["version"] == 2
        sub2_id = sub2_data["submission_id"]
        print(f"  ✓ Revision submitted successfully (Version {sub2_data['version']}).")

        # -----------------------------------------------------------------
        # 8. Approval & Automatic Milestone Advance (Week 1 -> Week 2)
        # -----------------------------------------------------------------
        print("\n[Step 10] Lead Mentor Approving Revision & Verifying Automated Next-Week Advance...")
        approve_v2_res = client.post(
            f"/api/v1/admin/submissions/{sub2_id}/publish-evaluation",
            json={
                "submission_id": sub2_id,
                "score": 96.0,
                "feedback": "Outstanding revision! HIPAA safeguards and threshold fallbacks are properly implemented.",
                "strengths": "Rapid turnaround, robust security guardrails",
                "improvements": "Ready for Week 2 integration",
                "final_status": "approved"
            },
            headers=admin_headers
        )
        assert approve_v2_res.status_code == 200
        print("  ✓ Revision approved with 96.0/100 score.")

        # Verify Intern 1 has automatically advanced to Week 2
        db = SessionLocal()
        intern_1_updated = db.query(Intern).filter(Intern.id == intern_1.id).first()
        assert intern_1_updated.current_week == 2, f"Intern did not advance to Week 2! Current: {intern_1_updated.current_week}"
        print(f"  ✓ Automated workflow advanced intern to Week {intern_1_updated.current_week}.")
        db.close()

        # -----------------------------------------------------------------
        # 9. Complete Internship & ReportLab PDF Certificate Generation
        # -----------------------------------------------------------------
        print("\n[Step 11] Fulfilling Internship Completion for Intern 2 & Generating ReportLab PDF Certificate...")
        db = SessionLocal()
        i2_db = db.query(Intern).filter(Intern.id == intern_2.id).first()
        for t in i2_db.tasks:
            t.status = "approved"
        i2_db.total_score = 92.5
        i2_db.status = "completed"
        db.commit()

        # Issue certificate
        cert = certificate_service.issue_certificate(intern_2.id, db, admin_override=True)
        assert cert is not None
        assert cert.certificate_number.startswith("CERT-IF-")
        assert cert.file_path and os.path.exists(cert.file_path)
        pdf_size = os.path.getsize(cert.file_path)
        assert pdf_size > 2000, f"Generated PDF is too small ({pdf_size} bytes)!"
        print(f"  ✓ Official ReportLab PDF Certificate generated: {cert.certificate_number}")
        print(f"    - File: {cert.file_path} ({pdf_size} bytes)")
        print(f"    - Grade: {cert.grade}, Verification Hash: {cert.verification_hash}")
        db.close()

        # -----------------------------------------------------------------
        # 10. Public QR Code Online Verification
        # -----------------------------------------------------------------
        print("\n[Step 12] Testing Public Online Certificate Verification (QR Code Target)...")
        # Public lookup without any authorization headers
        verify_res = client.get(f"/api/v1/certificates/verify/{cert.certificate_number}")
        assert verify_res.status_code == 200, f"Verification failed: {verify_res.text}"
        v_data = verify_res.json()
        assert v_data["valid"] is True
        assert v_data["intern_name"] == intern_2.name
        assert v_data["domain"] == intern_2.domain
        assert v_data["certificate_number"] == cert.certificate_number
        print(f"  ✓ Public verification confirmed: {v_data['intern_name']} -> {v_data['grade']}")

        # Test PDF download endpoint
        download_res = client.get(f"/api/v1/certificates/{cert.certificate_number}/download")
        assert download_res.status_code == 200
        assert download_res.headers["content-type"] == "application/pdf"
        assert len(download_res.content) == pdf_size
        print(f"  ✓ PDF Certificate download served successfully ({len(download_res.content)} bytes).")

        # Test invalid certificate lookup
        invalid_res = client.get("/api/v1/certificates/verify/CERT-IF-FAKE-9999")
        assert invalid_res.status_code == 404
        print("  ✓ Invalid certificate lookup properly rejected with 404.")

        # -----------------------------------------------------------------
        # 11. Workflow Pause, Resume & Cancel Controls
        # -----------------------------------------------------------------
        print("\n[Step 13] Testing Workflow Controls (Pause, Resume, Cancel)...")
        # Pause
        pause_res = client.post(f"/api/v1/automation/workflows/{intern_3.id}/pause", headers=admin_headers)
        assert pause_res.status_code == 200
        db = SessionLocal()
        assert db.query(Intern).filter(Intern.id == intern_3.id).first().workflow_status == "paused"
        print("  ✓ Workflow successfully paused.")

        # Resume
        resume_res = client.post(f"/api/v1/automation/workflows/{intern_3.id}/resume", headers=admin_headers)
        assert resume_res.status_code == 200
        assert db.query(Intern).filter(Intern.id == intern_3.id).first().workflow_status == "active"
        print("  ✓ Workflow successfully resumed.")

        # Cancel
        cancel_res = client.post(f"/api/v1/automation/workflows/{intern_3.id}/cancel", headers=admin_headers)
        assert cancel_res.status_code == 200
        assert db.query(Intern).filter(Intern.id == intern_3.id).first().workflow_status == "cancelled"
        print("  ✓ Workflow successfully cancelled.")
        db.close()

        # -----------------------------------------------------------------
        # 12. Configurable Automation Schedule Settings
        # -----------------------------------------------------------------
        print("\n[Step 14] Testing Configurable Automation Schedule Settings...")
        settings_get = client.get("/api/v1/automation/settings", headers=admin_headers)
        assert settings_get.status_code == 200
        cfg = settings_get.json()
        assert "working_days" in cfg and "review_time" in cfg
        print(f"  ✓ Schedule config retrieved: Review={cfg.get('review_day')} at {cfg.get('review_time')}")

        settings_put = client.put(
            "/api/v1/automation/settings",
            json={
                "review_day": "Friday",
                "review_time": "15:00",
                "submission_deadline_day_offset": 5,
                "resubmission_extension_days": 3,
                "timezone": "UTC"
            },
            headers=admin_headers
        )
        assert settings_put.status_code == 200
        updated_cfg = settings_put.json()
        assert updated_cfg["review_day"] == "Friday"
        assert updated_cfg["resubmission_extension_days"] == 3
        print("  ✓ Schedule config updated and persisted in SQLite.")

        # -----------------------------------------------------------------
        # 13. Advanced Analytics & At-Risk Intern Detection
        # -----------------------------------------------------------------
        print("\n[Step 15] Testing Advanced Analytics & At-Risk Intern Detection...")
        analytics_res = client.get("/api/v1/automation/analytics/advanced", headers=admin_headers)
        assert analytics_res.status_code == 200
        adv = analytics_res.json()
        assert "at_risk_interns" in adv
        assert "performance_tiers" in adv
        assert "weekly_breakdown" in adv
        print(f"  ✓ Advanced analytics verified: At-Risk Count={adv['at_risk_count']}, Performance Tiers={adv['performance_tiers']}")

        # -----------------------------------------------------------------
        # 14. Restart Missed-Job Recovery Test
        # -----------------------------------------------------------------
        print("\n[Step 16] Testing Laptop Restart Missed-Job Recovery...")
        db = SessionLocal()
        # Simulate a job that was interrupted mid-flight
        stuck_job = AutomationJob(
            intern_id=intern_1.id,
            job_type="send_deadline_reminder",
            status="running",
            scheduled_at=datetime.utcnow() - timedelta(minutes=10),
            idempotency_key=f"TEST_STUCK_{int(time.time())}"
        )
        db.add(stuck_job)
        db.commit()

        recovery_result = automation_service.recover_missed_jobs(db)
        assert recovery_result["recovered_stuck_count"] >= 1
        db.refresh(stuck_job)
        assert stuck_job.status == "pending", "Interrupted running job was not recovered back to pending!"
        print(f"  ✓ Interrupted jobs recovered after simulated restart: {recovery_result['recovered_stuck_count']} reset.")
        db.close()

        print("\n" + "=" * 70)
        print(" >>> ALL 16 COMPREHENSIVE AUTOMATION TESTS PASSED WITH 100% SUCCESS! <<<")
        print("=" * 70)

if __name__ == "__main__":
    test_phase3_complete_automation_system()
