import sys
import logging
from pathlib import Path

from services.rag_service import RAGService
from exceptions import RAGException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CLI:
    def __init__(self):
        self.rag_service = RAGService()
    
    def run(self):
        """Run the CLI interface"""
        print("🤖 Civic Nexus RAG System")
        print("=" * 50)
        
        # Check system status
        status = self.rag_service.get_status()
        if status["status"] != "healthy":
            print("❌ System not ready:")
            print(f"   Vector Store: {'✅' if status['vector_store_ready'] else '❌'}")
            print(f"   Ollama: {'✅' if status['ollama_available'] else '❌'}")
            return
        
        print(f"✅ System ready - {status['documents_ingested']} documents loaded")
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
                
                # Process query
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
            except RAGException as e:
                print(f"❌ Error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                print(f"❌ Unexpected error occurred")

if __name__ == "__main__":
    cli = CLI()
    cli.run()