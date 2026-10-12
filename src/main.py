from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.tickets import router
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


@app.get("/")
def home():
    return {
        "message": "IT Ops Copilot API is running",
        "docs": "/docs",
    }
