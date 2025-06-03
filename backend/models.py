from pydantic import BaseModel
from typing import List, Optional

class QueryRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5
    stream: Optional[bool] = False

class QueryResponse(BaseModel):
    response: str
    sources: List[str]
    num_sources: int
    processing_time: Optional[float] = None

class DocumentInfo(BaseModel):
    filename: str
    size: int
    ingested_at: str
    chunks: int

class SystemStatus(BaseModel):
    status: str
    documents_ingested: int
    vector_store_ready: bool
    ollama_available: bool
    
