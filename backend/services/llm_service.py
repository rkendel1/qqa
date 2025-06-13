import requests
import json
import logging
from typing import Generator, Dict, Any, Optional, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import retry, stop_after_attempt, wait_exponential
from prometheus_client import Counter, Histogram
from opentelemetry import trace

from config import settings
from exceptions import LLMException

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Metrics
llm_requests_total = Counter('llm_requests_total', 'Total number of LLM requests')
llm_request_duration = Histogram('llm_request_duration_seconds', 'LLM request duration in seconds')
llm_errors_total = Counter('llm_errors_total', 'Total number of LLM errors')

class LLMService:
    """Handles communication with Ollama LLM with improved reliability and monitoring"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self._setup_session()
    
    def _setup_session(self):
        """Setup requests session with retry strategy"""
        self.session = requests.Session()
        retry_strategy = Retry(
            total=settings.MAX_RETRIES,
            backoff_factor=settings.RETRY_BACKOFF_FACTOR,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            with tracer.start_as_current_span("check_ollama_availability"):
                response = self.session.get(
                    f"{self.base_url}/api/tags",
                    timeout=5
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama availability check failed: {e}")
            return False
    
    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def generate_response(
        self,
        prompt: str,
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Union[str, Generator[str, None, None]]:
        """Generate response from LLM with retries and monitoring"""
        if not self.is_available():
            llm_errors_total.inc()
            raise LLMException("Ollama service is not available")
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        try:
            with tracer.start_as_current_span("generate_llm_response") as span:
                span.set_attribute("model", self.model)
                span.set_attribute("stream", stream)
                
                llm_requests_total.inc()
                with llm_request_duration.time():
                    response = self.session.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                        stream=stream,
                        timeout=30
                    )
                    response.raise_for_status()
                
                if stream:
                    return self._handle_streaming_response(response)
                else:
                    return response.json().get("response", "")
                    
        except requests.RequestException as e:
            llm_errors_total.inc()
            logger.error(f"LLM request failed: {e}")
            raise LLMException(f"Failed to generate response: {e}")
    
    def _handle_streaming_response(self, response) -> Generator[str, None, None]:
        """Handle streaming response from Ollama with error handling"""
        try:
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        if "response" in data:
                            yield data["response"]
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to decode streaming response: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            raise LLMException(f"Streaming response failed: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            return next((m for m in models if m["name"] == self.model), {})
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return {}
