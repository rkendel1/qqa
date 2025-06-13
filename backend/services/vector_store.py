import os
import json
import logging
from pathlib import Path
from typing import List, Set, Dict, Any, Optional
from functools import lru_cache
from datetime import datetime
from prometheus_client import Counter, Histogram
from opentelemetry import trace

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader, PyPDFLoader, UnstructuredMarkdownLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from langchain.schema import Document


from config import settings
from exceptions import VectorStoreException, DocumentProcessingException

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Metrics
vector_store_operations = Counter('vector_store_operations_total', 'Total number of vector store operations', ['operation'])
vector_store_duration = Histogram('vector_store_operation_duration_seconds', 'Vector store operation duration in seconds', ['operation'])
document_processing_errors = Counter('document_processing_errors_total', 'Total number of document processing errors')

class VectorStoreService:
    """Handles document storage and retrieval using ChromaDB with improved reliability and monitoring"""

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
    LOADERS = {
        ".txt": TextLoader,
        ".pdf": PyPDFLoader,
        ".md": UnstructuredMarkdownLoader,
    }

    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
        self.ingested_files: Set[str] = set()
        self.vectorstore: Optional[Chroma] = None
        self._ensure_directories()
        self._load_metadata()
        self._initialize_vectorstore()

    def _ensure_directories(self):
        settings.create_directories()

    def _load_metadata(self):
        try:
            if settings.METADATA_FILE.exists():
                with open(settings.METADATA_FILE, "r") as f:
                    self.ingested_files = set(json.load(f))
            logger.info(f"Loaded metadata for {len(self.ingested_files)} files")
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            self.ingested_files = set()

    def _save_metadata(self):
        try:
            with open(settings.METADATA_FILE, "w") as f:
                json.dump(list(self.ingested_files), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def _initialize_vectorstore(self):
        try:
            with tracer.start_as_current_span("initialize_vectorstore"):
                self.vectorstore = Chroma(
                    collection_name="my_collection",
                    embedding_function=self.embeddings,
                    persist_directory=str(settings.CHROMA_DB_PATH),
                )
            
            logger.info(f"Initialized vector store with {len(self.vectorstore.get_collection().get_chunk_ids())} documents")
                logger.info("Vector store initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            self.vectorstore = None
            raise VectorStoreException(f"Vector store initialization failed: {e}")

    @lru_cache(maxsize=settings.CACHE_SIZE)
    def search_documents(self, query: str, k: Optional[int] = None) -> List[Document]:
        if not self.vectorstore:
            raise VectorStoreException("Vector store not initialized")

        if k is None:
            k = settings.SIMILARITY_K

        try:
            with tracer.start_as_current_span("search_documents") as span:
                span.set_attribute("query", query)
                span.set_attribute("k", k)

                vector_store_operations.labels(operation="search").inc()
                with vector_store_duration.labels(operation="search").time():
                    return self.vectorstore.similarity_search(query, k=k)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise VectorStoreException(f"Document search failed: {e}")

    def ingest_document(self, filepath: Path) -> bool:
        try:
            filename = filepath.name
            ext = filepath.suffix.lower()

            if ext not in self.SUPPORTED_EXTENSIONS:
                logger.warning(f"Unsupported file extension: {ext}")
                return False

            if filename in self.ingested_files:
                logger.info(f"File already ingested: {filename}")
                return True

            with tracer.start_as_current_span("ingest_document") as span:
                span.set_attribute("filename", filename)

                loader_class = self.LOADERS[ext]
                loader = loader_class(str(filepath))
                documents = loader.load()

                for doc in documents:
                    doc.metadata.update({
                        "source": filename,
                        "file_path": str(filepath),
                        "file_size": filepath.stat().st_size,
                        "ingested_at": datetime.now().isoformat()
                    })

                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=settings.CHUNK_SIZE,
                    chunk_overlap=settings.CHUNK_OVERLAP
                )
                chunks = splitter.split_documents(documents)

                vector_store_operations.labels(operation="ingest").inc()
                with vector_store_duration.labels(operation="ingest").time():
                    self.vectorstore.add_documents(chunks)
                    self.vectorstore.persist()

                self.ingested_files.add(filename)
                self._save_metadata()

                logger.info(f"Successfully ingested {filename} ({len(chunks)} chunks)")
                return True

        except Exception as e:
            document_processing_errors.inc()
            logger.error(f"Failed to ingest {filepath}: {e}")
            raise DocumentProcessingException(f"Document ingestion failed: {e}")

    def ingest_all_documents(self) -> int:
        count = 0
        for filepath in settings.DOCUMENTS_PATH.iterdir():
            if filepath.is_file() and self.ingest_document(filepath):
                count += 1
        return count

    def get_ingested_files(self) -> List[str]:
        return list(self.ingested_files)

    def is_ready(self) -> bool:
        if not self.vectorstore:
            return False
        try:
            # Try listing collections to verify the DB is accessible and not empty
            collection = self.vectorstore._collection
            return collection.count() > 0
        except Exception as e:
            logger.warning(f"Vector store readiness check failed: {e}")
            return False

    def get_vector_store(self) -> Chroma:
        if not self.vectorstore:
            raise VectorStoreException("Vector store not initialized")
        return self.vectorstore

    def get_context_sections(self, query: str, k: Optional[int] = None) -> Dict[str, Any]:
        try:
            with tracer.start_as_current_span("get_context_sections") as span:
                span.set_attribute("query", query)
                span.set_attribute("k", k)

                documents = self.search_documents(query, k)
                doc_text = "\n\n".join(doc.page_content for doc in documents)
                return {
                    "retrieved_docs": doc_text,
                    "retrieved_chunks": [doc.page_content for doc in documents],
                    "sources": [
                        {
                            "filename": doc.metadata.get("source"),
                            "metadata": doc.metadata
                        }
                        for doc in documents
                    ],
                }
        except Exception as e:
            logger.error(f"Failed to get context sections: {e}")
            raise VectorStoreException(f"Failed to get context sections: {e}")

    def clear_cache(self):
        self.search_documents.cache_clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_documents": len(self.ingested_files),
            "vector_store_ready": self.is_ready(),
            "cache_info": self.search_documents.cache_info()
        }