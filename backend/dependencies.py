from services.vector_store import VectorStoreService
from services.llm_service import LLMService
from services.rag_service import RAGService

# Instantiate services
vector_service = VectorStoreService()
llm_service = LLMService()
rag_service = RAGService(vector_service=vector_service, llm_service=llm_service)

# Populate app_services for dependency injection or app-wide access
app_services = {
    'vector_service': vector_service,
    'llm_service': llm_service,
    'rag_service': rag_service,
}

def get_vector_service() -> VectorStoreService:
    if 'vector_service' not in app_services:
        raise Exception("Vector service not initialized")
    return app_services['vector_service']

def get_llm_service() -> LLMService:
    if 'llm_service' not in app_services:
        raise Exception("LLM service not initialized")
    return app_services['llm_service']

def get_rag_service() -> RAGService:
    if 'rag_service' not in app_services:
        raise Exception("RAG service not initialized")
    return app_services['rag_service']