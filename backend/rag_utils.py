import os
import logging
import requests
from urllib.parse import urljoin
from typing import List

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def generate(self, model: str, prompt: str) -> str:
        logger.info(f"Sending generate request to Ollama model '{model}'...")
        response = requests.post(
            urljoin(self.base_url, "/api/generate"),
            json={
                "model": model,
                "prompt": prompt,
                "stream": False  # Ensure this stays False if using requests
            },
        )
        response.raise_for_status()
        result = response.json()
        logger.info("Received response from Ollama.")
        return result.get("response", "").strip()

    def show_models(self) -> List[str]:
        logger.info("Fetching list of models from Ollama...")
        response = requests.get(urljoin(self.base_url, "/api/tags"))
        response.raise_for_status()
        models = response.json().get("models", [])
        return [model["name"] for model in models]





# Load model from environment variable, or default to "mistral"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")