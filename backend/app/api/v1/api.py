from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.excel import router as excel_router
from app.api.v1.admin import router as admin_router
from app.api.v1.interns import router as intern_router
from app.api.v1.roadmaps import router as roadmap_router
from app.api.v1.ollama import router as ollama_router
from app.api.v1.email import router as email_router
from app.api.v1.google import router as google_router
from app.api.v1.automation import router as automation_router
from app.api.v1.certificates import router as certificates_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(excel_router, prefix="/excel", tags=["Excel Operations"])
api_router.include_router(admin_router, prefix="/admin", tags=["Admin Portal"])
api_router.include_router(intern_router, prefix="/intern", tags=["Intern Portal"])
api_router.include_router(roadmap_router, prefix="/roadmaps", tags=["Roadmaps"])
api_router.include_router(ollama_router, prefix="/ollama", tags=["Ollama AI"])
api_router.include_router(email_router, prefix="/email", tags=["Email Automation"])
api_router.include_router(google_router, prefix="/google", tags=["Google Integration"])
api_router.include_router(automation_router, prefix="/automation", tags=["Lifecycle Automation"])
api_router.include_router(certificates_router, prefix="/certificates", tags=["Certificates"])

