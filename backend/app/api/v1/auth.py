from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.models.intern import Intern
from app.models.log import AuditLog
from app.schemas.auth import (
    Token,
    LoginRequest,
    RegisterRequest,
    PasswordResetRequest,
    PasswordSetupRequest
)
from app.services.auth_service import (
    authenticate_user,
    setup_intern_password,
    reset_password,
    register_new_intern,
    check_login_rate_limit,
    record_failed_login,
    clear_failed_logins
)

router = APIRouter()


@router.post("/register")
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Public registration endpoint for new interns.
    Strictly provisions accounts with role 'intern' (never admin).
    Validates mandatory fields, password match, security requirements, and uniqueness.
    """
    success, msg, user = register_new_intern(
        db=db,
        full_name=data.full_name,
        email=data.email,
        password=data.password,
        confirm_password=data.confirm_password
    )
    if not success or not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg
        )

    return {
        "success": True,
        "message": msg,
        "email": user.email,
        "role": user.role
    }


@router.post("/login", response_model=Token)
def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> Any:
    """
    User authentication for Admin or Intern using JSON payload.
    Features brute-force rate limit protection and role-based token claims.
    """
    client_ip = request.client.host if request.client else "unknown"
    client_id = f"{login_data.email.strip().lower()}:{client_ip}"

    # Rate limiting check
    allowed, rate_err = check_login_rate_limit(client_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_err or "Too many failed login attempts. Please try again later."
        )

    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        record_failed_login(client_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email address or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Clear failed attempt counter on success
    clear_failed_logins(client_id)

    intern_id = None
    if user.role == "intern" and user.intern_profile:
        intern_id = user.intern_profile.id
    elif user.role == "intern":
        # Look up by email
        intern = db.query(Intern).filter(Intern.email == user.email).first()
        if intern:
            intern_id = intern.id
            if not intern.user_id:
                intern.user_id = user.id
                db.commit()

    access_token = create_access_token(
        subject=str(user.id),
        role=str(user.role),
        extra_claims={
            "email": user.email,
            "name": user.full_name,
            "intern_id": intern_id
        }
    )

    # Log login action
    try:
        audit = AuditLog(
            user_id=user.id,
            action="USER_LOGIN",
            entity_type="User",
            entity_id=str(user.id),
            details=f"User {user.email} logged in ({user.role.upper()})."
        )
        db.add(audit)
        db.commit()
    except Exception:
        pass

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
        "intern_id": intern_id,
        "name": user.full_name,
        "email": user.email
    }


@router.post("/setup-password", response_model=Token)
def setup_password(
    data: PasswordSetupRequest,
    db: Session = Depends(get_db)
) -> Any:
    """Secure invitation activation and password setup flow for new interns."""
    if data.password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match."
        )
    if len(data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )

    success, msg, user = setup_intern_password(
        db, data.invitation_token.strip(), data.password
    )
    if not success or not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg
        )

    intern_id = user.intern_profile.id if user.intern_profile else None
    access_token = create_access_token(
        subject=str(user.id),
        role=str(user.role),
        extra_claims={
            "email": user.email,
            "name": user.full_name,
            "intern_id": intern_id
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
        "intern_id": intern_id,
        "name": user.full_name,
        "email": user.email
    }


@router.post("/reset-password")
def handle_reset_password(
    data: PasswordResetRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Resets user password safely without exposing email existence to attackers.
    """
    if len(data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters long."
        )

    success, msg = reset_password(db, data.email, data.new_password)
    # Return generic success response to prevent email enumeration
    return {
        "success": True,
        "message": (
            "If an account is associated with this email address, "
            "the password has been reset successfully. You may now sign in."
        )
    }
