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
    
    def query(self, query: str, user_context: Dict[str, Any] = None, system_context: str = "", chat_history: List[Dict[str, str]] = None, max_results: int = 5, stream: bool = False) -> Dict[str, Any]:
        start_time = time.time()

        try:
            context_sections = self.vector_service.get_context_sections(query, k=max_results)
            prompt = self._build_prompt(
                retrieved_docs=context_sections["retrieved_docs"],
                system_context=system_context,
                user_context=user_context,
                chat_history=chat_history,
                question=query,
            )

            if stream:
                response_generator = self.llm_service.generate_response(prompt, stream=True)
                response = response_generator
            else:
                response = self.llm_service.generate_response(prompt)

            return {
                "response": response,
                "sources": context_sections["sources"],
                "num_sources": len(context_sections["sources"]),
                "processing_time": time.time() - start_time
            }
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            raise RAGException(f"Query processing failed: {e}")
    
    def _build_prompt(self, retrieved_docs: str, system_context: str, user_context: Dict[str, Any], chat_history: List[Dict[str, str]], question: str) -> str:
        sections = [
            f"System: {system_context}" if system_context else "",
            f"User Profile: {user_context}" if user_context else "",
            "Chat History:\n" + "\n".join(f"{m['type'].capitalize()}: {m['content']}" for m in chat_history) if chat_history else "",
            f"Documents:\n{retrieved_docs}" if retrieved_docs else "",
            f"Question: {question}",
            "Answer:"
        ]
        return "\n\n".join(s for s in sections if s)
    
    def _build_context(self, documents: List) -> str:
        return "\n\n".join([doc.page_content for doc in documents])
    
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