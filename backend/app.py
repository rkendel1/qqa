# app.py

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import Config
from services.vector_store import VectorStoreService
from services.llm_service import LLMService
from services.rag_service import RAGService
from dependencies import app_services  # Import shared service registry
from api.routes import router as rag_router
from api.auth_routes import router as auth_router
from users.models import User
from users.auth import hash_password, verify_password
from users.schemas import UserCreate, UserRead, UserLogin, Token


# Logging config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServiceManager:
    def __init__(self):
        self.vector_service = VectorStoreService()
        self.llm_service = LLMService()
        self.rag_service = RAGService(
            vector_service=self.vector_service,
            llm_service=self.llm_service
        )

    def initialize_services(self):
        # Optional initialization logic
        return True
    
    def get_services(self):
        return {
            "vector_service": self.vector_service,
            "llm_service": self.llm_service,
            "rag_service": self.rag_service
        }

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Civic Nexus RAG API...")

    service_manager = ServiceManager()
    if service_manager.initialize_services():
        app_services.update(service_manager.get_services())
        logger.info("✅ All services ready!")
    else:
        logger.error("❌ Service initialization failed!")
        raise Exception("Failed to initialize services")

    yield
    logger.info("🛑 Shutting down Civic Nexus RAG API...")

def create_app() -> FastAPI:
    app = FastAPI(
        title="Civic Nexus RAG API",
        description="A RAG system for civic document Q&A",
        version="1.0.0",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=Config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix="/auth")
    app.include_router(rag_router)
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    config = Config()
    uvicorn.run("app:app", host=config.API_HOST, port=config.API_PORT, reload=True)