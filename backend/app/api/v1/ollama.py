from typing import Any
from fastapi import APIRouter
from app.services.ollama_service import ollama_service

router = APIRouter()

@router.get("/status")
def get_ollama_status() -> Any:
    """Checks whether local Ollama daemon is active and returns pulled models."""
    return ollama_service.check_connection()

@router.post("/test")
def test_ollama_prompt(data: dict) -> Any:
    """Tests a prompt directly against Ollama local instance."""
    prompt = data.get("prompt", "Introduce yourself as the InternFlow AI mentor.")
    model = data.get("model")
    
    conn = ollama_service.check_connection()
    if conn["connected"]:
        reply = ollama_service.generate_completion(prompt, model=model)
        if reply:
            return {"success": True, "source": "Ollama LLM", "response": reply}
            
    return {
        "success": True,
        "source": "Local AI Curriculum Engine (Fallback)",
        "response": f"Ollama is currently unreachable at {conn['base_url']}. The InternFlow AI autonomous engine is handling all curriculum and roadmap generation with zero interruption."
    }

