import requests
import json
import logging
from typing import Generator, Dict, Any

from config import Config
from exceptions import LLMException

logger = logging.getLogger(__name__)

class LLMService:
    """Handles communication with Ollama LLM"""
    
    import requests

class LLMService:
    def __init__(self, base_url="http://host.docker.internal:11434"):
        self.base_url = base_url

    def query_mistral(self, prompt):
        response = requests.post(f"{self.base_url}/api/v1/query", json={"prompt": prompt})
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error querying Mistral: {response.text}")
    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def generate_response(self, prompt: str, stream: bool = False) -> str | Generator[str, None, None]:
        """Generate response from LLM"""
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
