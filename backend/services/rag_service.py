import time
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union, Protocol, Generator
from dataclasses import dataclass
from enum import Enum
from tenacity import retry, stop_after_attempt, wait_exponential
from prometheus_client import Counter, Histogram, Gauge
from opentelemetry import trace
from contextlib import contextmanager

from services.vector_store import VectorStoreService
from services.llm_service import LLMService
from models import QueryResponse
from exceptions import RAGException, VectorStoreException, LLMException
from config import settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Enhanced Metrics
rag_queries_total = Counter('rag_queries_total', 'Total number of RAG queries', ['query_type', 'status'])
rag_query_duration = Histogram('rag_query_duration_seconds', 'RAG query duration in seconds', ['query_type'])
rag_errors_total = Counter('rag_errors_total', 'Total number of RAG errors', ['error_type'])
rag_context_length = Histogram('rag_context_length_chars', 'Length of retrieved context in characters')
rag_prompt_length = Histogram('rag_prompt_length_chars', 'Length of generated prompt in characters')
rag_active_queries = Gauge('rag_active_queries', 'Number of currently active RAG queries')

class QueryType(Enum):
    """Enumeration of query types for metrics and monitoring"""
    STANDARD = "standard"
    MINIMAL = "minimal"
    SANITY_CHECK = "sanity_check"
    STREAMING = "streaming"

class RAGStatus(Enum):
    """RAG service status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    ERROR = "error"

@dataclass
class QueryConfig:
    """Configuration for RAG queries"""
    max_results: int = 5
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    stream: bool = False
    include_metadata: bool = True
    min_score_threshold: Optional[float] = None

@dataclass
class QueryMetrics:
    """Query execution metrics"""
    total_time: float
    retrieval_time: float
    generation_time: float
    prompt_length: int
    context_length: int
    num_sources: int
    
class VectorStoreProtocol(Protocol):
    """Enhanced protocol defining required vector store methods"""
    def is_ready(self) -> bool: ...
    def get_ingested_files(self) -> List[str]: ...
    def ingest_all_documents(self) -> int: ...
    def get_context_sections(self, query: str, k: int) -> Dict[str, Any]: ...
    def get_stats(self) -> Dict[str, Any]: ...
    def collections(self) -> Any: ...
    def clear_cache(self) -> None: ...

class RAGService:
    """Enhanced RAG service with improved reliability, monitoring, and features"""
    
    def __init__(self, vector_service: VectorStoreService, llm_service: LLMService):
        self.vector_service = vector_service
        self.llm_service = llm_service
        self.vector_store: VectorStoreProtocol = self.vector_service.get_vector_store()
        
        # Configuration
        self.max_prompt_length = getattr(settings, 'MAX_PROMPT_LENGTH', 32000)
        self.max_context_length = getattr(settings, 'MAX_CONTEXT_LENGTH', 16000)
        self.default_system_prompt = getattr(settings, 'DEFAULT_SYSTEM_PROMPT', 
            "You are a helpful assistant. Answer questions based on the provided context. "
            "If you cannot find the answer in the context, say so clearly.")
        
        # Cache for frequently used data
        self._status_cache = {}
        self._status_cache_ttl = 30  # seconds
        self._last_status_check = 0
        
        logger.info("RAG Service initialized")

    def _validate_query_input(self, query: str, config: QueryConfig) -> None:
        """Validate query input parameters"""
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        
        if len(query.strip()) == 0:
            raise ValueError("Query cannot be empty or whitespace only")
        
        if len(query) > getattr(settings, 'MAX_QUERY_LENGTH', 1000):
            raise ValueError(f"Query too long (max {getattr(settings, 'MAX_QUERY_LENGTH', 1000)} characters)")
        
        if config.max_results <= 0 or config.max_results > 50:
            raise ValueError("max_results must be between 1 and 50")
        
        if config.temperature is not None and not 0.0 <= config.temperature <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        
        if config.max_tokens is not None and config.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

    def _sanitize_input(self, text: str) -> str:
        """Sanitize input text to prevent injection attacks"""
        if not isinstance(text, str):
            return str(text)
        
        # Remove potentially harmful characters/patterns
        import re
        # Remove control characters except newlines and tabs
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        # Limit consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def vector_store_is_ready(self) -> bool:
        """Enhanced vector store readiness check"""
        try:
            with tracer.start_as_current_span("vector_store_readiness_check"):
                # Try the protocol method first
                if hasattr(self.vector_store, 'is_ready') and callable(self.vector_store.is_ready):
                    return self.vector_store.is_ready()
                
                # Fallback to collections check
                if hasattr(self.vector_store, "collections"):
                    collections = None
                    if callable(self.vector_store.collections):
                        collections = self.vector_store.collections()
                    else:
                        collections = self.vector_store.collections
                    return collections is not None
                
                # Last resort - try to get stats
                if hasattr(self.vector_store, "get_stats"):
                    self.vector_store.get_stats()
                    return True
                
                return False
                
        except Exception as e:
            logger.warning(f"Vector store readiness check failed: {e}")
            return False

    @contextmanager
    def _query_context(self, query_type: QueryType):
        """Context manager for query execution monitoring"""
        rag_active_queries.inc()
        start_time = time.time()
        
        try:
            yield
            rag_queries_total.labels(query_type=query_type.value, status="success").inc()
        except Exception as e:
            rag_queries_total.labels(query_type=query_type.value, status="error").inc()
            rag_errors_total.labels(error_type=type(e).__name__).inc()
            raise
        finally:
            rag_active_queries.dec()
            duration = time.time() - start_time
            rag_query_duration.labels(query_type=query_type.value).observe(duration)

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def query(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None,
        system_context: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        config: Optional[QueryConfig] = None
    ) -> Dict[str, Any]:
        """Enhanced query processing with comprehensive monitoring and validation"""
        
        # Set defaults
        if config is None:
            config = QueryConfig()
        
        # Validate inputs
        self._validate_query_input(query, config)
        query = self._sanitize_input(query)
        
        query_type = QueryType.STREAMING if config.stream else QueryType.STANDARD
        
        with self._query_context(query_type):
            with tracer.start_as_current_span("rag_query") as span:
                span.set_attribute("query", query[:100])  # Truncate for privacy
                span.set_attribute("query_length", len(query))
                span.set_attribute("max_results", config.max_results)
                span.set_attribute("stream", config.stream)
                
                metrics = QueryMetrics(0, 0, 0, 0, 0, 0)
                start_time = time.time()
                
                try:
                    # Step 1: Retrieve context
                    retrieval_start = time.time()
                    context_sections = self._retrieve_context(query, config)
                    metrics.retrieval_time = time.time() - retrieval_start
                    metrics.context_length = len(context_sections.get("retrieved_docs", ""))
                    metrics.num_sources = len(context_sections.get("sources", []))
                    
                    # Record context metrics
                    rag_context_length.observe(metrics.context_length)
                    
                    # Step 2: Build prompt
                    prompt = self._build_prompt(
                        retrieved_docs=context_sections.get("retrieved_docs", ""),
                        system_context=system_context or self.default_system_prompt,
                        user_context=user_context or {},
                        chat_history=chat_history or [],
                        question=query,
                    )
                    
                    metrics.prompt_length = len(prompt)
                    rag_prompt_length.observe(metrics.prompt_length)
                    
                    # Step 3: Generate response
                    generation_start = time.time()
                    response = self._generate_response(prompt, config)
                    metrics.generation_time = time.time() - generation_start
                    
                    metrics.total_time = time.time() - start_time
                    
                    # Build response
                    result = {
                        "response": response,
                        "sources": context_sections.get("sources", []),
                        "num_sources": metrics.num_sources,
                        "processing_time": metrics.total_time,
                    }
                    
                    if config.include_metadata:
                        result["metadata"] = {
                            "retrieval_time": metrics.retrieval_time,
                            "generation_time": metrics.generation_time,
                            "prompt_length": metrics.prompt_length,
                            "context_length": metrics.context_length,
                            "query_type": query_type.value
                        }
                    
                    return result
                    
                except VectorStoreException as e:
                    logger.error(f"Vector store error in query: {e}")
                    raise RAGException(f"Context retrieval failed: {e}")
                except LLMException as e:
                    logger.error(f"LLM error in query: {e}")
                    raise RAGException(f"Response generation failed: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error in query: {e}")
                    raise RAGException(f"Query processing failed: {e}")

    def _retrieve_context(self, query: str, config: QueryConfig) -> Dict[str, Any]:
        """Retrieve context with enhanced error handling"""
        try:
            with tracer.start_as_current_span("retrieve_context"):
                context_sections = self.vector_service.get_context_sections(
                    query, 
                    k=config.max_results
                )
                
                # Apply score threshold if specified
                if config.min_score_threshold is not None and "scores" in context_sections:
                    filtered_docs = []
                    filtered_sources = []
                    filtered_scores = []
                    
                    for i, score in enumerate(context_sections.get("scores", [])):
                        if score >= config.min_score_threshold:
                            if i < len(context_sections.get("retrieved_docs", [])):
                                filtered_docs.append(context_sections["retrieved_docs"][i])
                            if i < len(context_sections.get("sources", [])):
                                filtered_sources.append(context_sections["sources"][i])
                            filtered_scores.append(score)
                    
                    context_sections["retrieved_docs"] = "\n\n".join(filtered_docs)
                    context_sections["sources"] = filtered_sources
                    context_sections["scores"] = filtered_scores
                
                return context_sections
                
        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")
            raise VectorStoreException(f"Failed to retrieve context: {e}")

    def _generate_response(self, prompt: str, config: QueryConfig) -> Union[str, Generator[str, None, None]]:
        """Generate response with enhanced error handling"""
        try:
            with tracer.start_as_current_span("generate_response"):
                if config.stream:
                    return self._create_streaming_response(prompt, config)
                else:
                    return self.llm_service.generate_response(
                        prompt,
                        stream=False,
                        temperature=config.temperature,
                        max_tokens=config.max_tokens,
                        top_p=config.top_p,
                        top_k=config.top_k
                    )
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            raise LLMException(f"Failed to generate response: {e}")

    def _create_streaming_response(self, prompt: str, config: QueryConfig) -> Generator[str, None, None]:
        """Create a managed streaming response"""
        try:
            response_generator = self.llm_service.generate_response(
                prompt,
                stream=True,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k
            )
            
            for chunk in response_generator:
                yield chunk
                
        except Exception as e:
            logger.error(f"Streaming response failed: {e}")
            raise LLMException(f"Streaming response failed: {e}")

    def _build_prompt(
        self,
        retrieved_docs: str,
        system_context: str,
        user_context: Dict[str, Any],
        chat_history: List[Dict[str, str]],
        question: str
    ) -> str:
        """Enhanced prompt building with better formatting and validation"""
        try:
            with tracer.start_as_current_span("build_prompt") as span:
                # Sanitize all inputs
                system_context = self._sanitize_input(system_context)
                retrieved_docs = self._sanitize_input(retrieved_docs)
                question = self._sanitize_input(question)
                
                # Truncate context if too long
                if len(retrieved_docs) > self.max_context_length:
                    retrieved_docs = retrieved_docs[:self.max_context_length] + "...[truncated]"
                    logger.warning(f"Context truncated to {self.max_context_length} characters")
                
                # Build sections
                sections = []
                
                if system_context:
                    sections.append(f"System: {system_context}")
                
                if user_context:
                    user_context_str = self._format_user_context(user_context)
                    if user_context_str:
                        sections.append(f"User Profile: {user_context_str}")
                
                if chat_history:
                    history_str = self._format_chat_history(chat_history)
                    if history_str:
                        sections.append(f"Chat History:\n{history_str}")
                
                if retrieved_docs:
                    sections.append(f"Relevant Documents:\n{retrieved_docs}")
                
                sections.append(f"Question: {question}")
                sections.append("Answer:")
                
                prompt = "\n\n".join(sections)
                
                # Validate prompt length
                if len(prompt) > self.max_prompt_length:
                    logger.warning(f"Prompt length ({len(prompt)}) exceeds maximum ({self.max_prompt_length})")
                    # Truncate retrieved docs to fit
                    excess = len(prompt) - self.max_prompt_length
                    if len(retrieved_docs) > excess:
                        retrieved_docs = retrieved_docs[:len(retrieved_docs) - excess - 100] + "...[truncated]"
                        # Rebuild prompt
                        sections = [s for s in sections if not s.startswith("Relevant Documents:")]
                        sections.insert(-2, f"Relevant Documents:\n{retrieved_docs}")
                        prompt = "\n\n".join(sections)
                
                span.set_attribute("prompt_length", len(prompt))
                span.set_attribute("context_length", len(retrieved_docs))
                
                return prompt
                
        except Exception as e:
            logger.error(f"Failed to build prompt: {e}")
            raise RAGException(f"Prompt building failed: {e}")

    def _format_user_context(self, user_context: Dict[str, Any]) -> str:
        """Format user context for prompt"""
        if not user_context:
            return ""
        
        formatted_items = []
        for key, value in user_context.items():
            if value is not None:
                formatted_items.append(f"{key}: {self._sanitize_input(str(value))}")
        
        return ", ".join(formatted_items)

    def _format_chat_history(self, chat_history: List[Dict[str, str]]) -> str:
        """Format chat history for prompt"""
        if not chat_history:
            return ""
        
        formatted_history = []
        for message in chat_history[-10:]:  # Limit to last 10 messages
            msg_type = message.get('type', 'user').capitalize()
            content = self._sanitize_input(message.get('content', ''))
            if content:
                formatted_history.append(f"{msg_type}: {content}")
        
        return "\n".join(formatted_history)

    def query_minimal(self, question: str, max_results: int = 3) -> Dict[str, Any]:
        """Minimal query implementation with proper error handling"""
        config = QueryConfig(
            max_results=max_results,
            include_metadata=False,
            stream=False
        )
        
        with self._query_context(QueryType.MINIMAL):
            try:
                return self.query(
                    query=question,
                    config=config
                )
            except Exception as e:
                logger.error(f"Minimal query failed: {e}")
                raise RAGException(f"Minimal query failed: {e}")

    def query_with_sanity_check(
        self,
        question: str,
        max_results: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """Query with sanity check - refactored to reduce duplication"""
        
        with self._query_context(QueryType.SANITY_CHECK):
            try:
                # Get initial response
                config = QueryConfig(
                    max_results=max_results,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )
                
                initial_result = self.query(question, config=config)
                response = initial_result["response"]
                
                # Perform sanity check
                sanity_prompt = (
                    f"Please verify if the following answer appropriately addresses the question.\n"
                    f"Question: {question}\n"
                    f"Answer: {response}\n"
                    f"Respond with 'Yes' or 'No' and a brief explanation."
                )
                
                sanity_check = self.llm_service.generate_response(
                    sanity_prompt,
                    stream=False,
                    temperature=0.0,
                    max_tokens=100
                )
                
                return {
                    "response": response,
                    "sanity_check": sanity_check,
                    "sources": initial_result["sources"],
                    "num_sources": initial_result["num_sources"],
                    "processing_time": initial_result["processing_time"]
                }
                
            except Exception as e:
                logger.error(f"Query with sanity check failed: {e}")
                raise RAGException(f"Query with sanity check failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Enhanced status check with caching and comprehensive health metrics"""
        current_time = time.time()
        
        # Use cached status if still valid
        if (current_time - self._last_status_check < self._status_cache_ttl and 
            self._status_cache):
            return self._status_cache
        
        try:
            with tracer.start_as_current_span("get_status"):
                # Get component statuses
                vector_ready = self.vector_store_is_ready()
                llm_available = self.llm_service.is_available()
                
                # Get detailed information
                vector_store_stats = {}
                llm_info = {}
                ingested_files_count = 0
                
                try:
                    vector_store_stats = self.vector_service.get_stats()
                except Exception as e:
                    logger.warning(f"Failed to get vector store stats: {e}")
                    vector_store_stats = {"error": str(e)}
                
                try:
                    llm_info = self.llm_service.get_model_info()
                except Exception as e:
                    logger.warning(f"Failed to get LLM info: {e}")
                    llm_info = {"error": str(e)}
                
                try:
                    if hasattr(self.vector_store, "get_ingested_files"):
                        ingested_files = self.vector_store.get_ingested_files()
                        ingested_files_count = len(ingested_files)
                except Exception as e:
                    logger.warning(f"Failed to get ingested files count: {e}")
                
                # Determine overall status
                if vector_ready and llm_available:
                    status = RAGStatus.HEALTHY.value
                elif vector_ready or llm_available:
                    status = RAGStatus.DEGRADED.value
                else:
                    status = RAGStatus.UNHEALTHY.value
                
                status_info = {
                    "status": status,
                    "timestamp": current_time,
                    "components": {
                        "vector_store_ready": vector_ready,
                        "llm_available": llm_available,
                        "documents_ingested": ingested_files_count,
                    },
                    "details": {
                        "vector_store_stats": vector_store_stats,
                        "llm_info": llm_info,
                    },
                    "configuration": {
                        "max_prompt_length": self.max_prompt_length,
                        "max_context_length": self.max_context_length,
                        "default_system_prompt": self.default_system_prompt[:100] + "..." if len(self.default_system_prompt) > 100 else self.default_system_prompt,
                    }
                }
                
                # Cache the result
                self._status_cache = status_info
                self._last_status_check = current_time
                
                return status_info
                
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            error_status = {
                "status": RAGStatus.ERROR.value,
                "timestamp": current_time,
                "error": str(e)
            }
            self._status_cache = error_status
            self._last_status_check = current_time
            return error_status

    def ingest_documents(self) -> Dict[str, Any]:
        """Enhanced document ingestion with better monitoring"""
        try:
            with tracer.start_as_current_span("ingest_documents") as span:
                start_time = time.time()
                
                count = self.vector_store.ingest_all_documents()
                
                processing_time = time.time() - start_time
                span.set_attribute("documents_ingested", count)
                span.set_attribute("processing_time", processing_time)
                
                # Clear status cache to force refresh
                self._status_cache = {}
                self._last_status_check = 0
                
                return {
                    "documents_ingested": count,
                    "processing_time": processing_time,
                    "status": "success"
                }
                
        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            raise RAGException(f"Document ingestion failed: {e}")

    def clear_cache(self) -> Dict[str, Any]:
        """Enhanced cache clearing with status reporting"""
        try:
            with tracer.start_as_current_span("clear_cache"):
                # Clear vector service cache
                self.vector_service.clear_cache()
                
                # Clear internal caches
                self._status_cache = {}
                self._last_status_check = 0
                
                return {
                    "status": "success",
                    "message": "All caches cleared successfully"
                }
                
        except Exception as e:
            logger.error(f"Cache clearing failed: {e}")
            raise RAGException(f"Cache clearing failed: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive service metrics"""
        try:
            from prometheus_client import REGISTRY
            
            metrics_data = {}
            for collector in REGISTRY._collector_to_names.keys():
                if hasattr(collector, '_name') and collector._name.startswith('rag_'):
                    metrics_data[collector._name] = collector._value._value
            
            return {
                "metrics": metrics_data,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {"error": str(e)}

    def shutdown(self):
        """Graceful shutdown"""
        try:
            logger.info("Shutting down RAG service...")
            
            # Close LLM service
            if hasattr(self.llm_service, 'close'):
                self.llm_service.close()
            
            # Clear caches
            self.clear_cache()
            
            logger.info("RAG service shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")