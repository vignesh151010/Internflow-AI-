import sys
import time
from pathlib import Path
from datetime import date, timedelta

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.user import User
from app.models.intern import Intern
from app.services.auth_service import ensure_initial_admin

client = TestClient(app)


def test_auth_complete_redesign_scenarios():
    print("\n" + "=" * 70)
    print(" >>> RUNNING AUTH REDESIGN & REGISTRATION TEST SUITE <<<")
    print("=" * 70)

    db = SessionLocal()
    admin_user = ensure_initial_admin(db)
    db.close()

    timestamp = int(time.time() * 1000)
    test_email = f"test.intern.{timestamp}@internflow.ai"
    test_password = "SecurePassword@123"
    test_name = "Karthik Developer"

    # -------------------------------------------------------------
    # Scenario 1: Register a new account
    # -------------------------------------------------------------
    print("\n[Scenario 1] Registering a new account...")
    reg_res = client.post("/api/v1/auth/register", json={
        "full_name": test_name,
        "email": test_email,
        "password": test_password,
        "confirm_password": test_password
    })
    assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"
    reg_data = reg_res.json()
    assert reg_data["success"] is True
    assert reg_data["role"] == "intern"
    print(f"  ✓ User registered successfully with role '{reg_data['role']}'.")

    # Verify user record and intern profile in SQLite
    db = SessionLocal()
    u = db.query(User).filter(User.email == test_email).first()
    assert u is not None, "User not found in database!"
    assert u.role == "intern", "Role must be intern!"
    assert u.full_name == test_name
    assert u.hashed_password != test_password, "Password must be hashed, never plain-text!"

    intern_prof = db.query(Intern).filter(Intern.user_id == u.id).first()
    assert intern_prof is not None, "Intern profile was not created!"
    assert intern_prof.email == test_email
    assert intern_prof.status == "active"
    db.close()
    print("  ✓ Database record verified: User role=intern, Intern profile linked.")

    # -------------------------------------------------------------
    # Scenario 2: Register using an existing email (Duplicate Prevention)
    # -------------------------------------------------------------
    print("\n[Scenario 2] Registering with duplicate email...")
    dup_res = client.post("/api/v1/auth/register", json={
        "full_name": "Duplicate User",
        "email": test_email,
        "password": "AnotherPassword@123",
        "confirm_password": "AnotherPassword@123"
    })
    assert dup_res.status_code == 400, f"Expected 400, got {dup_res.status_code}"
    assert "already exists" in dup_res.text.lower()
    print("  ✓ Duplicate registration blocked with clear error message.")

    # -------------------------------------------------------------
    # Scenario 3: Register with invalid email
    # -------------------------------------------------------------
    print("\n[Scenario 3] Registering with invalid email format...")
    inv_email_res = client.post("/api/v1/auth/register", json={
        "full_name": "Invalid Email User",
        "email": "not-an-email-format",
        "password": "Password@123",
        "confirm_password": "Password@123"
    })
    assert inv_email_res.status_code == 422 or inv_email_res.status_code == 400
    print("  ✓ Invalid email properly rejected.")

    # -------------------------------------------------------------
    # Scenario 4: Register with mismatched passwords
    # -------------------------------------------------------------
    print("\n[Scenario 4] Registering with mismatched passwords...")
    mismatch_res = client.post("/api/v1/auth/register", json={
        "full_name": "Mismatch Tester",
        "email": f"mismatch.{timestamp}@example.com",
        "password": "Password@123",
        "confirm_password": "DifferentPassword@456"
    })
    assert mismatch_res.status_code == 400
    assert "not match" in mismatch_res.text.lower()
    print("  ✓ Mismatched passwords rejected.")

    # -------------------------------------------------------------
    # Scenario 5: Login using correct credentials
    # -------------------------------------------------------------
    print("\n[Scenario 5] Logging in with correct credentials...")
    login_res = client.post("/api/v1/auth/login", json={
        "email": test_email,
        "password": test_password
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["role"] == "intern"
    assert token_data["email"] == test_email
    assert token_data["intern_id"] is not None
    intern_token = token_data["access_token"]
    print("  ✓ Correct credentials accepted; JWT token and claims generated.")

    # -------------------------------------------------------------
    # Scenario 6: Login using incorrect password
    # -------------------------------------------------------------
    print("\n[Scenario 6] Logging in with incorrect password...")
    wrong_pwd_res = client.post("/api/v1/auth/login", json={
        "email": test_email,
        "password": "WrongPassword999"
    })
    assert wrong_pwd_res.status_code == 401
    print("  ✓ Incorrect password rejected (HTTP 401).")

    # -------------------------------------------------------------
    # Scenario 7: Login using an unregistered email
    # -------------------------------------------------------------
    print("\n[Scenario 7] Logging in with an unregistered email...")
    unreg_res = client.post("/api/v1/auth/login", json={
        "email": f"unregistered.{timestamp}@nonexistent.org",
        "password": "SomePassword@123"
    })
    assert unreg_res.status_code == 401
    print("  ✓ Unregistered email rejected (HTTP 401).")

    # -------------------------------------------------------------
    # Scenario 8: Verify Admin Login
    # -------------------------------------------------------------
    print("\n[Scenario 8] Verifying Administrator login...")
    admin_login_res = client.post("/api/v1/auth/login", json={
        "email": "admin@internflow.ai",
        "password": "Admin@123"
    })
    assert admin_login_res.status_code == 200
    admin_token_data = admin_login_res.json()
    assert admin_token_data["role"] == "admin"
    admin_token = admin_token_data["access_token"]
    print("  ✓ Administrator authenticated successfully with role 'admin'.")

    # -------------------------------------------------------------
    # Scenario 9: Verify Intern Login
    # -------------------------------------------------------------
    print("\n[Scenario 9] Verifying Intern profile retrieval with intern JWT...")
    intern_headers = {"Authorization": f"Bearer {intern_token}"}
    profile_res = client.get("/api/v1/intern/profile", headers=intern_headers)
    assert profile_res.status_code == 200, f"Profile lookup failed: {profile_res.text}"
    prof_data = profile_res.json()
    assert prof_data["name"] == test_name
    assert prof_data["email"] == test_email
    print(f"  ✓ Intern profile retrieved: {prof_data['name']} ({prof_data['intern_code']}).")

    # -------------------------------------------------------------
    # Scenario 10: Verify Role-based Dashboard Redirection & Access
    # -------------------------------------------------------------
    print("\n[Scenario 10] Verifying Dashboard access...")
    # Admin accesses admin overview
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_dash_res = client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert admin_dash_res.status_code == 200
    print("  ✓ Admin token allows access to Admin Dashboard API.")

    # -------------------------------------------------------------
    # Scenario 11: Verify Unauthorized Admin Access is Blocked
    # -------------------------------------------------------------
    print("\n[Scenario 11] Verifying intern token blocked from admin endpoints...")
    hack_res = client.get("/api/v1/admin/dashboard", headers=intern_headers)
    assert hack_res.status_code == 403, f"Expected 403, got {hack_res.status_code}"
    print("  ✓ Unauthorized admin access strictly forbidden for interns (HTTP 403).")

    # -------------------------------------------------------------
    # Scenario 12: Verify Existing User Accounts Still Work
    # -------------------------------------------------------------
    print("\n[Scenario 12] Verifying existing demo/imported accounts still work...")
    # Admin login still works
    admin_relogin = client.post("/api/v1/auth/login", json={
        "email": "admin@internflow.ai",
        "password": "Admin@123"
    })
    assert admin_relogin.status_code == 200
    print("  ✓ Existing Administrator account operational.")

    # -------------------------------------------------------------
    # Password Reset Test (Requirement 6)
    # -------------------------------------------------------------
    print("\n[Additional] Verifying Password Reset Flow...")
    new_pwd = "ResetPassword@456"
    reset_res = client.post("/api/v1/auth/reset-password", json={
        "email": test_email,
        "new_password": new_pwd
    })
    assert reset_res.status_code == 200
    # Login with new password
    login_new_res = client.post("/api/v1/auth/login", json={
        "email": test_email,
        "password": new_pwd
    })
    assert login_new_res.status_code == 200
    print("  ✓ Password reset and subsequent login confirmed.")

    print("\n" + "=" * 70)
    print(" >>> ALL 12 AUTH REDESIGN SCENARIOS PASSED WITH 100% SUCCESS! <<<")
    print("=" * 70)


if __name__ == "__main__":
    test_auth_complete_redesign_scenarios()
