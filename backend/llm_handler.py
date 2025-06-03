import requests
import json

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434/api/generate"):
        self.base_url = base_url

    def generate(self, model: str, prompt: str, stream: bool = False):
        headers = {"Content-Type": "application/json"}
        data = {
            "model": model,
            "prompt": prompt,
            "stream": stream
        }

        if stream:
                response = requests.post(self.base_url, headers=headers, data=json.dumps(data), stream=True)
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode("utf-8"))
                            yield data.get("response", "")
                        except json.JSONDecodeError:
                            continue
        else:
            response = requests.post(self.base_url, headers=headers, data=json.dumps(data))
            print("OLLAMA RAW RESPONSE:", response.status_code, response.text)  # 🧪 ADD THIS

        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            return f"Ollama error: {response.status_code}"


class LocalRAGPipeline:
    def __init__(self, documents_path: str, ollama_model: str):
        from local_rag import LocalRAGSystem

        self.rag_system = LocalRAGSystem(documents_path=documents_path)
        self.ollama = OllamaClient()
        self.ollama_model = ollama_model

        # Initial document ingestion
        self.rag_system.ingest_documents()

    def query(self, query: str, use_streaming: bool = False):
        documents = self.rag_system.query(query)

        if not documents:
            return {
                "response": "No relevant documents found.",
                "sources": [],
                "num_sources": 0
            }

        context = "\n\n".join([doc.page_content for doc in documents])
        prompt = (
            f"You are a helpful assistant. Answer the question below using only the context provided.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            f"Answer:"
        )

        if use_streaming:
            response_generator = self.ollama.generate(model=self.ollama_model, prompt=prompt, stream=True)
            return {
                "response": response_generator,
                "sources": list(set([doc.metadata.get("source", "unknown") for doc in documents])),
                "num_sources": len(set([doc.metadata.get("source", "unknown") for doc in documents]))
            }
        else:
            response = self.ollama.generate(model=self.ollama_model, prompt=prompt, stream=False)
            return {
                "response": response,
                "sources": list(set([doc.metadata.get("source", "unknown") for doc in documents])),
                "num_sources": len(set([doc.metadata.get("source", "unknown") for doc in documents]))
            }