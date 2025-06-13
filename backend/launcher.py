import sys
import argparse
import logging
import uvicorn

from services.vector_store import VectorStoreService
from services.llm_service import LLMService
from services.rag_service import RAGService

from api.auth_routes import router as users_router
from api.user_routes import router as rag_router

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
        # Add any startup logic if needed
        return True

class CLI:
    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service

    def run(self):
        print("🤖 Civic Nexus RAG System")
        print("=" * 50)

        status = self.rag_service.get_status()
        if status.get("status") != "healthy":
            print("❌ System not ready:")
            print(f"   Vector Store: {'✅' if status.get('vector_store_ready') else '❌'}")
            print(f"   Ollama: {'✅' if status.get('ollama_available') else '❌'}")
            return

        print(f"✅ System ready - {status.get('documents_ingested', 0)} documents loaded")
        print("\nCommands: 'quit' to exit, 'ingest' to process documents")
        print("=" * 50)

        while True:
            try:
                query = input("\n🤔 Your question: ").strip()
                if query.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                if query.lower() == 'ingest':
                    count = self.rag_service.ingest_documents()
                    print(f"✅ Processed {count} documents")
                    continue
                if not query:
                    continue
                result = self.rag_service.query(query)
                print("\n" + "-" * 50)
                print(f"🧠 Response:\n{result['response']}")
                print(f"\n📋 Sources: {', '.join(result['sources'])}")
                print(f"Documents used: {result['num_sources']}")
                print(f"Processing time: {result['processing_time']:.2f}s")
                print("-" * 50)
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                print(f"❌ Unexpected error occurred")

def start_api(service_manager: ServiceManager):
    from app import app

    app.state.rag_service = service_manager.rag_service
    app.state.vector_service = service_manager.vector_service
    app.state.llm_service = service_manager.llm_service

    app.include_router(users_router, prefix="/users", tags=["users"])
    app.include_router(rag_router, prefix="/api", tags=["RAG API"])

    logger.info("🚀 Starting API server...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

def main():
    parser = argparse.ArgumentParser(description="Unified Civic Nexus Launcher")
    parser.add_argument("mode", choices=["api", "cli"], help="Run mode: 'api' or 'cli'")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    service_manager = ServiceManager()
    if not service_manager.initialize_services():
        logger.error("❌ Failed to initialize services. Exiting.")
        sys.exit(1)

    if args.mode == "api":
        start_api(service_manager)
    else:
        cli = CLI(rag_service=service_manager.rag_service)
        cli.run()

if __name__ == "__main__":
    main()