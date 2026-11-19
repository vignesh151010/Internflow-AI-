import sys
import asyncio
from pathlib import Path

# Ensure backend directory is in sys.path for direct executions
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal, auto_migrate_schema
from app.models import *  # Import all 15 models to register metadata
from app.api.v1.api import api_router
from app.services.auth_service import ensure_initial_admin
from app.services.excel_service import create_sample_excel_template
from app.services.automation_service import automation_service

# Frontend directory
FRONTEND_DIR = settings.BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize SQLite tables and run schema auto-migrations
    Base.metadata.create_all(bind=engine)
    auto_migrate_schema()
    
    # 2. Seed default Administrator
    db = SessionLocal()
    try:
        ensure_initial_admin(db)
        # 3. Recover missed automation jobs after system restart
        automation_service.recover_missed_jobs(db)
    finally:
        db.close()
        
    # 4. Ensure sample Excel template is generated
    sample_template_path = settings.DATA_DIR / "sample_template" / "internflow_sample_import.xlsx"
    create_sample_excel_template(sample_template_path)
    
    # 5. Background automated lifecycle processor
    stop_event = asyncio.Event()
    async def automation_loop():
        while not stop_event.is_set():
            try:
                loop_db = SessionLocal()
                try:
                    automation_service.run_pending_jobs(loop_db)
                finally:
                    loop_db.close()
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                pass

    worker_task = asyncio.create_task(automation_loop())

    yield

    stop_event.set()
    worker_task.cancel()
    try:
        await worker_task
    except (asyncio.CancelledError, Exception):
        pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="AI-Powered Intelligent Internship Management & Automation Platform",
    lifespan=lifespan
)

# CORS configuration for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount Static Files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Serve Frontend Pages
@app.get("/", include_in_schema=False)
def serve_home():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/admin", include_in_schema=False)
@app.get("/admin/", include_in_schema=False)
def serve_admin():
    return FileResponse(FRONTEND_DIR / "admin" / "index.html")

@app.get("/intern", include_in_schema=False)
@app.get("/intern/", include_in_schema=False)
def serve_intern():
    return FileResponse(FRONTEND_DIR / "intern" / "index.html")

@app.get("/verify", include_in_schema=False)
@app.get("/verify/{certificate_number}", include_in_schema=False)
def serve_verify(certificate_number: str = ""):
    return FileResponse(FRONTEND_DIR / "verify.html")

