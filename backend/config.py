import os
from pathlib import Path
from typing import List
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Paths
    BASE_DIR: Path = Path(__file__).parent
    DOCUMENTS_PATH: Path = Field(default=Path(__file__).parent / "documents")
    CHROMA_DB_PATH: Path = Field(default=Path(__file__).parent / "chroma_db")
    METADATA_FILE: Path = Field(default=Path(__file__).parent / "ingested_files.json")
    
    # Embedding model
    EMBEDDING_MODEL: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    
    # RAG Settings
    CHUNK_SIZE: int = Field(default=500, ge=100, le=2000)
    CHUNK_OVERLAP: int = Field(default=100, ge=0, le=500)
    SIMILARITY_K: int = Field(default=5, ge=1, le=20)
    
    # LLM Settings
    OLLAMA_MODEL: str = Field(default="mistral")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    
    # API Settings
    API_HOST: str = Field(default="127.0.0.1")
    API_PORT: int = Field(default=8000, ge=1024, le=65535)
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:8081", "http://127.0.0.1:8081"])
    
    # Cache Settings
    CACHE_SIZE: int = Field(default=1000, ge=100, le=10000)
    CACHE_TTL: int = Field(default=3600, ge=60, le=86400)
    
    # Retry Settings
    MAX_RETRIES: int = Field(default=3, ge=1, le=5)
    RETRY_BACKOFF_FACTOR: float = Field(default=0.1, ge=0.1, le=1.0)
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100, ge=10, le=1000)
    RATE_LIMIT_PERIOD: str = Field(default="minute")  # not int
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    @validator("CHUNK_OVERLAP")
    def validate_chunk_overlap(cls, v, values):
        if "CHUNK_SIZE" in values and v >= values["CHUNK_SIZE"]:
            raise ValueError("CHUNK_OVERLAP must be less than CHUNK_SIZE")
        return v
    
    def create_directories(self):
        """Create necessary directories"""
        self.DOCUMENTS_PATH.mkdir(exist_ok=True)
        self.CHROMA_DB_PATH.mkdir(exist_ok=True)

# Create global settings instance
settings = Settings()