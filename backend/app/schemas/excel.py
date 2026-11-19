from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr

class ExcelPreviewRow(BaseModel):
    row_index: int
    name: str
    email: str
    domain: str
    main_task: str
    task_description: Optional[str] = ""
    start_date: str
    duration_weeks: int
    end_date: str
    is_valid: bool = True
    errors: List[str] = []
    warnings: List[str] = []
    is_duplicate: bool = False

class ExcelUploadResponse(BaseModel):
    filename: str
    total_rows: int
    valid_rows_count: int
    invalid_rows_count: int
    detected_columns: Dict[str, str]
    rows: List[ExcelPreviewRow]
    summary_message: str

class ExcelApproveRow(BaseModel):
    row_index: int
    name: str
    email: EmailStr
    domain: str
    main_task: str
    task_description: Optional[str] = ""
    start_date: str
    duration_weeks: int = 4
    end_date: str

class ExcelApproveRequest(BaseModel):
    approved_rows: List[ExcelApproveRow]
    generate_roadmaps_automatically: bool = True

