"""Agent chat endpoints for the Streamlit copilot drawer."""
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.copilot import llm
from src.copilot.agent import answer_question

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])


class HistoryMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$", max_length=16)
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: Optional[List[HistoryMessage]] = None


class ChatResponse(BaseModel):
    reply: str
    mode: str  # "ai" | "fallback"
    sources: List[str] = []


@router.post("/chat", response_model=ChatResponse)
def copilot_chat(payload: ChatRequest):
    result = answer_question(payload.question, payload.history)
    return result


@router.get("/health")
def copilot_health():
    config = llm.get_llm_config()
    return {
        "agent_ready": True,
        "llm_provider": config.provider,
        "llm_model": config.model or None,
        "llm_configured": llm.is_provider_configured(config),
    }
