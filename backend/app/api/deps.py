from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.intern import Intern

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Extracts and verifies JWT token, returning the authenticated User."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id_int).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensures current user possesses the admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to access resource."
        )
    return current_user


def get_current_intern_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Intern:
    """Ensures current user is an intern and retrieves their Intern profile."""
    if current_user.role == "intern":
        intern = (
            db.query(Intern)
            .filter(Intern.user_id == current_user.id)
            .first()
        )
        if not intern:
            # Fallback search by email
            intern = (
                db.query(Intern)
                .filter(Intern.email == current_user.email)
                .first()
            )
        if not intern:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intern profile not associated with this account."
            )
        return intern
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Intern credentials required to access this resource."
    )
