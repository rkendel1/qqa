import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from llm_handler import LocalRAGPipeline
from local_rag import LocalRAGSystem
from file_watcher import start_watching

app = FastAPI()

# RAG Pipeline shared by API and CLI
rag_pipeline = LocalRAGPipeline(
    documents_path="/Users/randy/Desktop/Dev/civic-nexus-chat/backend/documents",
    ollama_model="mistral"
)

# CORS settings for the UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False



@app.post("/rag-query")
async def rag_query(request: QueryRequest):
    try:
        result = rag_pipeline.query(query=request.prompt, use_streaming=request.stream)

        # Ensure this returns what you expect
        return {
            "response": result.get("response", "No response received"),
            "sources": result.get("sources", []),
            "num_sources": result.get("num_sources", 0)
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"response": f"Error during RAG processing: {str(e)}"}
        )

# Optional streaming endpoint (UI use if needed)
@app.post("/rag-query-stream")
async def rag_query_stream(request: Request):
    body = await request.json()
    query = body.get("query", "")

    try:
        result = rag_pipeline.query(query, use_streaming=True)  # <-- use_streaming=True to get generator
        gen = result["response"]  # This should be a generator now
        sources = result["sources"]
        num_sources = result["num_sources"]

        def event_generator():
            try:
                for chunk in gen:  # gen yields strings (chunks)
                    yield f"data: {chunk}\n\n"
                yield f"data: [[DONE]]\n\n"
            except Exception as e:
                yield f"data: Error: {str(e)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        return JSONResponse(status_code=500, content={"response": f"Streaming error: {str(e)}"})

# CLI-only: Print banner and check Ollama
def print_banner():
    print("=" * 60)
    print("🤖 LOCAL RAG SYSTEM WITH OLLAMA MISTRAL")
    print("=" * 60)
    print("• Local document processing and vector storage")
    print("• HuggingFace embeddings")
    print("• Ollama with Mistral for response generation")
    print("=" * 60)

def check_ollama_setup():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [model["name"] for model in models]
            if any("mistral" in name for name in model_names):
                print("✅ Ollama is running with Mistral model")
                return True
            else:
                print("❌ Mistral model not found — run: `ollama pull mistral`")
                return False
        else:
            print("❌ Ollama server not responding")
            return False
    except Exception as e:
        print(f"❌ Error connecting to Ollama: {e}")
        print("➡️ Make sure Ollama is installed and running")
        return False

# CLI main loop — using same pipeline instance
def main():
    print_banner()

    if not check_ollama_setup():
        return

    print("\n📖 USAGE INSTRUCTIONS:")
    print("• Add documents to ./documents/ folder")
    print("• Type your questions below")
    print("• Commands: 'quit' to exit, 'add' to add documents")
    print("=" * 60)

    while True:
        try:
            question = input("\n🤔 Your question (or 'quit'/'add'): ").strip()

            if question.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break

            if question.lower() == 'add':
                file_path = input("📄 Enter file path to add: ").strip()
                if os.path.isfile(file_path):
                    rag_pipeline.add_document(file_path)
                    print("✅ Document added.")
                else:
                    print("❌ File not found.")
                continue

            if not question:
                continue

            result = rag_pipeline.query(question, use_streaming=False)

            print("\n" + "-" * 50)
            print(f"\n🧠 Assistant:\n{result.get('response', 'No response')}")
            print(f"\n📋 Summary:")
            print(f"Sources: {', '.join(result.get('sources', []))}")
            print(f"Documents used: {result.get('num_sources', 0)}")
            print("-" * 50)

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

# Start backend + watcher + CLI interface
if __name__ == "__main__":
    rag = LocalRAGSystem()
    rag.ingest_documents()
    start_watching(rag)
    main()