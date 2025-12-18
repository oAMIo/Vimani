import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from backend/.env before anything else.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

from fastapi import FastAPI

logger = logging.getLogger(__name__)
logger.info("ENV_PATH resolved to %s (exists=%s)", ENV_PATH, ENV_PATH.exists())
logger.info("OPENAI_API_KEY loaded? %s", bool(os.getenv("OPENAI_API_KEY")))


def create_app() -> FastAPI:
    """Application factory to keep imports lightweight."""
    from app.api.ws import router as ws_router
    
    app = FastAPI(title="Vimani Orchestrator POC")
    app.include_router(ws_router)

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    return app


app = create_app()

