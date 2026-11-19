import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from sqlalchemy.orm import Session

from app.models.intern import Intern
from app.models.user import User
from app.models.log import AuditLog, EmailLog
from app.core.security import get_password_hash, generate_secure_token
from app.schemas.excel import ExcelPreviewRow, ExcelUploadResponse, ExcelApproveRow

# Canonical column names
CANONICAL_COLUMNS = {
    "name": ["intern name", "name", "student name", "candidate name", "full name"],
    "email": ["email address", "email", "mail", "e-mail", "email_id"],
    "domain": ["domain", "track", "specialization", "department", "stream", "field"],
    "main_task": ["main assigned task", "main task", "assigned task", "project", "project title", "task title"],
    "task_description": ["task description", "description", "project description", "details", "summary", "scope"],
    "start_date": ["internship start date", "start date", "joining date", "commencement date", "from date"],
    "duration_weeks": ["internship duration", "duration", "duration (weeks)", "duration_weeks", "weeks", "period"],
    "end_date": ["internship end date", "end date", "completion date", "to date"]
}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def map_column_header(header: str) -> Optional[str]:
    """Matches a header string to one of the canonical column names."""
    norm = str(header).strip().lower().replace("_", " ")
    for canonical, variations in CANONICAL_COLUMNS.items():
        if norm in variations:
            return canonical
        for var in variations:
            if var in norm or norm in var:
                return canonical
    return None

def parse_date_value(val: Any) -> Optional[date]:
    """Parses various date formats from Excel or strings."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date()
    if isinstance(val, date):
        return val
        
    s = str(val).strip()
    if not s:
        return None
        
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y",
        "%Y/%m/%d", "%d.%m.%Y", "%B %d, %Y", "%b %d, %Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def parse_duration_weeks(val: Any) -> int:
    """Parses duration in weeks."""
    if val is None or pd.isna(val):
        return 4
    if isinstance(val, (int, float)):
        return max(1, int(val))
    s = str(val).lower()
    # Extract first number
    match = re.search(r"\d+", s)
    if match:
        return max(1, int(match.group()))
    return 4

def process_excel_file(file_path: Path, db: Session) -> ExcelUploadResponse:
    """Reads Excel file, auto-maps columns, validates rows, detects duplicates."""
    df = pd.read_excel(file_path)
    
    # 1. Map columns
    detected_columns: Dict[str, str] = {}
    mapped_df_cols: Dict[str, str] = {}
    
    for col in df.columns:
        canonical = map_column_header(col)
        if canonical and canonical not in mapped_df_cols:
            mapped_df_cols[canonical] = col
            detected_columns[canonical] = str(col)
            
    # Check for missing required canonical columns
    required_canonicals = ["name", "email", "domain", "main_task"]
    missing_required = [c for c in required_canonicals if c not in mapped_df_cols]
    
    # Get all existing intern emails from DB for duplicate checking
    existing_emails = set(e[0].lower() for e in db.query(Intern.email).all())
    
    preview_rows: List[ExcelPreviewRow] = []
    seen_file_emails = set()
    valid_count = 0
    invalid_count = 0
    
    for idx, row in df.iterrows():
        errors: List[str] = []
        warnings: List[str] = []
        is_duplicate = False
        
        # Extract fields using mapped column or default
        def get_val(canonical_key: str, default: Any = "") -> Any:
            col_name = mapped_df_cols.get(canonical_key)
            if col_name and col_name in row:
                val = row[col_name]
                return "" if pd.isna(val) else val
            return default

        name = str(get_val("name", "")).strip()
        email = str(get_val("email", "")).strip().lower()
        domain = str(get_val("domain", "General Internship")).strip()
        main_task = str(get_val("main_task", "")).strip()
        task_description = str(get_val("task_description", "")).strip()
        
        raw_start_date = get_val("start_date", None)
        raw_duration = get_val("duration_weeks", 4)
        raw_end_date = get_val("end_date", None)
        
        start_date_obj = parse_date_value(raw_start_date)
        duration_weeks_val = parse_duration_weeks(raw_duration)
        end_date_obj = parse_date_value(raw_end_date)
        
        # Validation checks
        if not name:
            errors.append("Missing intern name.")
            
        if not email:
            errors.append("Missing email address.")
        elif not EMAIL_REGEX.match(email):
            errors.append(f"Invalid email format: '{email}'.")
        else:
            if email in seen_file_emails:
                errors.append(f"Duplicate email within Excel file: '{email}'.")
                is_duplicate = True
            elif email in existing_emails:
                errors.append(f"Intern with email '{email}' already registered in system.")
                is_duplicate = True
            seen_file_emails.add(email)
            
        if not domain:
            warnings.append("Domain missing; defaulted to 'General Internship'.")
            domain = "General Internship"
            
        if not main_task:
            errors.append("Missing main assigned task/project title.")
            
        # Date resolution
        if not start_date_obj:
            start_date_obj = date.today()
            warnings.append("Start date missing; defaulted to today.")
            
        if not end_date_obj:
            end_date_obj = start_date_obj + timedelta(weeks=duration_weeks_val)
        else:
            if end_date_obj <= start_date_obj:
                errors.append("End date must be after Start date.")
                
        is_valid = len(errors) == 0
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            
        preview_rows.append(ExcelPreviewRow(
            row_index=idx + 1,
            name=name,
            email=email,
            domain=domain,
            main_task=main_task,
            task_description=task_description,
            start_date=start_date_obj.isoformat(),
            duration_weeks=duration_weeks_val,
            end_date=end_date_obj.isoformat(),
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            is_duplicate=is_duplicate
        ))
        
    summary_message = (
        f"Processed {len(df)} rows: {valid_count} ready for import, "
        f"{invalid_count} requiring review or correction."
    )
    if missing_required:
        summary_message += f" Note: Missing standard column mappings: {', '.join(missing_required)}."

    return ExcelUploadResponse(
        filename=file_path.name,
        total_rows=len(df),
        valid_rows_count=valid_count,
        invalid_rows_count=invalid_count,
        detected_columns=detected_columns,
        rows=preview_rows,
        summary_message=summary_message
    )

def approve_and_import_interns(
    approved_rows: List[ExcelApproveRow],
    current_admin_user: User,
    db: Session
) -> Tuple[int, List[Intern], List[str]]:
    """Imports approved rows into SQLite, creates Intern accounts, User logins, invitations."""
    imported_interns: List[Intern] = []
    error_logs: List[str] = []
    
    current_year = datetime.now().year
    
    for row in approved_rows:
        try:
            # Check if email already exists
            existing = db.query(Intern).filter(Intern.email == row.email.strip().lower()).first()
            if existing:
                error_logs.append(f"Skipped {row.email}: Already registered.")
                continue
                
            start_date_obj = parse_date_value(row.start_date) or date.today()
            end_date_obj = parse_date_value(row.end_date) or (start_date_obj + timedelta(weeks=row.duration_weeks))
            
            # Count interns for unique code
            count = db.query(Intern).count() + 1
            intern_code = f"IF-{current_year}-{count:04d}"
            invite_token = generate_secure_token(16)
            
            # 1. Create Intern Record
            intern = Intern(
                intern_code=intern_code,
                name=row.name.strip(),
                email=row.email.strip().lower(),
                domain=row.domain.strip(),
                main_task=row.main_task.strip(),
                task_description=row.task_description.strip() if row.task_description else None,
                start_date=start_date_obj,
                duration_weeks=row.duration_weeks,
                end_date=end_date_obj,
                status="active",
                current_week=1,
                total_score=0.0,
                invitation_token=invite_token,
                is_invited=True,
                invitation_sent_at=datetime.utcnow()
            )
            db.add(intern)
            db.flush()
            
            # 2. Create corresponding User login record with initial temporary password
            # Default password is e.g. Intern@2026 or activation token
            temp_password = f"Intern@{intern.intern_code[-4:]}"
            user = User(
                email=intern.email,
                hashed_password=get_password_hash(temp_password),
                full_name=intern.name,
                role="intern",
                is_active=True
            )
            db.add(user)
            db.flush()
            
            # Link user to intern
            intern.user_id = user.id
            
            # 3. Log Simulated Email
            email_log = EmailLog(
                recipient_email=intern.email,
                subject=f"Welcome to InternFlow AI - Internship Activation ({intern.intern_code})",
                body_preview=f"Hello {intern.name}, welcome to your {intern.domain} internship on '{intern.main_task}'. Use invite token: {invite_token} or default password '{temp_password}' to log in.",
                email_type="invite",
                status="simulated_local"
            )
            db.add(email_log)
            
            imported_interns.append(intern)
        except Exception as e:
            error_logs.append(f"Error importing {row.email}: {str(e)}")
            
    # Record admin audit log
    audit = AuditLog(
        user_id=current_admin_user.id,
        action="EXCEL_IMPORT_APPROVED",
        entity_type="Intern",
        entity_id="batch",
        details=f"Admin {current_admin_user.full_name} approved {len(imported_interns)} interns from Excel."
    )
    db.add(audit)
    db.commit()
    
    return len(imported_interns), imported_interns, error_logs

def create_sample_excel_template(output_path: Path) -> Path:
    """Creates a sample Excel file with realistic test intern data across domains."""
    sample_data = [
        {
            "Intern Name": "Aarav Sharma",
            "Email Address": "aarav.sharma@example.com",
            "Domain": "AI / Machine Learning",
            "Main Assigned Task": "Intelligent Document Q&A Engine using RAG",
            "Task Description": "Build a local retrieval-augmented generation pipeline using LangChain, Vector Embeddings, and Ollama LLM to query company PDF documents with source citations.",
            "Internship Start Date": date.today().strftime("%Y-%m-%d"),
            "Internship Duration": 4,
            "Internship End Date": (date.today() + timedelta(weeks=4)).strftime("%Y-%m-%d")
        },
        {
            "Intern Name": "Priya Nair",
            "Email Address": "priya.nair@example.com",
            "Domain": "Full Stack Web Development",
            "Main Assigned Task": "Multi-Tenant E-Commerce Dashboard with Real-Time Analytics",
            "Task Description": "Develop responsive frontend in HTML/Tailwind/React with FastAPI backend, order management, inventory control, and WebSockets live sales updates.",
            "Internship Start Date": date.today().strftime("%Y-%m-%d"),
            "Internship Duration": 4,
            "Internship End Date": (date.today() + timedelta(weeks=4)).strftime("%Y-%m-%d")
        },
        {
            "Intern Name": "Rohan Verma",
            "Email Address": "rohan.verma@example.com",
            "Domain": "Cloud & DevOps",
            "Main Assigned Task": "Containerized CI/CD Deployment Pipeline & Monitoring",
            "Task Description": "Create Dockerized microservices environment, automated GitHub Actions workflow, health check probes, Prometheus metrics, and Grafana dashboard.",
            "Internship Start Date": date.today().strftime("%Y-%m-%d"),
            "Internship Duration": 4,
            "Internship End Date": (date.today() + timedelta(weeks=4)).strftime("%Y-%m-%d")
        },
        {
            "Intern Name": "Sneha Patel",
            "Email Address": "sneha.patel@example.com",
            "Domain": "Cybersecurity",
            "Main Assigned Task": "Automated Web Vulnerability Scanner & Audit Reporter",
            "Task Description": "Design security scanner for OWASP Top 10 vulnerabilities (SQLi, XSS, CSRF, insecure headers), generating structured executive PDF audit reports.",
            "Internship Start Date": date.today().strftime("%Y-%m-%d"),
            "Internship Duration": 4,
            "Internship End Date": (date.today() + timedelta(weeks=4)).strftime("%Y-%m-%d")
        }
    ]
    df = pd.DataFrame(sample_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)
    return output_path

