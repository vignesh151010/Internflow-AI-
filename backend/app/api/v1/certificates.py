import os
from pathlib import Path
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.certificate import Certificate
from app.models.intern import Intern
from app.services.certificate_service import certificate_service

router = APIRouter()

@router.get("/verify/{certificate_number}")
def public_verify_certificate(
    certificate_number: str,
    db: Session = Depends(get_db)
) -> Any:
    """
    Public verification endpoint to authenticate certificate credentials and QR scans.
    Accessible without login.
    """
    result = certificate_service.verify_certificate(certificate_number, db)
    if not result.get("valid"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result

@router.get("/{certificate_number}/download")
def download_certificate_pdf(
    certificate_number: str,
    db: Session = Depends(get_db)
) -> Any:
    """Downloads the official PDF certificate file."""
    cert = db.query(Certificate).filter(Certificate.certificate_number == certificate_number).first()
    if not cert or not cert.file_path or not os.path.exists(cert.file_path):
        raise HTTPException(status_code=404, detail="Certificate PDF file not found.")

    return FileResponse(
        path=cert.file_path,
        filename=f"InternFlow_Certificate_{cert.certificate_number}.pdf",
        media_type="application/pdf"
    )

@router.get("/eligibility/{intern_id}")
def check_certificate_eligibility(
    intern_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Evaluates whether an intern satisfies certificate issuance criteria."""
    intern = db.query(Intern).filter(Intern.id == intern_id).first()
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found.")
    return certificate_service.check_eligibility(intern, db)

@router.post("/issue/{intern_id}")
def admin_issue_certificate(
    intern_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Admin approves and generates the official PDF certificate with embedded QR code."""
    try:
        cert = certificate_service.issue_certificate(intern_id, db, admin_override=True)
        return {
            "success": True,
            "message": f"Certificate {cert.certificate_number} successfully issued and dispatched via email.",
            "certificate_number": cert.certificate_number,
            "grade": cert.grade,
            "issue_date": cert.issue_date.isoformat(),
            "download_url": f"/api/v1/certificates/{cert.certificate_number}/download"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/roster")
def list_certificates(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Lists all certificates generated across the platform."""
    certs = db.query(Certificate).order_by(Certificate.issue_date.desc()).all()
    return [
        {
            "id": c.id,
            "certificate_number": c.certificate_number,
            "intern_id": c.intern_id,
            "intern_name": c.intern.name if c.intern else "Unknown",
            "domain": c.intern.domain if c.intern else "Engineering",
            "grade": c.grade,
            "issue_date": c.issue_date.isoformat(),
            "verification_hash": c.verification_hash,
            "file_available": bool(c.file_path and os.path.exists(c.file_path)),
            "download_url": f"/api/v1/certificates/{c.certificate_number}/download"
        }
        for c in certs
    ]

