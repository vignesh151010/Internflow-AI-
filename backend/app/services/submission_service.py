import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
import pypdf
import docx

from app.core.config import settings
from app.models.submission import Submission
from app.models.task import Task
from app.models.intern import Intern
from app.models.log import AuditLog

class SubmissionService:
    def __init__(self):
        self.submissions_dir = settings.UPLOAD_DIR / "submissions"
        self.submissions_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = settings.MAX_FILE_SIZE_BYTES
        self.allowed_extensions = settings.ALLOWED_EXTENSIONS

    def validate_file(self, file: UploadFile) -> str:
        """Validates extension and returns normalized suffix."""
        filename = file.filename or ""
        ext = Path(filename).suffix.lower()
        if ext not in self.allowed_extensions:
            allowed_list = ", ".join(sorted(list(self.allowed_extensions)))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{ext}' is not permitted. Allowed: {allowed_list}"
            )
        return ext

    def safely_extract_text_content(self, file_path: Path, ext: str) -> str:
        """
        Safely extracts readable text content from submitted files for AI evaluation.
        NEVER executes untrusted code.
        """
        extracted = []
        try:
            # Source code or text
            if ext in {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".sql", ".json", ".md", ".txt"}:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(50000)  # Safe limit 50KB text
                    extracted.append(f"--- File: {file_path.name} ---\n{content}")

            # PDF Files
            elif ext == ".pdf":
                reader = pypdf.PdfReader(str(file_path))
                text_pages = []
                for i in range(min(15, len(reader.pages))):
                    page_text = reader.pages[i].extract_text()
                    if page_text:
                        text_pages.append(page_text)
                extracted.append(f"--- PDF Document ({len(reader.pages)} pages) ---\n" + "\n".join(text_pages)[:50000])

            # DOCX Files
            elif ext == ".docx":
                doc = docx.Document(str(file_path))
                doc_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                extracted.append("--- DOCX Document ---\n" + doc_text[:50000])

            # PPTX or other binary documents
            elif ext == ".pptx":
                extracted.append(f"--- Presentation Deliverable: {file_path.name} (Binary PPTX) ---")

            # ZIP Archives
            elif ext == ".zip":
                extracted.append(f"--- ZIP Archive: {file_path.name} ---")
                with zipfile.ZipFile(str(file_path), "r") as z:
                    file_list = z.namelist()
                    extracted.append(f"Contained Files ({len(file_list)} items):\n" + "\n".join(file_list[:30]))
                    # Read sample code files from ZIP safely
                    for member in file_list[:5]:
                        if any(member.endswith(s) for s in [".py", ".js", ".html", ".md", ".json"]):
                            try:
                                with z.open(member) as zf:
                                    code_sample = zf.read(15000).decode("utf-8", errors="ignore")
                                    extracted.append(f"\n--- Code Sample [{member}] ---\n{code_sample}")
                            except Exception:
                                pass
        except Exception as e:
            extracted.append(f"Note: Text extraction limited for {file_path.name} ({str(e)}).")

        return "\n".join(extracted)

    def process_task_submission(
        self,
        task_id: int,
        intern: Intern,
        submission_link: Optional[str],
        notes: Optional[str],
        file: Optional[UploadFile],
        db: Session
    ) -> Submission:
        """
        Creates or updates a task submission, managing versioning (v1, v2, v3) for resubmissions.
        """
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found.")
            
        if task.intern_id != intern.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Cannot submit deliverables for another intern's task."
            )

        # Determine version counter
        existing_submissions = (
            db.query(Submission)
            .filter(Submission.task_id == task.id, Submission.intern_id == intern.id)
            .order_by(Submission.version.desc())
            .all()
        )
        new_version = (existing_submissions[0].version + 1) if existing_submissions else 1

        # Mark previous submissions as not latest
        for prev in existing_submissions:
            prev.is_latest = False

        saved_file_path = None
        file_type = None
        file_size = None
        extracted_text = ""

        # Handle file upload if present
        if file and file.filename:
            ext = self.validate_file(file)
            file_type = ext

            # Create versioned directory: data/uploads/submissions/<intern_code>/task_<id>/v<version>/
            version_dir = self.submissions_dir / intern.intern_code / f"task_{task.id}" / f"v{new_version}"
            version_dir.mkdir(parents=True, exist_ok=True)
            
            # Safe filename
            safe_filename = Path(file.filename).name
            target_file_path = version_dir / safe_filename

            # Read and verify size limit
            content = file.file.read()
            file_size = len(content)
            if file_size > self.max_file_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File exceeds maximum allowed size of 25 MB ({round(file_size / (1024*1024), 2)} MB uploaded)."
                )

            with open(target_file_path, "wb") as f_out:
                f_out.write(content)

            saved_file_path = str(target_file_path)
            extracted_text = self.safely_extract_text_content(target_file_path, ext)

        # Contextual notes if link provided
        if submission_link:
            extracted_text += f"\nRepository / Deliverable Link: {submission_link}"
        if notes:
            extracted_text += f"\nIntern Implementation Notes: {notes}"

        submission = Submission(
            task_id=task.id,
            intern_id=intern.id,
            submission_link=submission_link,
            file_path=saved_file_path,
            version=new_version,
            file_type=file_type,
            file_size_bytes=file_size,
            is_latest=True,
            extracted_text=extracted_text,
            notes=notes,
            status="submitted",
            submitted_at=datetime.utcnow()
        )
        db.add(submission)
        task.status = "submitted"

        audit = AuditLog(
            user_id=intern.user_id,
            action="TASK_SUBMITTED",
            entity_type="Submission",
            entity_id=str(task.id),
            details=f"Intern {intern.name} submitted milestone '{task.title}' (Version {new_version})."
        )
        db.add(audit)
        db.commit()
        db.refresh(submission)

        return submission

submission_service = SubmissionService()
