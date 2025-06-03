import os
import json
import logging
from pathlib import Path
from typing import List, Set
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader, PyPDFLoader, UnstructuredMarkdownLoader
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.schema import Document
from config import Config

from exceptions import VectorStoreException, DocumentProcessingException

logger = logging.getLogger(__name__)

class VectorStoreService:
    """Handles document storage and retrieval using ChromaDB"""
    
    
    
    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
    LOADERS = {
        ".txt": TextLoader,
        ".pdf": PyPDFLoader,
        ".md": UnstructuredMarkdownLoader,
    }
    
    def __init__(self):
        self.config = Config()
        self.embeddings = HuggingFaceEmbeddings(model_name=self.config.EMBEDDING_MODEL)
        
        self.ingested_files: Set[str] = set()
        
        self._ensure_directories()
        self._load_metadata()
        self._initialize_vectorstore()
    
    def _ensure_directories(self):
        """Create necessary directories"""
        self.config.DOCUMENTS_PATH.mkdir(exist_ok=True)
        self.config.CHROMA_DB_PATH.mkdir(exist_ok=True)
    
    def _load_metadata(self):
        """Load ingested files metadata"""
        try:
            if self.config.METADATA_FILE.exists():
                with open(self.config.METADATA_FILE, "r") as f:
                    self.ingested_files = set(json.load(f))
            logger.info(f"Loaded metadata for {len(self.ingested_files)} files")
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            self.ingested_files = set()
    
    def _save_metadata(self):
        """Save ingested files metadata"""
        try:
            with open(self.config.METADATA_FILE, "w") as f:
                json.dump(list(self.ingested_files), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
    
    def _initialize_vectorstore(self):
        try:
            self.vectorstore = Chroma(
                collection_name="my_collection",
                embedding_function=self.embeddings,
                persist_directory=str(self.config.CHROMA_DB_PATH),
            )
            logger.info("Vector store initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise VectorStoreException(f"Vector store initialization failed: {e}")
    
    def ingest_document(self, filepath: Path) -> bool:
        """Ingest a single document"""
        try:
            filename = filepath.name
            ext = filepath.suffix.lower()
            
            if ext not in self.SUPPORTED_EXTENSIONS:
                logger.warning(f"Unsupported file extension: {ext}")
                return False
            
            if filename in self.ingested_files:
                logger.info(f"File already ingested: {filename}")
                return True
            
            loader_class = self.LOADERS[ext]
            loader = loader_class(str(filepath))
            documents = loader.load()
            
            for doc in documents:
                doc.metadata.update({
                    "source": filename,
                    "file_path": str(filepath),
                    "file_size": filepath.stat().st_size
                })
            
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.CHUNK_SIZE,
                chunk_overlap=self.config.CHUNK_OVERLAP
            )
            chunks = splitter.split_documents(documents)
            
            self.vectorstore.add_documents(chunks)
            self.vectorstore.persist()
            
            self.ingested_files.add(filename)
            self._save_metadata()
            
            logger.info(f"Successfully ingested {filename} ({len(chunks)} chunks)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ingest {filepath}: {e}")
            raise DocumentProcessingException(f"Document ingestion failed: {e}")
    
    def ingest_all_documents(self) -> int:
        """Ingest all documents in the documents directory"""
        count = 0
        for filepath in self.config.DOCUMENTS_PATH.iterdir():
            if filepath.is_file() and self.ingest_document(filepath):
                count += 1
        return count
    
    def search_documents(self, query: str, k: int = None) -> List[Document]:
        """Search for relevant documents"""
        if not self.vectorstore:
            raise VectorStoreException("Vector store not initialized")
        
        k = k or self.config.SIMILARITY_K
        try:
            return self.vectorstore.similarity_search(query, k=k)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise VectorStoreException(f"Document search failed: {e}")
    
    def get_ingested_files(self) -> List[str]:
        """Get list of ingested files"""
        return list(self.ingested_files)
    
    def is_ready(self) -> bool:
        """Check if vector store is ready"""
        return self.vectorstore is not None
    
    def get_vector_store(self):
        return self.vectorstore