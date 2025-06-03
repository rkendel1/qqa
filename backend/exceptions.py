class RAGException(Exception):
    """Base exception for RAG operations"""
    pass

class VectorStoreException(RAGException):
    """Exception for vector store operations"""
    pass

class DocumentProcessingException(RAGException):
    """Exception for document processing"""
    pass

class LLMException(RAGException):
    """Exception for LLM operations"""
    pass