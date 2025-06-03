import time
import logging
from typing import Dict, Any, List

from services.vector_store import VectorStoreService
from services.llm_service import LLMService
from models import QueryResponse
from exceptions import RAGException

logger = logging.getLogger(__name__)

class RAGService:
    """Main RAG service that orchestrates document retrieval and response generation"""
    
    def __init__(self, vector_service: VectorStoreService, llm_service: LLMService):
        self.vector_service = vector_service
        self.llm_service = llm_service
        self.vector_store = self.vector_service.get_vector_store()
    
    def query(self, query: str, max_results: int = 5, stream: bool = False) -> Dict[str, Any]:
        start_time = time.time()
        
        try:
            documents = self.vector_store.similarity_search(query, k=max_results)
            
            if not documents:
                return {
                    "response": "No relevant documents found for your query.",
                    "sources": [],
                    "num_sources": 0,
                    "processing_time": time.time() - start_time
                }
            
            context = self._build_context(documents)
            prompt = self._build_prompt(context, query)
            
            if stream:
                response_generator = self.llm_service.generate_response(prompt, stream=True)
                return {
                    "response": response_generator,
                    "sources": self._extract_sources(documents),
                    "num_sources": len(set(doc.metadata.get("source", "unknown") for doc in documents)),
                    "processing_time": time.time() - start_time
                }
            else:
                response = self.llm_service.generate_response(prompt, stream=False)
                return {
                    "response": response,
                    "sources": self._extract_sources(documents),
                    "num_sources": len(set(doc.metadata.get("source", "unknown") for doc in documents)),
                    "processing_time": time.time() - start_time
                }
                
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            raise RAGException(f"Query processing failed: {e}")
    
    def _build_context(self, documents: List) -> str:
        return "\n\n".join([doc.page_content for doc in documents])
    
    def _build_prompt(self, context: str, query: str) -> str:
        return f"""You are a helpful assistant. Answer the question below using only the context provided.

Context:
{context}

Question: {query}

Answer:"""
    
    def _extract_sources(self, documents: List) -> List[str]:
        return list(set(doc.metadata.get("source", "unknown") for doc in documents))
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self.vector_store.is_ready() and self.llm_service.is_available() else "unhealthy",
            "documents_ingested": len(self.vector_store.get_ingested_files()),
            "vector_store_ready": self.vector_store.is_ready(),
            "ollama_available": self.llm_service.is_available()
        }
    
    def ingest_documents(self) -> int:
        return self.vector_store.ingest_all_documents()