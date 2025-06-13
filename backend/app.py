# app.py
import os, sys
print("cwd:", os.getcwd())
print("sys.path:", sys.path)
import logging
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Dict, Any, Optional
import uvicorn

from config import settings
from services.vector_store import VectorStoreService
from services.llm_service import LLMService
from services.rag_service import RAGService
from dependencies import app_services  # Import shared service registry
from models import QueryRequest, QueryResponse
from exceptions import RAGException
from monitoring import setup_monitoring, get_tracer

from api.auth_routes import router as auth_router
from api.user_routes import router as rag_router
from users.models import User
from users.auth import hash_password, verify_password
from users.schemas import UserCreate, UserRead, UserLogin, Token
from fastapi.responses import StreamingResponse




project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


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

# Initialize FastAPI app
app = FastAPI(title="RAG API")

# Setup rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down."}
    )

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup monitoring
setup_monitoring(app)

# Initialize ServiceManager and get shared services
service_manager = ServiceManager()
service_manager.initialize_services()

# vector_service = service_manager.vector_service
# llm_service = service_manager.llm_service
# rag_service = service_manager.rag_service

app.state.vector_service = service_manager.vector_service
app.state.llm_service = service_manager.llm_service
app.state.rag_service = service_manager.rag_service

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "RAG API is running"}

@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint"""
    rag_service = request.app.state.rag_service
    return rag_service.get_status()

@app.post("/query", response_model=QueryResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/minute")  # or hour, second, etc
async def query(
    request: Request,
    query_request: QueryRequest
) -> Dict[str, Any]:
    """Query endpoint with rate limiting"""
    rag_service = request.app.state.rag_service
    try:
        with get_tracer().start_as_current_span("query_endpoint") as span:
            span.set_attribute("query", query_request.query)
            span.set_attribute("stream", query_request.stream)
            
            response = rag_service.query(
                query=query_request.query,
                user_context=query_request.user_context,
                system_context=query_request.system_context or "",
                chat_history=query_request.chat_history,
                max_results=query_request.max_results,
                stream=query_request.stream,
                temperature=query_request.temperature,
                max_tokens=query_request.max_tokens
)
            
            return response
    except RAGException as e:
        logger.error(f"RAG error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



@router.post("/query/stream")
async def stream_query_documents(request: QueryRequest, rag_service: RAGService = Depends(get_rag_service)):
    response_generator = rag_service.query(
        query=request.question,
        user_context=request.user_context,
        system_context=request.system_context,
        chat_history=[msg.dict() for msg in request.chat_history] if request.chat_history else None,
        max_results=request.k,
        stream=True
    )  # This will return a generator from LLMService

    return StreamingResponse(response_generator, media_type="text/event-stream")



@app.post("/ingest")
async def ingest_documents(request: Request):
    """Ingest documents endpoint"""
    rag_service = request.app.state.rag_service
    try:
        with get_tracer().start_as_current_span("ingest_documents_endpoint"):
            count = rag_service.ingest_documents()
            return {"message": f"Successfully ingested {count} documents"}
    except RAGException as e:
        logger.error(f"Document ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/documents")
async def get_documents(request: Request):
    """Get ingested documents endpoint"""
    vector_service = request.app.state.vector_service
    try:
        with get_tracer().start_as_current_span("get_documents_endpoint"):
            files = vector_service.get_ingested_files()
            return {"documents": files}
    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/cache")
async def clear_cache(request: Request):
    """Clear cache endpoint"""
    rag_service = request.app.state.rag_service
    try:
        with get_tracer().start_as_current_span("clear_cache_endpoint"):
            rag_service.clear_cache()
            return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )