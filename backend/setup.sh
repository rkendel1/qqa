#!/bin/bash
# setup.sh
echo "🚀 Setting up Local RAG with Ollama Mistral..."
# Create directories
mkdir -p documents
mkdir -p chroma_db
# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install langchain langchain-community chromadb sentence-transformers pypdf python-docx requests
# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found. Installing..."
    curl https://ollama.ai/install.sh | sh
fi
# Pull Mistral model
echo "🤖 Pulling Mistral model..."
ollama pull mistral
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Add your documents to ./documents/ folder"
echo "2. Start Ollama: ollama serve"
echo "3. Run the system: python main.py"
