import threading
from vectorstore import LocalRAGSystem

def start_watching(rag_system: LocalRAGSystem):
    watcher_thread = threading.Thread(target=rag_system.start_watching, daemon=True)
    watcher_thread.start()