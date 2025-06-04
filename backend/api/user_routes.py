from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from services.vector_store import VectorStoreService
from services.rag_service import RAGService
from dependencies import get_vector_service, get_rag_service
from users.models import User
from users.auth import hash_password, verify_password
from users.schemas import UserCreate, UserRead, UserLogin, Token

router = APIRouter()

# Request/Response models
class ChatMessage(BaseModel):
    type: str
    content: str

class QueryRequest(BaseModel):
    question: str
    k: int = 5
    user_context: Optional[Dict[str, Any]] = None
    system_context: Optional[str] = None
    chat_history: Optional[List[ChatMessage]] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float = None

class DocumentInfo(BaseModel):
    filename: str
    chunks: int = None

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Civic Nexus RAG API is running"}

@router.get("/documents", response_model=List[str])
async def get_documents(
    vector_service: VectorStoreService = Depends(get_vector_service)
):
    """Get list of ingested documents"""
    try:
        documents = vector_service.get_ingested_files()
        return documents
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get documents: {str(e)}")

@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    """Query documents using RAG"""
    try:
        # Generate answer using RAG service (includes retrieval)
        response_data = rag_service.query(
            query=request.question,
            user_context=request.user_context,
            system_context=request.system_context,
            chat_history=[msg.dict() for msg in request.chat_history] if request.chat_history else None,
            max_results=request.k
        )
        answer = response_data["response"]
        doc_sources = response_data.get("sources", [])

        # Format sources as list of dicts with content and metadata
        sources = []
        for src in doc_sources:
            if isinstance(src, dict):
                content = src.get("content", "")
                metadata = src.get("metadata", {})
                sources.append({"content": content, "metadata": metadata})
            else:
                sources.append({"content": src, "metadata": {"source": src}})

        return QueryResponse(
            answer=answer,
            sources=sources
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@router.post("/documents/search")
async def search_documents(
    request: QueryRequest,
    vector_service: VectorStoreService = Depends(get_vector_service)
):
    """Search documents without generating an answer"""
    try:
        documents = vector_service.similarity_search(request.question, k=request.k)
        
        results = []
        for doc in documents:
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "similarity_score": getattr(doc, 'similarity_score', None)
            })
        
        return {"results": results, "count": len(results)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/documents/ingest")
async def ingest_documents(
    vector_service: VectorStoreService = Depends(get_vector_service)
):
    """Manually trigger document ingestion"""
    try:
        count = vector_service.ingest_all_documents()
        return {"message": f"Successfully ingested {count} documents", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    
@router.get("/debug/vectorstore")
def check_vectorstore(vector_service: VectorStoreService = Depends(get_vector_service)):
    return {
        "is_ready": vector_service.is_ready(),
        "ingested_files": vector_service.get_ingested_files()
    }