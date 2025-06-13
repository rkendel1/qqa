import os
import json
import logging
from pathlib import Path
from typing import List, Set, Dict, Any, Optional, Union
from functools import lru_cache
from datetime import datetime
import hashlib
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock

from prometheus_client import Counter, Histogram
from opentelemetry import trace

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader, PyPDFLoader, UnstructuredMarkdownLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.schema import Document

# Assuming these exist in your project
from config import settings
from exceptions import VectorStoreException, DocumentProcessingException

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Metrics
vector_store_operations = Counter('vector_store_operations_total', 'Total number of vector store operations', ['operation'])
vector_store_duration = Histogram('vector_store_operation_duration_seconds', 'Vector store operation duration in seconds', ['operation'])
document_processing_errors = Counter('document_processing_errors_total', 'Total number of document processing errors')
cache_hits = Counter('vector_store_cache_hits_total', 'Total number of cache hits')
cache_misses = Counter('vector_store_cache_misses_total', 'Total number of cache misses')

@dataclass
class DocumentInfo:
    """Enhanced document metadata"""
    filename: str
    filepath: str
    file_size: int
    file_hash: str
    ingested_at: str
    chunk_count: int
    last_modified: float

class VectorStoreService:
    """Enhanced document storage and retrieval using ChromaDB with improved reliability, monitoring, and performance"""

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".html"}
    LOADERS = {
        ".txt": TextLoader,
        ".pdf": PyPDFLoader,
        ".md": UnstructuredMarkdownLoader,
    }

    def __init__(self, max_workers: int = 4):
        self.embeddings = self._initialize_embeddings()
        self.ingested_files: Dict[str, DocumentInfo] = {}
        self.vectorstore: Optional[Chroma] = None
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._metadata_lock = Lock()
        self._ensure_directories()
        self._load_metadata()
        self._initialize_vectorstore()

    def _initialize_embeddings(self) -> HuggingFaceEmbeddings:
        """Initialize embeddings with error handling and validation"""
        try:
            embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={'device': 'cpu'},  # Explicit device setting
                encode_kwargs={'normalize_embeddings': True}  # Better retrieval performance
            )
            # Test embeddings with a sample text
            test_embedding = embeddings.embed_query("test")
            if not test_embedding:
                raise ValueError("Embedding model failed to generate embeddings")
            logger.info(f"Embeddings initialized successfully with model: {settings.EMBEDDING_MODEL}")
            return embeddings
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
            raise VectorStoreException(f"Embedding initialization failed: {e}")

    def _ensure_directories(self):
        """Ensure all required directories exist"""
        try:
            settings.create_directories()
            # Create backup directory for metadata
            backup_dir = settings.CHROMA_DB_PATH.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directories: {e}")
            raise VectorStoreException(f"Directory creation failed: {e}")

    def _calculate_file_hash(self, filepath: Path) -> str:
        """Calculate SHA-256 hash of file for change detection"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {filepath}: {e}")
            return ""

    def _load_metadata(self):
        """Load metadata with backup and recovery"""
        try:
            with self._metadata_lock:
                if settings.METADATA_FILE.exists():
                    with open(settings.METADATA_FILE, "r") as f:
                        data = json.load(f)
                    
                    # Handle both old and new metadata formats
                    if isinstance(data, list):
                        # Old format - convert to new format
                        self.ingested_files = {filename: DocumentInfo(
                            filename=filename,
                            filepath="",
                            file_size=0,
                            file_hash="",
                            ingested_at=datetime.now().isoformat(),
                            chunk_count=0,
                            last_modified=0
                        ) for filename in data}
                        self._save_metadata()  # Upgrade metadata format
                    else:
                        # New format
                        self.ingested_files = {
                            filename: DocumentInfo(**info) 
                            for filename, info in data.items()
                        }
                else:
                    self.ingested_files = {}
                
                logger.info(f"Loaded metadata for {len(self.ingested_files)} files")
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            # Try to load from backup
            self._load_metadata_backup()

    def _load_metadata_backup(self):
        """Load metadata from backup if main file fails"""
        backup_path = settings.CHROMA_DB_PATH.parent / "backups" / "metadata_backup.json"
        try:
            if backup_path.exists():
                with open(backup_path, "r") as f:
                    data = json.load(f)
                self.ingested_files = {
                    filename: DocumentInfo(**info) 
                    for filename, info in data.items()
                }
                logger.info(f"Loaded metadata from backup for {len(self.ingested_files)} files")
            else:
                self.ingested_files = {}
        except Exception as e:
            logger.error(f"Failed to load backup metadata: {e}")
            self.ingested_files = {}

    def _save_metadata(self):
        """Save metadata with backup"""
        try:
            with self._metadata_lock:
                # Create backup first
                backup_path = settings.CHROMA_DB_PATH.parent / "backups" / "metadata_backup.json"
                if settings.METADATA_FILE.exists():
                    import shutil
                    shutil.copy2(settings.METADATA_FILE, backup_path)
                
                # Save current metadata
                data = {
                    filename: info.__dict__ 
                    for filename, info in self.ingested_files.items()
                }
                with open(settings.METADATA_FILE, "w") as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def _initialize_vectorstore(self):
        """Initialize vector store with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with tracer.start_as_current_span("initialize_vectorstore"):
                    self.vectorstore = Chroma(
                        collection_name="my_collection",
                        embedding_function=self.embeddings,
                        persist_directory=str(settings.CHROMA_DB_PATH),
                    )
                
                # Test the connection
                self.vectorstore._collection.count()
                logger.info("Vector store initialized successfully")
                return
                
            except Exception as e:
                logger.warning(f"Vector store initialization attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to initialize vector store after {max_retries} attempts: {e}")
                    self.vectorstore = None
                    raise VectorStoreException(f"Vector store initialization failed: {e}")
                
                # Wait before retry
                import time
                time.sleep(2 ** attempt)

    @contextmanager
    def _operation_metrics(self, operation: str):
        """Context manager for operation metrics"""
        vector_store_operations.labels(operation=operation).inc()
        with vector_store_duration.labels(operation=operation).time():
            yield

    @lru_cache(maxsize=settings.CACHE_SIZE)
    def search_documents(self, query: str, k: Optional[int] = None, score_threshold: float = 0.0) -> List[Document]:
        """Enhanced search with score filtering and better caching"""
        if not self.vectorstore:
            raise VectorStoreException("Vector store not initialized")

        if k is None:
            k = settings.SIMILARITY_K

        cache_hits.inc()
        
        try:
            with tracer.start_as_current_span("search_documents") as span:
                span.set_attribute("query", query)
                span.set_attribute("k", k)
                span.set_attribute("score_threshold", score_threshold)

                with self._operation_metrics("search"):
                    if score_threshold > 0:
                        # Use similarity search with score threshold
                        results = self.vectorstore.similarity_search_with_score(query, k=k)
                        return [doc for doc, score in results if score >= score_threshold]
                    else:
                        return self.vectorstore.similarity_search(query, k=k)
                        
        except Exception as e:
            cache_misses.inc()
            logger.error(f"Search failed: {e}")
            raise VectorStoreException(f"Document search failed: {e}")

    def _needs_reingestion(self, filepath: Path, filename: str) -> bool:
        """Check if document needs reingestion based on file changes"""
        if filename not in self.ingested_files:
            return True
        
        doc_info = self.ingested_files[filename]
        current_mtime = filepath.stat().st_mtime
        current_size = filepath.stat().st_size
        current_hash = self._calculate_file_hash(filepath)
        
        return (
            doc_info.last_modified != current_mtime or
            doc_info.file_size != current_size or
            doc_info.file_hash != current_hash
        )

    def ingest_document(self, filepath: Path, force_reingest: bool = False) -> bool:
        """Enhanced document ingestion with change detection and better error handling"""
        try:
            filename = filepath.name
            ext = filepath.suffix.lower()

            if ext not in self.SUPPORTED_EXTENSIONS:
                logger.warning(f"Unsupported file extension: {ext}")
                return False

            if not filepath.exists():
                logger.error(f"File does not exist: {filepath}")
                return False

            # Check if reingestion is needed
            if not force_reingest and not self._needs_reingestion(filepath, filename):
                logger.info(f"File unchanged, skipping: {filename}")
                return True

            with tracer.start_as_current_span("ingest_document") as span:
                span.set_attribute("filename", filename)
                span.set_attribute("force_reingest", force_reingest)

                # Remove existing document if reingestting
                if filename in self.ingested_files and force_reingest:
                    self._remove_document_from_store(filename)

                # Load document
                loader_class = self.LOADERS.get(ext)
                if not loader_class:
                    logger.error(f"No loader available for extension: {ext}")
                    return False

                loader = loader_class(str(filepath))
                documents = loader.load()

                if not documents:
                    logger.warning(f"No content loaded from {filename}")
                    return False

                # Enhanced metadata
                file_stat = filepath.stat()
                file_hash = self._calculate_file_hash(filepath)
                
                for doc in documents:
                    doc.metadata.update({
                        "source": filename,
                        "file_path": str(filepath),
                        "file_size": file_stat.st_size,
                        "file_hash": file_hash,
                        "ingested_at": datetime.now().isoformat(),
                        "last_modified": file_stat.st_mtime,
                        "file_extension": ext
                    })

                # Smart chunking based on document type
                splitter = self._get_text_splitter(ext)
                chunks = splitter.split_documents(documents)

                if not chunks:
                    logger.warning(f"No chunks created from {filename}")
                    return False

                # Add to vector store
                with self._operation_metrics("ingest"):
                    self.vectorstore.add_documents(chunks)
                    self.vectorstore.persist()

                # Update metadata
                doc_info = DocumentInfo(
                    filename=filename,
                    filepath=str(filepath),
                    file_size=file_stat.st_size,
                    file_hash=file_hash,
                    ingested_at=datetime.now().isoformat(),
                    chunk_count=len(chunks),
                    last_modified=file_stat.st_mtime
                )
                
                with self._metadata_lock:
                    self.ingested_files[filename] = doc_info
                    self._save_metadata()

                logger.info(f"Successfully ingested {filename} ({len(chunks)} chunks)")
                return True

        except Exception as e:
            document_processing_errors.inc()
            logger.error(f"Failed to ingest {filepath}: {e}")
            raise DocumentProcessingException(f"Document ingestion failed for {filepath}: {e}")

    def _get_text_splitter(self, file_extension: str) -> RecursiveCharacterTextSplitter:
        """Get optimized text splitter based on file type"""
        if file_extension == ".md":
            # Markdown-specific separators
            separators = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]
        elif file_extension == ".pdf":
            # PDF-specific separators
            separators = ["\n\n", "\n", ". ", " ", ""]
        else:
            # Default separators
            separators = ["\n\n", "\n", " ", ""]

        return RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=separators,
            length_function=len,
        )

    def _remove_document_from_store(self, filename: str):
        """Remove document from vector store (placeholder - ChromaDB doesn't support easy deletion)"""
        # Note: ChromaDB doesn't have a built-in way to delete documents by metadata
        # This would require rebuilding the collection or using document IDs
        logger.warning(f"Document removal not implemented for ChromaDB: {filename}")

    async def ingest_all_documents_async(self) -> int:
        """Asynchronously ingest all documents"""
        loop = asyncio.get_event_loop()
        
        tasks = []
        for filepath in settings.DOCUMENTS_PATH.iterdir():
            if filepath.is_file():
                task = loop.run_in_executor(
                    self.executor, 
                    self.ingest_document, 
                    filepath
                )
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for result in results if result is True)
        
        logger.info(f"Async ingestion completed: {success_count}/{len(tasks)} files successful")
        return success_count

    def ingest_all_documents(self) -> int:
        """Synchronous batch ingestion with progress tracking"""
        count = 0
        total_files = list(settings.DOCUMENTS_PATH.iterdir())
        
        for i, filepath in enumerate(total_files, 1):
            if filepath.is_file():
                try:
                    if self.ingest_document(filepath):
                        count += 1
                    logger.info(f"Progress: {i}/{len(total_files)} files processed")
                except Exception as e:
                    logger.error(f"Failed to process {filepath}: {e}")
                    continue
        
        return count

    def get_ingested_files(self) -> List[Dict[str, Any]]:
        """Get detailed information about ingested files"""
        return [
            {
                "filename": info.filename,
                "filepath": info.filepath,
                "file_size": info.file_size,
                "chunk_count": info.chunk_count,
                "ingested_at": info.ingested_at,
                "last_modified": datetime.fromtimestamp(info.last_modified).isoformat() if info.last_modified else None
            }
            for info in self.ingested_files.values()
        ]

    def is_ready(self) -> bool:
        """Enhanced readiness check"""
        if not self.vectorstore:
            return False
        try:
            collection = self.vectorstore._collection
            count = collection.count()
            return count > 0
        except Exception as e:
            logger.warning(f"Vector store readiness check failed: {e}")
            return False

    def get_vector_store(self) -> Chroma:
        """Get vector store with validation"""
        if not self.vectorstore:
            raise VectorStoreException("Vector store not initialized")
        return self.vectorstore

    def get_context_sections(self, query: str, k: Optional[int] = None, include_scores: bool = False) -> Dict[str, Any]:
        """Enhanced context retrieval with optional scores"""
        try:
            with tracer.start_as_current_span("get_context_sections") as span:
                span.set_attribute("query", query)
                span.set_attribute("k", k)
                span.set_attribute("include_scores", include_scores)

                if include_scores:
                    results = self.vectorstore.similarity_search_with_score(query, k=k or settings.SIMILARITY_K)
                    documents = [doc for doc, score in results]
                    scores = [score for doc, score in results]
                else:
                    documents = self.search_documents(query, k)
                    scores = None

                doc_text = "\n\n".join(doc.page_content for doc in documents)
                
                context = {
                    "retrieved_docs": doc_text,
                    "retrieved_chunks": [doc.page_content for doc in documents],
                    "sources": [
                        {
                            "filename": doc.metadata.get("source"),
                            "metadata": doc.metadata
                        }
                        for doc in documents
                    ],
                    "query": query,
                    "timestamp": datetime.now().isoformat()
                }
                
                if include_scores and scores:
                    context["scores"] = scores
                
                return context
                
        except Exception as e:
            logger.error(f"Failed to get context sections: {e}")
            raise VectorStoreException(f"Failed to get context sections: {e}")

    def clear_cache(self):
        """Clear all caches"""
        self.search_documents.cache_clear()
        logger.info("Caches cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Enhanced statistics"""
        cache_info = self.search_documents.cache_info()
        
        total_chunks = sum(info.chunk_count for info in self.ingested_files.values())
        total_size = sum(info.file_size for info in self.ingested_files.values())
        
        return {
            "total_documents": len(self.ingested_files),
            "total_chunks": total_chunks,
            "total_size_bytes": total_size,
            "vector_store_ready": self.is_ready(),
            "cache_info": {
                "hits": cache_info.hits,
                "misses": cache_info.misses,
                "maxsize": cache_info.maxsize,
                "currsize": cache_info.currsize,
                "hit_rate": cache_info.hits / (cache_info.hits + cache_info.misses) if (cache_info.hits + cache_info.misses) > 0 else 0
            },
            "embedding_model": settings.EMBEDDING_MODEL,
            "supported_extensions": list(self.SUPPORTED_EXTENSIONS)
        }

    def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        health = {
            "status": "healthy",
            "checks": {
                "vector_store_initialized": self.vectorstore is not None,
                "vector_store_accessible": False,
                "embeddings_working": False,
                "metadata_loaded": len(self.ingested_files) >= 0,
                "directories_exist": settings.CHROMA_DB_PATH.exists()
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Test vector store access
        try:
            if self.vectorstore:
                self.vectorstore._collection.count()
                health["checks"]["vector_store_accessible"] = True
        except Exception as e:
            health["checks"]["vector_store_accessible"] = False
            logger.error(f"Vector store access check failed: {e}")
        
        # Test embeddings
        try:
            test_embedding = self.embeddings.embed_query("test")
            health["checks"]["embeddings_working"] = len(test_embedding) > 0
        except Exception as e:
            health["checks"]["embeddings_working"] = False
            logger.error(f"Embeddings check failed: {e}")
        
        # Overall status
        if not all(health["checks"].values()):
            health["status"] = "unhealthy"
        
        return health

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        if self.executor:
            self.executor.shutdown(wait=True)
        logger.info("VectorStoreService cleanup completed")

# Convenience function for easy initialization
def create_vector_store_service(**kwargs) -> VectorStoreService:
    """Factory function to create VectorStoreService with custom settings"""
    return VectorStoreService(**kwargs)