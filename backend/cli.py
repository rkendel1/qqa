import sys
import logging
from typing import Optional
from services.rag_service import RAGService
from exceptions import RAGException
from services.vector_store import VectorStoreService
from services.llm_service import LLMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CLI:
    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service
        self.commands = {
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
            "q": self._cmd_quit,
            "ingest": self._cmd_ingest,
            "help": self._cmd_help,
            "?": self._cmd_help,
        }
        self.running = True
    
    def run(self):
        """Run the CLI interface"""
        print("🤖 Civic Nexus RAG System")
        print("=" * 50)
        
        # Check system status
        status = self.rag_service.get_status()
        if status.get("status") != "healthy":
            print("❌ System not ready:")
            print(f"   Vector Store: {'✅' if status.get('vector_store_ready') else '❌'}")
            print(f"   Ollama: {'✅' if status.get('ollama_available') else '❌'}")
            return
        
        print(f"✅ System ready - {status.get('documents_ingested', 0)} documents loaded")
        print("\nCommands: 'help' for list, 'quit' to exit, 'ingest' to process documents")
        print("=" * 50)
        
        while self.running:
            try:
                query = input("\n🤔 Your question: ").strip()
                if not query:
                    continue
                
                # Check if the input is a command
                cmd_func = self.commands.get(query.lower())
                if cmd_func:
                    cmd_func()
                    continue
                
                # Otherwise treat input as a natural language query
                self._handle_query(query)
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except RAGException as e:
                print(f"❌ Error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                print(f"❌ Unexpected error occurred. Check logs.")
    
    def _handle_query(self, query: str) -> None:
        """Process a user query and print the results"""
        print("Processing query, please wait...")
        result = self.rag_service.query(query)
        print("\n" + "-" * 50)
        print(f"🧠 Response:\n{result.get('response', '[No response]')}")
        sources = result.get('sources', [])
        print(f"\n📋 Sources: {', '.join(sources) if sources else 'None'}")
        print(f"Documents used: {result.get('num_sources', 0)}")
        print(f"Processing time: {result.get('processing_time', 0):.2f}s")
        print("-" * 50)
    
    def _cmd_quit(self) -> None:
        """Exit the CLI"""
        print("👋 Goodbye!")
        self.running = False
    
    def _cmd_ingest(self) -> None:
        """Run document ingestion process"""
        print("Starting document ingestion...")
        count = self.rag_service.ingest_documents()
        print(f"✅ Processed {count} document{'s' if count != 1 else ''}")
    
    def _cmd_help(self) -> None:
        """Show available commands"""
        print("\nAvailable commands:")
        print("  ingest  - Process all documents for ingestion")
        print("  quit    - Exit the program")
        print("  exit    - Exit the program")
        print("  q       - Exit the program")
        print("  help/?  - Show this help message")

if __name__ == "__main__":
    vector_service = VectorStoreService()
    llm_service = LLMService()
    rag_service = RAGService(vector_service=vector_service, llm_service=llm_service)
    cli = CLI(rag_service=rag_service)
    cli.run()