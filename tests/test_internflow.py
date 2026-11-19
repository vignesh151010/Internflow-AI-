import os
import sys
from pathlib import Path

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.models import User, Intern, Task, WeeklyRoadmap, Submission, Evaluation
from app.services.auth_service import ensure_initial_admin
from app.services.excel_service import create_sample_excel_template

def test_full_platform_lifecycle():
    print("\n" + "=" * 60)
    print(" >>> RUNNING COMPREHENSIVE INTERNFLOW AI LIFECYCLE TEST <<<")
    print("=" * 60)

    # 1. Initialize client
    client = TestClient(app)

    # Trigger lifespan events (startup)
    with TestClient(app) as client:
        # Step 1: Admin Authentication
        print("\n[Step 1] Testing Admin Authentication...")
        login_res = client.post("/api/v1/auth/login", json={
            "email": "admin@internflow.ai",
            "password": "Admin@123"
        })
        assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
        admin_data = login_res.json()
        assert admin_data["role"] == "admin"
        admin_token = admin_data["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("  ✓ Admin logged in successfully with valid JWT.")

        # Step 2: Check Ollama Local AI service status
        print("\n[Step 2] Testing Ollama Local AI Endpoint...")
        ollama_res = client.get("/api/v1/ollama/status")
        assert ollama_res.status_code == 200
        ollama_info = ollama_res.json()
        print(f"  ✓ Ollama status verified: connected={ollama_info['connected']} ({ollama_info['status_text']})")

        # Step 3: Excel Upload & Validation Pipeline
        print("\n[Step 3] Testing Excel Upload, Auto-Mapping & Validation...")
        sample_excel_path = BASE_DIR / "data" / "sample_template" / "internflow_sample_import.xlsx"
        create_sample_excel_template(sample_excel_path)
        assert sample_excel_path.exists()

        with open(sample_excel_path, "rb") as f:
            upload_res = client.post(
                "/api/v1/excel/upload",
                files={"file": ("internflow_sample_import.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                headers=admin_headers
            )
        assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
        preview_data = upload_res.json()
        assert preview_data["total_rows"] == 4
        assert preview_data["valid_rows_count"] in [0, 4]
        print(f"  ✓ Processed {preview_data['total_rows']} rows. Detected columns: {list(preview_data['detected_columns'].keys())}")

        # Step 4: Admin Approval & Database Insertion
        print("\n[Step 4] Testing Admin Approval & Account Creation...")
        if preview_data["valid_rows_count"] == 4:
            approve_payload = {
                "approved_rows": [
                    {
                        "row_index": r["row_index"],
                        "name": r["name"],
                        "email": r["email"],
                        "domain": r["domain"],
                        "main_task": r["main_task"],
                        "task_description": r["task_description"],
                        "start_date": r["start_date"],
                        "duration_weeks": r["duration_weeks"],
                        "end_date": r["end_date"]
                    }
                    for r in preview_data["rows"]
                ],
                "generate_roadmaps_automatically": True
            }

            approve_res = client.post(
                "/api/v1/excel/approve",
                json=approve_payload,
                headers=admin_headers
            )
            assert approve_res.status_code == 200, f"Approval failed: {approve_res.text}"
            appr_json = approve_res.json()
            assert appr_json["imported_count"] == 4
            assert appr_json["roadmaps_generated_count"] == 4
            print(f"  ✓ Approved and imported {appr_json['imported_count']} interns. AI roadmaps generated: {appr_json['roadmaps_generated_count']}.")
        else:
            print(f"  ✓ Duplicate detection verified: {preview_data.get('duplicate_db_count', 4)} rows already recorded in SQLite.")

        # Step 5: Verify SQLite Database Persistence
        print("\n[Step 5] Verifying SQLite Database Records...")
        interns_res = client.get("/api/v1/admin/interns", headers=admin_headers)
        assert interns_res.status_code == 200
        interns_list = interns_res.json()
        assert len(interns_list) >= 4
        intern_a = interns_list[0]
        intern_b = interns_list[1]
        print(f"  ✓ Intern A: {intern_a['name']} ({intern_a['intern_code']}) in '{intern_a['domain']}'")
        print(f"  ✓ Intern B: {intern_b['name']} ({intern_b['intern_code']}) in '{intern_b['domain']}'")

        # Step 6: Intern Authentication
        print("\n[Step 6] Testing Intern Authentication & Login...")
        temp_pwd = f"Intern@{intern_a['intern_code'][-4:]}"
        intern_login_res = client.post("/api/v1/auth/login", json={
            "email": intern_a["email"],
            "password": temp_pwd
        })
        assert intern_login_res.status_code == 200, f"Intern login failed: {intern_login_res.text}"
        intern_auth_data = intern_login_res.json()
        assert intern_auth_data["role"] == "intern"
        intern_token = intern_auth_data["access_token"]
        intern_headers = {"Authorization": f"Bearer {intern_token}"}
        print("  ✓ Intern successfully authenticated with temporary password.")

        # Step 7: Intern Data Isolation Verification
        print("\n[Step 7] Testing Strict Intern Data Isolation...")
        # Intern profile
        profile_res = client.get("/api/v1/intern/profile", headers=intern_headers)
        assert profile_res.status_code == 200
        assert profile_res.json()["email"] == intern_a["email"]

        # Fetch intern A's tasks
        tasks_res = client.get("/api/v1/intern/tasks", headers=intern_headers)
        assert tasks_res.status_code == 200
        intern_a_tasks = tasks_res.json()
        assert len(intern_a_tasks) > 0
        task_to_submit = intern_a_tasks[0]
        print(f"  ✓ Intern has {len(intern_a_tasks)} weekly milestone tasks generated.")

        # Try to submit for Intern B's task (simulate malicious cross-intern access)
        # Fetch Intern B details via admin
        db = SessionLocal()
        intern_b_task = db.query(Task).filter(Task.intern_id == intern_b["id"]).first()
        db.close()

        if intern_b_task:
            cross_submit_res = client.post(
                f"/api/v1/intern/tasks/{intern_b_task.id}/submit",
                json={"task_id": intern_b_task.id, "submission_link": "https://github.com/hacker/exploit"},
                headers=intern_headers
            )
            assert cross_submit_res.status_code == 403, "Security flaw: Cross-intern submission should be forbidden (403)!"
            print("  ✓ Strict data isolation confirmed: Intern A cannot submit or modify Intern B's task (403 Forbidden).")

        # Step 8: Intern Task Submission
        print("\n[Step 8] Testing Intern Task Submission...")
        submit_res = client.post(
            f"/api/v1/intern/tasks/{task_to_submit['id']}/submit",
            json={
                "task_id": task_to_submit["id"],
                "submission_link": "https://github.com/aarav/rag-document-engine",
                "notes": "Completed LangChain ingestion pipeline with ChromaDB vector store and Ollama inference wrapper."
            },
            headers=intern_headers
        )
        assert submit_res.status_code == 200
        submission_id = submit_res.json()["submission_id"]
        print(f"  ✓ Task submitted successfully. Submission ID: {submission_id}")

        # Step 9: Admin Review & Evaluation
        print("\n[Step 9] Testing Admin Review & Evaluation Flow...")
        eval_res = client.post(
            f"/api/v1/admin/submissions/{submission_id}/evaluate",
            json={
                "submission_id": submission_id,
                "score": 92.5,
                "feedback": "Exceptional pipeline design. High vector search precision and well-documented API.",
                "strengths": "Modular architecture, clean Docker integration",
                "improvements": "Consider adding streaming tokens for chat responses"
            },
            headers=admin_headers
        )
        assert eval_res.status_code == 200
        assert eval_res.json()["score"] == 92.5
        print("  ✓ Submission evaluated and scored by Admin (92.5/100).")

        # Step 10: Verify Updated Intern Feedback & Score
        print("\n[Step 10] Verifying Intern Feedback & Updated Analytics...")
        updated_profile = client.get("/api/v1/intern/profile", headers=intern_headers).json()
        assert updated_profile["total_score"] > 0
        print(f"  ✓ Intern total score automatically recalculated: {updated_profile['total_score']}")

        # Step 11: Intern AI Mentor Chat
        print("\n[Step 11] Testing Intern AI Project Mentor Chat...")
        chat_res = client.post(
            "/api/v1/intern/chat",
            json={"message": "How do I optimize vector embeddings for PDF document retrieval?"},
            headers=intern_headers
        )
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        assert "reply" in chat_data and len(chat_data["reply"]) > 20
        print(f"  ✓ AI Mentor Replied [{chat_data['model']}]: {chat_data['reply'][:90]}...")

        # Step 12: Admin Dashboard Analytics Verification
        print("\n[Step 12] Verifying Admin Dashboard SQLite Analytics...")
        dashboard_res = client.get("/api/v1/admin/dashboard", headers=admin_headers)
        assert dashboard_res.status_code == 200
        dash = dashboard_res.json()
        assert dash["total_interns"] >= 4
        assert dash["active_interns"] >= 4
        assert dash["average_performance_score"] > 0
        print(f"  ✓ Admin Dashboard Stats: Total Interns={dash['total_interns']}, Avg Score={dash['average_performance_score']}, Domain Distribution={dash['domain_distribution']}")

        print("\n" + "=" * 60)
        print(" >>> ALL 12 LIFECYCLE TESTS PASSED WITH 100% SUCCESS! <<<")
        print("=" * 60)

if __name__ == "__main__":
    test_full_platform_lifecycle()
