"""
Unified entry point for the Civic Nexus RAG system
"""
import sys
import argparse
import subprocess
import logging
from pathlib import Path

# Import your services
from services.vector_store import VectorStoreService
from services.llm_service import LLMService  # Adjust import name as needed
from services.rag_service import RAGService    # Adjust import name as needed
from config import Config
from exceptions import VectorStoreException, DocumentProcessingException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServiceManager:
    """Manages initialization and startup of all services"""
    
    def __init__(self):
        self.config = Config()
        self.vector_service = None
        self.llm_service = None
        self.rag_service = None
        self.services_initialized = False
    
    def initialize_services(self):
        """Initialize all core services"""
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
            self.rag_service = RAGService()
            logger.info("✅ RAG Service initialized")
            
            self.services_initialized = True
            logger.info("🎉 All services initialized successfully!")
            
            return True
            
        except (VectorStoreException, DocumentProcessingException) as e:
            logger.error(f"❌ Service initialization failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error during initialization: {e}")
            return False
    
    def check_services_health(self):
        """Check if all services are healthy"""
        health_status = {
            'vector_store': self.vector_service.is_ready() if self.vector_service else False,
            'llm_service': hasattr(self.llm_service, 'is_ready') and self.llm_service.is_ready() if self.llm_service else True,  # Assume ready if no health check
            'rag_service': self.rag_service is not None
        }
        
        all_healthy = all(health_status.values())
        
        logger.info("🏥 Service Health Check:")
        for service, status in health_status.items():
            status_icon = "✅" if status else "❌"
            logger.info(f"  {status_icon} {service}: {'Ready' if status else 'Not Ready'}")
        
        return all_healthy
    
    def ingest_documents(self):
        """Ingest all documents if vector service is available"""
        if not self.vector_service:
            logger.warning("⚠️ Vector service not initialized, skipping document ingestion")
            return 0
        
        try:
            logger.info("📄 Checking for new documents to ingest...")
            count = self.vector_service.ingest_all_documents()
            if count > 0:
                logger.info(f"✅ Ingested {count} new documents")
            else:
                logger.info("ℹ️ No new documents to ingest")
            return count
        except Exception as e:
            logger.error(f"❌ Document ingestion failed: {e}")
            return 0
    
    def get_services(self):
        """Return initialized services"""
        return {
            'vector_service': self.vector_service,
            'llm_service': self.llm_service,
            'rag_service': self.rag_service
        }

def start_api():
    """Start the API server with initialized services"""
    logger.info("🚀 Starting API server...")
    
    # The FastAPI app will handle service initialization via lifespan events
    # Start the API server
    try:
        subprocess.run([sys.executable, "app.py"])
    except KeyboardInterrupt:
        logger.info("🛑 API server stopped by user")
    except Exception as e:
        logger.error(f"❌ API server error: {e}")

def start_cli():
    """Start the CLI interface with initialized services"""
    logger.info("🚀 Starting CLI interface...")
    
    # Initialize services
    service_manager = ServiceManager()
    if not service_manager.initialize_services():
        logger.error("❌ Failed to initialize services. Exiting.")
        sys.exit(1)
    
    # Check service health
    if not service_manager.check_services_health():
        logger.warning("⚠️ Some services are not healthy, but continuing...")
    
    # Ingest documents
    service_manager.ingest_documents()
    
    # Start the CLI
    try:
        subprocess.run([sys.executable, "cli.py"])
    except KeyboardInterrupt:
        logger.info("🛑 CLI stopped by user")
    except Exception as e:
        logger.error(f"❌ CLI error: {e}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Civic Nexus RAG System")
    parser.add_argument(
        "mode",
        choices=["api", "cli"],
        help="Run mode: 'api' for web server, 'cli' for command line"
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Skip document ingestion on startup"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("🌟 Civic Nexus RAG System Starting...")
    
    if args.mode == "api":
        start_api()
    elif args.mode == "cli":
        start_cli()

def quick_start():
    """Quickly start the backend in API mode with minimal setup"""
    logger.info("🚀 Quick Start: Initializing and starting the backend in API mode...")
    
    # Initialize Service Manager
    service_manager = ServiceManager()
    if not service_manager.initialize_services():
        logger.error("❌ Failed to initialize services. Exiting.")
        sys.exit(1)

    # Start API Server
    start_api()

if __name__ == "__main__":
    quick_start()

if __name__ == "__main__":
    main()
