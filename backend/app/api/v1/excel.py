import os
import shutil
import logging
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_admin
from app.models.user import User
from app.schemas.excel import ExcelUploadResponse, ExcelApproveRequest
from app.services.excel_service import process_excel_file, approve_and_import_interns, create_sample_excel_template
from app.services.ollama_service import ollama_service

router = APIRouter()

@router.post("/upload", response_model=ExcelUploadResponse)
def upload_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Uploads Excel spreadsheet, inspects columns, validates records, returns preview for admin review."""
    if not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload an Excel (.xlsx or .xls) file."
        )

    # Save to uploads directory
    save_path = settings.UPLOAD_DIR / f"upload_{file.filename}"
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        preview_response = process_excel_file(save_path, db)
        return preview_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process Excel file: {str(e)}"
        )

@router.post("/approve")
def approve_excel_data(
    request: ExcelApproveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
) -> Any:
    """Admin approves previewed/corrected Excel data. Inserts into SQLite and triggers workflows."""
    if not request.approved_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No rows were submitted for approval."
        )

    count_imported, interns, errors = approve_and_import_interns(
        request.approved_rows,
        current_admin_user=admin,
        db=db
    )

    # If requested, automatically generate AI roadmaps
    generated_roadmaps_count = 0
    if request.generate_roadmaps_automatically:
        for intern in interns:
            try:
                roadmaps = ollama_service.create_roadmap_for_intern(intern, db)
                if roadmaps:
                    generated_roadmaps_count += 1
            except Exception as e:
                errors.append(f"Roadmap generation warning for {intern.name}: {str(e)}")

    # Initialize complete automated lifecycle for each imported intern
    from app.services.automation_service import automation_service
    for intern in interns:
        try:
            automation_service.initialize_intern_workflow(intern.id, db)
        except Exception as e:
            errors.append(f"Workflow automation initialization error for {intern.name}: {str(e)}")

    # Run immediate pending lifecycle jobs
    try:
        automation_service.run_pending_jobs(db)
    except Exception as e:
        logger.error(f"Error running initial lifecycle jobs: {e}")

    return {
        "success": True,
        "imported_count": count_imported,
        "roadmaps_generated_count": generated_roadmaps_count,
        "errors": errors,
        "message": f"Successfully created {count_imported} intern accounts and launched individual automated workflows."
    }

@router.get("/download-template")
def download_sample_template() -> Any:
    """Generates and serves sample Excel file template for testing and demonstration."""
    template_path = settings.DATA_DIR / "sample_template" / "internflow_sample_import.xlsx"
    create_sample_excel_template(template_path)
    return FileResponse(
        path=template_path,
        filename="internflow_sample_template.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

