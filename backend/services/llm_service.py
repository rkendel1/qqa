import os
import requests
import json
import logging
from typing import Generator, Union

from config import Config
from exceptions import LLMException

logger = logging.getLogger(__name__)

class LLMService:
    """Handles communication with Ollama LLM, supporting local or container setup."""
    
    def __init__(self):
        use_local_ollama = os.getenv("USE_LOCAL_OLLAMA", "true").lower() == "true"
        if use_local_ollama:
            self.base_url = "http://host.docker.internal:11434"  # Local Ollama
        else:
            self.base_url = "http://ollama:11434"  # Containerized Ollama

        self.config = Config()
    
    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def generate_response(self, prompt: str, stream: bool = False) -> Union[str, Generator[str, None, None]]:
        """Generate response from Ollama LLM"""
        if not self.is_available():
            raise LLMException("Ollama service is not available")
        
        payload = {
            "model": self.config.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": stream
        }
        
        try:
            response = requests.post(
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
            logger.error(f"LLM request failed: {e}")
            raise LLMException(f"Failed to generate response: {e}")
    
    def _handle_streaming_response(self, response) -> Generator[str, None, None]:
        """Handle streaming response from Ollama"""
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode("utf-8"))
                    if "response" in data:
                        yield data["response"]
                except json.JSONDecodeError:
                    continue

    def query_mistral(self, prompt: str) -> dict:
        """Query Mistral model at /api/v1/query endpoint"""
        try:
            response = requests.post(f"{self.base_url}/api/v1/query", json={"prompt": prompt}, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Mistral query failed: {e}")
            raise LLMException(f"Failed to query Mistral: {e}")
