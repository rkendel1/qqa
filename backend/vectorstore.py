import os
import json
import time
from typing import List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader, PyPDFLoader, UnstructuredMarkdownLoader
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.schema import Document

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}

class LocalRAGSystem:
    def __init__(self, 
                 documents_path: str = "/Users/randy/Desktop/Dev/civic-nexus-chat/backend/documents",
                 persist_directory: str = "/Users/randy/Desktop/Dev/civic-nexus-chat/chroma_db",
                 metadata_file: str = "ingested_files.json"):
        
        self.documents_path = documents_path
        self.persist_directory = persist_directory
        self.metadata_file = metadata_file

        self.embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self.embedding_function = HuggingFaceEmbeddings(model_name=self.embedding_model_name)
        self.vectorstore = None
        self.ingested_files = set()

        self._load_metadata()
        self._initialize_vectorstore()

    def _load_metadata(self):
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, "r") as f:
                self.ingested_files = set(json.load(f))
        else:
            self.ingested_files = set()

    def _save_metadata(self):
        with open(self.metadata_file, "w") as f:
            json.dump(list(self.ingested_files), f)

    def _initialize_vectorstore(self):
        try:
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embedding_function
            )
            print("🧠 Vectorstore initialized or loaded from:", self.persist_directory)
        except Exception as e:
            print(f"❌ Failed to initialize vectorstore: {e}")
            self.vectorstore = None
            
        else:
            print("📂 No existing vectorstore found. Creating one...")
            os.makedirs(self.persist_directory, exist_ok=True)
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embedding_function
            )

    def _process_and_add_file(self, filepath: str):
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()

        if ext not in SUPPORTED_EXTENSIONS:
            print(f"⏭️ Skipping unsupported file: {filename}")
            return

        if filename in self.ingested_files:
            print(f"🛑 Already ingested: {filename}")
            return

        loader_cls = {
            ".txt": TextLoader,
            ".pdf": PyPDFLoader,
            ".md": UnstructuredMarkdownLoader
        }.get(ext)

        try:
            loader = loader_cls(filepath)
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = filename

            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
            chunks = splitter.split_documents(docs)
            
            print(f"📚 Loaded {len(docs)} raw documents from {filename}")
            print(f"🔪 Split into {len(chunks)} chunks")

            self.vectorstore.add_documents(chunks)
            self.vectorstore.persist()

            self.ingested_files.add(filename)
            self._save_metadata()

            print(f"✅ Ingested '{filename}' with {len(chunks)} chunks.")

        except Exception as e:
            print(f"⚠️ Failed to process {filename}: {e}")

    def retrieve_documents(self, query: str, k: int = 5) -> List[Document]:
        if not self.vectorstore:
            print("❌ Vectorstore not initialized.")
            return []
        return self.vectorstore.similarity_search(query, k=k)

    def start_watching(self):
        print("👀 Watching for new files in:", self.documents_path)
        event_handler = NewFileHandler(self)
        observer = Observer()
        observer.schedule(event_handler, self.documents_path, recursive=False)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            print("\n🛑 Stopped watching.")
        observer.join()

class NewFileHandler(FileSystemEventHandler):
    def __init__(self, rag_system: LocalRAGSystem):
        super().__init__()
        self.rag_system = rag_system

    def on_created(self, event):
        if not event.is_directory:
            filepath = event.src_path
            print(f"📄 Detected new file: {filepath}")
            time.sleep(0.5)  # ensure file is fully written
            self.rag_system._process_and_add_file(filepath)