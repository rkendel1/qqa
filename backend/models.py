from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    """Request model for RAG queries"""
    query: str = Field(..., description="The query to process")
    user_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User profile and preferences"
    )
    system_context: Optional[str] = Field(
        default="",
        description="System-level context/instructions"
    )
    chat_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Previous conversation messages"
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of documents to retrieve"
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response"
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Temperature for response generation"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        le=4096,
        description="Maximum number of tokens to generate"
    )

class QueryResponse(BaseModel):
    """Response model for RAG queries"""
    response: str | List[str] = Field(..., description="The generated response")
    sources: List[Dict[str, Any]] = Field(..., description="Source documents used")
    num_sources: int = Field(..., description="Number of sources used")
    processing_time: float = Field(..., description="Time taken to process the query")

class DocumentMetadata(BaseModel):
    """Model for document metadata"""
    source: str = Field(..., description="Source filename")
    file_path: str = Field(..., description="Full file path")
    file_size: int = Field(..., description="File size in bytes")
    ingested_at: str = Field(..., description="ISO timestamp of ingestion")

class ServiceStatus(BaseModel):
    """Model for service status"""
    status: str = Field(..., description="Service status (healthy/unhealthy)")
    documents_ingested: int = Field(..., description="Number of ingested documents")
    vector_store_ready: bool = Field(..., description="Vector store status")
    ollama_available: bool = Field(..., description="Ollama service status")
    vector_store_stats: Dict[str, Any] = Field(..., description="Vector store statistics")
    llm_info: Dict[str, Any] = Field(..., description="LLM service information")
    
