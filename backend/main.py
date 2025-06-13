# main.py
import os
import sys
import argparse
import logging
import uvicorn
from pathlib import Path

# Setup paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.vector_store import VectorStoreService
from services.llm_service import LLMService
from services.rag_service import RAGService
from config import settings
from exceptions import RAGException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServiceManager:
    def __init__(self):
        self.vector_service = None
        self.llm_service = None
        self.rag_service = None
        self.initialized = False
    
    def initialize_services(self):
        """Initialize all services with proper error handling"""
        if self.initialized:
            return True
            
        try:
            logger.info("🔧 Initializing services...")
            
            # Initialize Vector Store Service
            logger.info("📚 Initializing Vector Store Service...")
            self.vector_service = VectorStoreService()
            logger.info(f"✅ Vector Store initialized with {len(self.vector_service.get_ingested_files())} files")
            
            # Initialize LLM Service
            logger.info("🤖 Initializing LLM Service...")
            self.llm_service = LLMService()
            logger.info("✅ LLM Service initialized")
            
            # Initialize RAG Service
            logger.info("🔍 Initializing RAG Service...")
            self.rag_service = RAGService(
                vector_service=self.vector_service,
                llm_service=self.llm_service
            )
            logger.info("✅ RAG Service initialized")
            
            self.initialized = True
            logger.info("🎉 All services initialized successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Service initialization failed: {e}")
            return False
    
    def check_health(self):
        """Check service health"""
        if not self.initialized:
            return False
            
        try:
            status = self.rag_service.get_status()
            return status.get("status") == "healthy"
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

# Global service manager
service_manager = ServiceManager()

def start_api():
    """Start the FastAPI server"""
    logger.info("🚀 Starting API server...")
    
    # Initialize services
    if not service_manager.initialize_services():
        logger.error("❌ Failed to initialize services. Exiting.")
        sys.exit(1)
    
    # Check health
    if not service_manager.check_health():
        logger.warning("⚠️ Some services are not healthy, but continuing...")
    
    # Import and configure the FastAPI app
    from app import app
    
    # Set services in app state BEFORE starting uvicorn
    app.state.vector_service = service_manager.vector_service
    app.state.llm_service = service_manager.llm_service
    app.state.rag_service = service_manager.rag_service
    
    # Start server
    uvicorn.run(
        "app:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False  # Set to False when using external service initialization
    )

def start_cli():
    """Start the CLI interface"""
    logger.info("🚀 Starting CLI interface...")
    
    # Initialize services
    if not service_manager.initialize_services():
        logger.error("❌ Failed to initialize services. Exiting.")
        sys.exit(1)
    
    # Start CLI
    from cli import CLI
    cli = CLI(rag_service=service_manager.rag_service)
    cli.run()

def main():
    parser = argparse.ArgumentParser(description="Civic Nexus RAG System")
    parser.add_argument("mode", choices=["api", "cli"], help="Run mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("🌟 Civic Nexus RAG System Starting...")
    
    if args.mode == "api":
        start_api()
    elif args.mode == "cli":
        start_cli()

if __name__ == "__main__":
    main()