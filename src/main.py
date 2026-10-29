from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.agent import router as agent_router
from src.api.tickets import router
from src.copilot.llm import get_llm_config, is_provider_configured
from src.database.db import Base, engine
from src.models.ticket import Ticket


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="IT Ops Copilot",
    description="IT incident and ticket management API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
app.include_router(agent_router)


@app.get("/")
def home():
    config = get_llm_config()
    return {
        "message": "IT Ops Copilot API is running",
        "docs": "/docs",
        "copilot": {
            "agent_ready": True,
            "llm_provider": config.provider,
            "llm_configured": is_provider_configured(config),
        },
    }
