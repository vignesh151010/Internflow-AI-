import os
import sys
from pathlib import Path
import uvicorn

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    print("=" * 60)
    print(" INTERNFLOW AI - Starting Local Platform")
    print(" Primary URL : http://localhost:8000")
    print(" Admin Portal: http://localhost:8000/admin")
    print(" Intern Portal: http://localhost:8000/intern")
    print(" API Docs    : http://localhost:8000/docs")
    print(" Default Admin: admin@internflow.ai / Admin@123")
    print("=" * 60)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

