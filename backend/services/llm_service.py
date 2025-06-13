import requests
import json
import logging
import time
from typing import Generator, Dict, Any, Optional, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import retry, stop_after_attempt, wait_exponential
from prometheus_client import Counter, Histogram
from opentelemetry import trace
from contextlib import contextmanager

from config import settings
from exceptions import LLMException

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Metrics
llm_requests_total = Counter('llm_requests_total', 'Total number of LLM requests')
llm_request_duration = Histogram('llm_request_duration_seconds', 'LLM request duration in seconds')
llm_errors_total = Counter('llm_errors_total', 'Total number of LLM errors')
llm_stream_errors_total = Counter('llm_stream_errors_total', 'Total number of streaming decode errors')

class LLMService:
    """Handles communication with Ollama LLM with improved reliability and monitoring"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = getattr(settings, 'LLM_TIMEOUT', 30)
        self.max_prompt_length = getattr(settings, 'MAX_PROMPT_LENGTH', 32000)
        self.session_refresh_interval = getattr(settings, 'SESSION_REFRESH_INTERVAL', 3600)  # 1 hour
        self._last_session_refresh = time.time()
        self._setup_session()
    
    def _setup_session(self):
        """Setup requests session with retry strategy and connection pooling"""
        self.session = requests.Session()
        retry_strategy = Retry(
            total=settings.MAX_RETRIES,
            backoff_factor=getattr(settings, 'RETRY_BACKOFF_FACTOR', 1),
            status_forcelist=[500, 502, 503, 504, 429]  # Added 429 for rate limiting
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=getattr(settings, 'HTTP_POOL_CONNECTIONS', 10),
            pool_maxsize=getattr(settings, 'HTTP_POOL_MAXSIZE', 20)
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': f'QQA-RAG-Service/{getattr(settings, "VERSION", "1.0")}'
        })
        
        self._last_session_refresh = time.time()
        logger.info("HTTP session initialized with connection pooling")
    
    def _refresh_session_if_needed(self):
        """Refresh session periodically to avoid stale connections"""
        if time.time() - self._last_session_refresh > self.session_refresh_interval:
            logger.info("Refreshing HTTP session")
            self.session.close()
            self._setup_session()
    
    def _validate_parameters(
        self, 
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None
    ):
        """Validate input parameters"""
        if not prompt or not isinstance(prompt, str):
            raise ValueError("Prompt must be a non-empty string")
        
        if len(prompt) > self.max_prompt_length:
            raise ValueError(f"Prompt length ({len(prompt)}) exceeds maximum ({self.max_prompt_length})")
        
        if temperature is not None:
            if not isinstance(temperature, (int, float)) or not 0.0 <= temperature <= 2.0:
                raise ValueError("Temperature must be a number between 0.0 and 2.0")
        
        if max_tokens is not None:
            if not isinstance(max_tokens, int) or max_tokens <= 0:
                raise ValueError("max_tokens must be a positive integer")
        
        if top_p is not None:
            if not isinstance(top_p, (int, float)) or not 0.0 <= top_p <= 1.0:
                raise ValueError("top_p must be a number between 0.0 and 1.0")
        
        if top_k is not None:
            if not isinstance(top_k, int) or top_k <= 0:
                raise ValueError("top_k must be a positive integer")
    
    def is_available(self) -> bool:
        """Check if Ollama is available with better error handling"""
        try:
            with tracer.start_as_current_span("check_ollama_availability"):
                self._refresh_session_if_needed()
                response = self.session.get(
                    f"{self.base_url}/api/tags",
                    timeout=5
                )
                if response.status_code == 200:
                    # Additional check: verify our model is available
                    models = response.json().get("models", [])
                    model_names = [model.get("name", "") for model in models]
                    return self.model in model_names
                return False
        except requests.exceptions.Timeout:
            logger.warning("Ollama availability check timed out")
            return False
        except requests.exceptions.ConnectionError:
            logger.warning("Cannot connect to Ollama service")
            return False
        except Exception as e:
            logger.error(f"Ollama availability check failed: {e}")
            return False
    
    @contextmanager
    def _managed_response(self, response):
        """Context manager for proper response cleanup"""
        try:
            yield response
        finally:
            if hasattr(response, 'close'):
                response.close()
    
    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def generate_response(
        self,
        prompt: str,
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        system_prompt: Optional[str] = None
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response from LLM with comprehensive validation and monitoring"""
        
        # Validate inputs
        self._validate_parameters(prompt, temperature, max_tokens, top_p, top_k)
        
        if not self.is_available():
            llm_errors_total.inc()
            raise LLMException("Ollama service is not available or model not found")
        
        # Build payload with all supported parameters
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {}
        }
        
        # Add optional parameters to options
        if temperature is not None:
            payload["options"]["temperature"] = temperature
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens  # Ollama uses num_predict
        if top_p is not None:
            payload["options"]["top_p"] = top_p
        if top_k is not None:
            payload["options"]["top_k"] = top_k
        
        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            with tracer.start_as_current_span("generate_llm_response") as span:
                span.set_attribute("model", self.model)
                span.set_attribute("stream", stream)
                span.set_attribute("prompt_length", len(prompt))
                if temperature is not None:
                    span.set_attribute("temperature", temperature)
                
                self._refresh_session_if_needed()
                llm_requests_total.inc()
                
                with llm_request_duration.time():
                    response = self.session.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                        stream=stream,
                        timeout=self.timeout
                    )
                    response.raise_for_status()
                
                if stream:
                    return self._handle_streaming_response(response)
                else:
                    with self._managed_response(response):
                        result = response.json()
                        return result.get("response", "")
                        
        except requests.exceptions.Timeout as e:
            llm_errors_total.inc()
            logger.error(f"LLM request timed out after {self.timeout}s: {e}")
            raise LLMException(f"Request timed out after {self.timeout} seconds")
        except requests.exceptions.ConnectionError as e:
            llm_errors_total.inc()
            logger.error(f"LLM connection error: {e}")
            raise LLMException("Failed to connect to Ollama service")
        except requests.exceptions.HTTPError as e:
            llm_errors_total.inc()
            logger.error(f"LLM HTTP error: {e}")
            if e.response.status_code == 404:
                raise LLMException(f"Model '{self.model}' not found")
            elif e.response.status_code == 429:
                raise LLMException("Rate limit exceeded, please try again later")
            else:
                raise LLMException(f"HTTP error {e.response.status_code}: {e}")
        except json.JSONDecodeError as e:
            llm_errors_total.inc()
            logger.error(f"Failed to decode LLM response: {e}")
            raise LLMException("Invalid response format from LLM service")
        except Exception as e:
            llm_errors_total.inc()
            logger.error(f"Unexpected LLM error: {e}")
            raise LLMException(f"Unexpected error: {e}")
    
    def _handle_streaming_response(self, response) -> Generator[str, None, None]:
        """Handle streaming response from Ollama with improved error handling and monitoring"""
        decode_errors = 0
        max_decode_errors = 5  # Allow some decode errors before giving up
        
        try:
            with self._managed_response(response):
                for line in response.iter_lines(decode_unicode=True):
                    if line:
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                            # Check if stream is done
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError as e:
                            decode_errors += 1
                            llm_stream_errors_total.inc()
                            logger.warning(f"Failed to decode streaming response line: {e}")
                            
                            if decode_errors >= max_decode_errors:
                                logger.error(f"Too many decode errors ({decode_errors}), stopping stream")
                                raise LLMException("Too many streaming decode errors")
                            continue
        except requests.exceptions.ChunkedEncodingError as e:
            logger.error(f"Chunked encoding error in streaming response: {e}")
            raise LLMException("Streaming connection interrupted")
        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            raise LLMException(f"Streaming response failed: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get comprehensive information about the current model"""
        try:
            with tracer.start_as_current_span("get_model_info"):
                self._refresh_session_if_needed()
                response = self.session.get(
                    f"{self.base_url}/api/tags",
                    timeout=10
                )
                response.raise_for_status()
                
                models = response.json().get("models", [])
                model_info = next((m for m in models if m["name"] == self.model), {})
                
                if model_info:
                    # Add additional runtime info
                    model_info["configured_model"] = self.model
                    model_info["base_url"] = self.base_url
                    model_info["timeout"] = self.timeout
                    model_info["max_prompt_length"] = self.max_prompt_length
                
                return model_info
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get model info: {e}")
            return {"error": f"Failed to retrieve model info: {e}"}
        except Exception as e:
            logger.error(f"Unexpected error getting model info: {e}")
            return {"error": f"Unexpected error: {e}"}
    
    def get_available_models(self) -> List[str]:
        """Get list of all available models"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=10
            )
            response.raise_for_status()
            models = response.json().get("models", [])
            return [model.get("name", "") for model in models if model.get("name")]
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        health_status = {
            "service": "LLMService",
            "timestamp": time.time(),
            "ollama_available": False,
            "model_available": False,
            "configured_model": self.model,
            "base_url": self.base_url,
            "timeout": self.timeout
        }
        
        try:
            # Check if Ollama is running
            ollama_available = self.is_available()
            health_status["ollama_available"] = ollama_available
            
            if ollama_available:
                # Check if our specific model is available
                available_models = self.get_available_models()
                health_status["model_available"] = self.model in available_models
                health_status["available_models"] = available_models
            
            # Determine overall health
            health_status["healthy"] = health_status["ollama_available"] and health_status["model_available"]
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["error"] = str(e)
            health_status["healthy"] = False
        
        return health_status
    
    def close(self):
        """Clean up resources"""
        if hasattr(self, 'session'):
            self.session.close()
            logger.info("LLM service session closed")