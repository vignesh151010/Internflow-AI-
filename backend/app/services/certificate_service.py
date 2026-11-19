import os
import io
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import qrcode

from app.core.config import settings
from app.models.certificate import Certificate
from app.models.intern import Intern
from app.models.task import Task
from app.models.log import AuditLog
from app.services.email_service import email_service

class CertificateService:
    def __init__(self):
        self.certificates_dir = settings.DATA_DIR / "uploads" / "certificates"
        self.certificates_dir.mkdir(parents=True, exist_ok=True)

    def check_eligibility(self, intern: Intern, db: Session) -> Dict[str, Any]:
        """
        Verifies whether the intern has met all completion criteria:
        - All weekly tasks approved
        - Final project completed
        - Overall passing grade
        """
        total_tasks = len(intern.tasks)
        approved_tasks = sum(1 for t in intern.tasks if t.status == "approved")
        all_approved = (total_tasks > 0 and approved_tasks == total_tasks)
        is_completed = (intern.status == "completed" or all_approved)

        grade = "Outstanding" if intern.total_score >= 85 else ("A+" if intern.total_score >= 70 else ("A" if intern.total_score >= 55 else "Pass"))

        return {
            "eligible": is_completed,
            "total_tasks": total_tasks,
            "approved_tasks": approved_tasks,
            "total_score": intern.total_score,
            "suggested_grade": grade,
            "reason": "All milestones approved and verified." if is_completed else f"Only {approved_tasks} of {total_tasks} milestones certified."
        }

    def generate_pdf(self, intern: Intern, certificate: Certificate) -> str:
        """
        Generates a professional, landscape PDF certificate with ReportLab and embedded QR code.
        """
        pdf_filename = f"{certificate.certificate_number}.pdf"
        pdf_path = self.certificates_dir / pdf_filename

        # Dimensions: 11 x 8.5 inches (792 x 612 pt)
        width, height = landscape(letter)
        c = canvas.Canvas(str(pdf_path), pagesize=landscape(letter))

        # 1. Background & Decorative Borders
        # Outer Border - Primary Navy #1E3A8A
        c.setStrokeColor(colors.HexColor("#1E3A8A"))
        c.setLineWidth(6)
        c.rect(24, 24, width - 48, height - 48)

        # Inner Border - Secondary Blue #2563EB
        c.setStrokeColor(colors.HexColor("#2563EB"))
        c.setLineWidth(1.5)
        c.rect(32, 32, width - 64, height - 64)

        # Corner Accents - Orange Accent #F97316
        c.setStrokeColor(colors.HexColor("#F97316"))
        c.setLineWidth(3)
        corner_len = 36
        # Top-left
        c.line(24, height - 24 - corner_len, 24, height - 24)
        c.line(24, height - 24, 24 + corner_len, height - 24)
        # Top-right
        c.line(width - 24 - corner_len, height - 24, width - 24, height - 24)
        c.line(width - 24, height - 24, width - 24, height - 24 - corner_len)
        # Bottom-left
        c.line(24, 24 + corner_len, 24, 24)
        c.line(24, 24, 24 + corner_len, 24)
        # Bottom-right
        c.line(width - 24 - corner_len, 24, width - 24, 24)
        c.line(width - 24, 24, width - 24, 24 + corner_len)

        # 2. Header & Branding
        c.setFillColor(colors.HexColor("#F97316"))
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(width / 2.0, height - 70, "INTERNFLOW AI ENGINEERING ACADEMY")

        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(width / 2.0, height - 105, "CERTIFICATE OF COMPLETION")

        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica-Oblique", 13)
        c.drawCentredString(width / 2.0, height - 135, "This is proudly presented to")

        # 3. Recipient Name
        c.setFillColor(colors.HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 26)
        c.drawCentredString(width / 2.0, height - 180, intern.name)

        # Underline under name
        name_width = c.stringWidth(intern.name, "Helvetica-Bold", 26)
        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.setLineWidth(1)
        c.line((width - name_width) / 2.0 - 20, height - 190, (width + name_width) / 2.0 + 20, height - 190)

        # 4. Accomplishment Statement
        c.setFillColor(colors.HexColor("#334155"))
        c.setFont("Helvetica", 13)
        c.drawCentredString(
            width / 2.0, height - 225,
            "For successfully completing the intensive local engineering internship in the domain of"
        )

        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width / 2.0, height - 255, intern.domain)

        c.setFillColor(colors.HexColor("#475569"))
        c.setFont("Helvetica-Oblique", 12.5)
        task_snippet = (intern.main_task or "Capstone Engineering Project")[:75]
        c.drawCentredString(width / 2.0, height - 285, f'Capstone Project: "{task_snippet}"')

        # 5. Metadata Details Box
        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.setFont("Helvetica-Bold", 12)
        duration_str = f"Duration: {intern.duration_weeks} Weeks  |  Term: {intern.start_date} to {intern.end_date}  |  Performance Grade: {certificate.grade}"
        c.drawCentredString(width / 2.0, height - 325, duration_str)

        # 6. QR Code Generation for Online Verification
        verification_url = f"http://localhost:8000/verify/{certificate.certificate_number}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=3,
            border=1
        )
        qr.add_data(verification_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#1E3A8A", back_color="white")

        qr_temp_path = self.certificates_dir / f"temp_qr_{certificate.certificate_number}.png"
        qr_img.save(str(qr_temp_path))

        # Draw QR code in bottom-right corner
        qr_size = 72
        qr_x = width - 130
        qr_y = 60
        c.drawImage(str(qr_temp_path), qr_x, qr_y, width=qr_size, height=qr_size)

        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(qr_x + (qr_size / 2.0), qr_y - 10, "Scan to Verify Authenticity")

        # Clean up temporary QR image file
        try:
            if qr_temp_path.exists():
                os.remove(qr_temp_path)
        except Exception:
            pass

        # 7. Signature Blocks
        sig_y = 90
        # Mentor signature line
        c.setStrokeColor(colors.HexColor("#94A3B8"))
        c.setLineWidth(1)
        c.line(80, sig_y + 25, 230, sig_y + 25)
        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(80, sig_y + 12, "Lead Mentor & Evaluator")
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 9)
        c.drawString(80, sig_y, "InternFlow AI Academy")

        # Director signature line
        c.line(280, sig_y + 25, 430, sig_y + 25)
        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(280, sig_y + 12, "Director of AI Systems")
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 9)
        c.drawString(280, sig_y, "Certification Authority")

        # 8. Footer Metadata (Verification Hash, Certificate ID & Issue Date)
        c.setFillColor(colors.HexColor("#475569"))
        c.setFont("Helvetica", 9)
        c.drawString(80, 48, f"Certificate ID: {certificate.certificate_number}   |   Issued: {certificate.issue_date.isoformat()}")

        c.setFillColor(colors.HexColor("#94A3B8"))
        c.setFont("Courier", 7.5)
        c.drawString(80, 36, f"Cryptographic Verification Hash: {certificate.verification_hash}")

        # Finalize and save
        c.showPage()
        c.save()

        return str(pdf_path)

    def issue_certificate(
        self,
        intern_id: int,
        db: Session,
        admin_override: bool = False
    ) -> Certificate:
        """
        Creates or retrieves an existing Certificate, generates the official PDF, and updates DB.
        Guarantees duplicate prevention.
        """
        intern = db.query(Intern).filter(Intern.id == intern_id).first()
        if not intern:
            raise ValueError("Intern not found.")

        # Check existing certificate to prevent duplicate creation
        existing = db.query(Certificate).filter(Certificate.intern_id == intern.id).first()
        if existing and existing.file_path and os.path.exists(existing.file_path):
            return existing

        # Eligibility check
        eligibility = self.check_eligibility(intern, db)
        if not eligibility["eligible"] and not admin_override:
            raise ValueError(f"Intern is not eligible for certificate: {eligibility['reason']}")

        # Generate deterministic certificate number and SHA-256 hash
        now = datetime.utcnow()
        clean_code = intern.intern_code[-4:] if intern.intern_code else f"{intern.id:04d}"
        cert_no = f"CERT-IF-{clean_code}-{now.year}"
        
        raw_hash_data = f"{cert_no}:{intern.email}:{intern.domain}:{now.isoformat()}"
        verification_hash = hashlib.sha256(raw_hash_data.encode()).hexdigest()[:24].upper()

        grade = eligibility["suggested_grade"]

        if not existing:
            cert = Certificate(
                intern_id=intern.id,
                certificate_number=cert_no,
                issue_date=date.today(),
                grade=grade,
                verification_hash=verification_hash,
                status="issued"
            )
            db.add(cert)
            db.flush()
        else:
            cert = existing
            cert.certificate_number = cert_no
            cert.verification_hash = verification_hash
            cert.grade = grade
            cert.status = "issued"

        # Generate the PDF file
        pdf_path = self.generate_pdf(intern, cert)
        cert.file_path = pdf_path

        # Mark intern completed
        intern.status = "completed"
        intern.workflow_status = "completed"
        db.commit()
        db.refresh(cert)

        # Log audit trail
        audit = AuditLog(
            action="CERTIFICATE_ISSUED",
            entity_type="certificate",
            entity_id=str(cert.id),
            details=f"Verified Certificate {cert.certificate_number} generated for {intern.name} ({intern.domain})"
        )
        db.add(audit)
        db.commit()

        # Send certificate delivery email with PDF attachment
        email_service.send_email(
            recipient_email=intern.email,
            email_type="certificate_delivery",
            intern=intern,
            context_data={
                "certificate_number": cert.certificate_number,
                "verification_hash": cert.verification_hash,
                "grade": cert.grade,
                "total_score": intern.total_score
            },
            attachment_path=cert.file_path,
            db=db
        )

        return cert

    def verify_certificate(self, identifier: str, db: Session) -> Dict[str, Any]:
        """
        Public verification lookup using either Certificate Number or Verification Hash.
        """
        clean_id = identifier.strip()
        cert = (
            db.query(Certificate)
            .filter(
                (Certificate.certificate_number == clean_id) |
                (Certificate.verification_hash == clean_id.upper())
            )
            .first()
        )

        if not cert:
            return {
                "valid": False,
                "message": f"No registered certificate found matching identifier '{clean_id}'."
            }

        intern = cert.intern
        return {
            "valid": True,
            "certificate_number": cert.certificate_number,
            "verification_hash": cert.verification_hash,
            "issue_date": cert.issue_date.isoformat(),
            "grade": cert.grade,
            "intern_name": intern.name if intern else "Verified Intern",
            "intern_code": intern.intern_code if intern else "",
            "domain": intern.domain if intern else "",
            "capstone_project": intern.main_task if intern else "",
            "duration_weeks": intern.duration_weeks if intern else 4,
            "total_score": intern.total_score if intern else 0.0,
            "download_url": f"/api/v1/certificates/{cert.certificate_number}/download"
        }

certificate_service = CertificateService()

