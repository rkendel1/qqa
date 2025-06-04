import os
from pathlib import Path

class Config:
    # Paths
    BASE_DIR = Path(__file__).parent
    DOCUMENTS_PATH = Path(__file__).parent / "documents"
    CHROMA_DB_PATH = Path(__file__).parent / "chroma_db"
    METADATA_FILE = BASE_DIR / "ingested_files.json"
    
    # Embedding model (using HuggingFaceEmbeddings)
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # or replace with your preferred model

    # RAG Settings
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 100
    SIMILARITY_K = 5

   
    CONTEXT_MAX_SIZE = 1024  # Max size for context in bytes or characters 

    # Ollama or other LLM backends (optional)
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # API Settings
    API_HOST = "127.0.0.1"
    API_PORT = 8000
    CORS_ORIGINS = [
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ]
