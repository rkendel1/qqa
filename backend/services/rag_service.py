import time
import logging
from typing import Dict, Any, List, Optional, Union, Protocol
from tenacity import retry, stop_after_attempt, wait_exponential
from prometheus_client import Counter, Histogram
from opentelemetry import trace
from fastapi.responses import StreamingResponse

from services.vector_store import VectorStoreService
from services.llm_service import LLMService
from models import QueryResponse
from exceptions import RAGException
from config import settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Metrics
rag_queries_total = Counter('rag_queries_total', 'Total number of RAG queries')
rag_query_duration = Histogram('rag_query_duration_seconds', 'RAG query duration in seconds')
rag_errors_total = Counter('rag_errors_total', 'Total number of RAG errors')

class VectorStoreProtocol(Protocol):
    """Protocol defining required vector store methods"""
    def is_ready(self) -> bool: ...
    def get_ingested_files(self) -> List[str]: ...
    def ingest_all_documents(self) -> int: ...
    def get_context_sections(self, query: str, k: int) -> Dict[str, Any]: ...

class RAGService:
    """Main RAG service that orchestrates document retrieval and response generation"""
    def __init__(self, vector_service: VectorStoreService, llm_service: LLMService):
        self.vector_service = vector_service
        self.llm_service = llm_service
        self.vector_store: VectorStoreProtocol = self.vector_service.get_vector_store()

    def vector_store_is_ready(self) -> bool:
        """Check if vector store is ready by attempting a lightweight operation."""
        try:
            # Chroma Python client typically exposes 'collections()' method
            # Adapt this based on your actual vector_store API
            collections = None
            if hasattr(self.vector_store, "collections"):
                if callable(self.vector_store.collections):
                    collections = self.vector_store.collections()
                else:
                    collections = self.vector_store.collections
            if collections is not None:
                return True
            return False
        except Exception as e:
            logger.warning(f"Vector store readiness check failed: {e}")
            return False

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def query(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None,
        system_context: str = "",
        chat_history: Optional[List[Dict[str, str]]] = None,
        max_results: int = 5,
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process a query with retries and monitoring"""
        start_time = time.time()
        rag_queries_total.inc()

        try:
            with tracer.start_as_current_span("rag_query") as span:
                span.set_attribute("query", query)
                span.set_attribute("max_results", max_results)
                span.set_attribute("stream", stream)
                
                with rag_query_duration.time():
                    context_sections = self.vector_service.get_context_sections(query, k=max_results)
                    prompt = self._build_prompt(
                        retrieved_docs=context_sections["retrieved_docs"],
                        system_context=system_context,
                        user_context=user_context or {},
                        chat_history=chat_history or [],
                        question=query,
                    )

                    if stream:
                        response_generator = self.llm_service.generate_response(
                            prompt,
                            stream=True,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                        response = response_generator
                    else:
                        response = self.llm_service.generate_response(
                            prompt,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )

                    return {
                        "response": response,
                        "sources": context_sections["sources"],
                        "num_sources": len(context_sections["sources"]),
                        "processing_time": time.time() - start_time
                    }
        except Exception as e:
            rag_errors_total.inc()
            logger.error(f"RAG query failed: {e}")
            raise RAGException(f"Query processing failed: {e}")

 
    
    def _build_prompt(
        self,
        retrieved_docs: str,
        system_context: str,
        user_context: Dict[str, Any],
        chat_history: List[Dict[str, str]],
        question: str
    ) -> str:
        try:
            with tracer.start_as_current_span("build_prompt") as span:
                sections = [
                    ("System", system_context) if system_context else None,
                    ("User Profile", str(user_context)) if user_context else None,
                    ("Chat History", "\n".join(f"{m['type'].capitalize()}: {m['content']}" for m in chat_history)) if chat_history else None,
                    ("Documents", retrieved_docs) if retrieved_docs else None,
                    ("Question", question),
                    ("Answer", "")
                ]
                formatted_sections = [
                    f"{section[0]}: {section[1]}" if section[0] != "Answer" else section[1]
                    for section in sections if section is not None
                ]
                prompt = "\n\n".join(formatted_sections)
                span.set_attribute("prompt_length", len(prompt))
                return prompt
        except Exception as e:
            logger.error(f"Failed to build prompt: {e}")
            raise RAGException(f"Prompt building failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get service status with detailed information"""
        try:
            vector_store_stats = self.vector_service.get_stats()
            llm_info = self.llm_service.get_model_info()

            vector_ready = self.vector_store_is_ready()

            # Try to get ingested files count, fallback to zero if not available
            try:
                ingested_files = []
                if hasattr(self.vector_store, "get_ingested_files") and callable(self.vector_store.get_ingested_files):
                    ingested_files = self.vector_store.get_ingested_files()
                elif hasattr(self.vector_store, "collections") and callable(self.vector_store.collections):
                    # Optionally count documents per collection if you track this
                    # Example fallback: count number of collections as ingested docs count
                    collections = self.vector_store.collections()
                    ingested_files = collections if collections else []
                else:
                    ingested_files = []
            except Exception as e:
                logger.warning(f"Failed to fetch ingested files list: {e}")
                ingested_files = []

            return {
                "status": "healthy" if vector_ready and self.llm_service.is_available() else "unhealthy",
                "documents_ingested": len(ingested_files),
                "vector_store_ready": vector_ready,
                "ollama_available": self.llm_service.is_available(),
                "vector_store_stats": vector_store_stats,
                "llm_info": llm_info
            }
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def ingest_documents(self) -> int:
        try:
            with tracer.start_as_current_span("ingest_documents"):
                return self.vector_store.ingest_all_documents()
        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            raise RAGException(f"Document ingestion failed: {e}")
    
    def clear_cache(self):
        self.vector_service.clear_cache()