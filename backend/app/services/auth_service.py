from datetime import datetime, date, timedelta
from typing import Optional, Tuple, Dict
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.intern import Intern
from app.models.log import AuditLog
from app.core.security import get_password_hash, verify_password
from app.core.config import settings

# In-memory login attempt tracking for basic brute-force protection
# Key: email or client IP, Value: list of failed timestamps
_FAILED_LOGIN_ATTEMPTS: Dict[str, list] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 5

def check_login_rate_limit(identifier: str) -> Tuple[bool, Optional[str]]:
    """Checks whether the identifier has exceeded the failed login attempt limit."""
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=LOCKOUT_MINUTES)
    
    attempts = _FAILED_LOGIN_ATTEMPTS.get(identifier, [])
    # Keep only attempts within lockout window
    recent_attempts = [t for t in attempts if t > cutoff]
    _FAILED_LOGIN_ATTEMPTS[identifier] = recent_attempts
    
    if len(recent_attempts) >= MAX_FAILED_ATTEMPTS:
        minutes_left = max(1, int((recent_attempts[0] + timedelta(minutes=LOCKOUT_MINUTES) - now).total_seconds() // 60))
        return False, f"Too many failed login attempts. Please try again in {minutes_left} minute(s)."
    return True, None

def record_failed_login(identifier: str):
    """Records a failed login attempt for rate limiting."""
    now = datetime.utcnow()
    if identifier not in _FAILED_LOGIN_ATTEMPTS:
        _FAILED_LOGIN_ATTEMPTS[identifier] = []
    _FAILED_LOGIN_ATTEMPTS[identifier].append(now)

def clear_failed_logins(identifier: str):
    """Clears failed login attempts upon successful authentication."""
    if identifier in _FAILED_LOGIN_ATTEMPTS:
        del _FAILED_LOGIN_ATTEMPTS[identifier]

def register_new_intern(
    db: Session,
    full_name: str,
    email: str,
    password: str,
    confirm_password: str
) -> Tuple[bool, str, Optional[User]]:
    """
    Registers a new public intern account with role 'intern'.
    Strictly forbids creating admin accounts publicly.
    Validates mandatory fields, password matching, security requirements and uniqueness.
    """
    clean_name = (full_name or "").strip()
    clean_email = (email or "").strip().lower()

    if not clean_name:
        return False, "User Name is mandatory.", None
    if len(clean_name) < 2:
        return False, "User Name must be at least 2 characters long.", None

    if not clean_email or "@" not in clean_email or "." not in clean_email:
        return False, "A valid email address is required.", None

    if not password:
        return False, "Password is mandatory.", None
    if len(password) < 6:
        return False, "Password must be at least 6 characters long.", None

    if password != confirm_password:
        return False, "Password and Confirm Password do not match.", None

    # Check for existing user account
    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        return False, "An account with this email address already exists. Please sign in.", None

    # 1. Create User account (Strictly role='intern')
    user = User(
        email=clean_email,
        hashed_password=get_password_hash(password),
        full_name=clean_name,
        role="intern",
        is_active=True
    )
    db.add(user)
    db.flush()

    # 2. Check if an Intern record already exists for this email (e.g. from Excel import)
    intern = db.query(Intern).filter(Intern.email == clean_email).first()
    if intern:
        intern.user_id = user.id
        intern.name = clean_name
    else:
        # Create default Intern profile for seamless access to Intern Portal
        current_year = datetime.now().year
        count = db.query(Intern).count() + 1
        intern_code = f"IF-{current_year}-{count:04d}"
        start_date_val = date.today()
        end_date_val = start_date_val + timedelta(weeks=4)

        intern = Intern(
            intern_code=intern_code,
            name=clean_name,
            email=clean_email,
            domain="Engineering",
            main_task="General Engineering & Platform Onboarding",
            task_description="Complete initial onboarding, set up workspace environment, and review foundational documentation.",
            start_date=start_date_val,
            duration_weeks=4,
            end_date=end_date_val,
            status="active",
            current_week=1,
            total_score=0.0,
            user_id=user.id
        )
        db.add(intern)

    # 3. Audit log
    audit = AuditLog(
        user_id=user.id,
        action="USER_REGISTERED",
        entity_type="User",
        entity_id=str(user.id),
        details=f"New public user registered as intern: {user.email} ({user.full_name})."
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    return True, "Account successfully created! Please sign in with your credentials.", user

def ensure_initial_admin(db: Session) -> User:
    """Ensures at least one default admin exists in SQLite database."""
    admin = db.query(User).filter(User.role == "admin").first()
    if not admin:
        admin = User(
            email=settings.DEFAULT_ADMIN_EMAIL,
            hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
            full_name=settings.DEFAULT_ADMIN_NAME,
            role="admin",
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        # Log system event
        audit = AuditLog(
            user_id=admin.id,
            action="INITIALIZE_ADMIN",
            entity_type="User",
            entity_id=str(admin.id),
            details="Default administrator account initialized."
        )
        db.add(audit)
        db.commit()
    return admin

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticates a user via email and plain password."""
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, str(user.hashed_password)):
        return None
    return user

def setup_intern_password(db: Session, token: str, password: str) -> Tuple[bool, str, Optional[User]]:
    """Activates an intern account and sets password using invitation token."""
    intern = db.query(Intern).filter(Intern.invitation_token == token).first()
    if not intern:
        return False, "Invalid or expired invitation token.", None
        
    user = intern.user
    if not user:
        # Create user account if not yet attached
        user = User(
            email=intern.email,
            hashed_password=get_password_hash(password),
            full_name=intern.name,
            role="intern",
            is_active=True
        )
        db.add(user)
        db.flush()
        intern.user_id = user.id
    else:
        user.hashed_password = get_password_hash(password)
        user.is_active = True
        
    intern.invitation_token = None  # Consume token
    intern.is_invited = True
    
    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="ACCOUNT_ACTIVATED",
        entity_type="Intern",
        entity_id=str(intern.id),
        details=f"Intern {intern.name} activated their account."
    )
    db.add(audit)
    db.commit()
    db.refresh(user)
    return True, "Account successfully activated.", user

def reset_password(db: Session, email: str, new_password: str) -> Tuple[bool, str]:
    """Resets user password."""
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        return False, "User with this email not found."
    user.hashed_password = get_password_hash(new_password)
    
    audit = AuditLog(
        user_id=user.id,
        action="PASSWORD_RESET",
        entity_type="User",
        entity_id=str(user.id),
        details=f"Password reset for {user.email}."
    )
    db.add(audit)
    db.commit()
    return True, "Password has been successfully reset."

