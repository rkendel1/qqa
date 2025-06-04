# Makefile for Civic Nexus RAG backend

.PHONY: api cli

# Start backend API server with hot reload
api:
	python start.py api

# Start CLI interface
cli:
	python start.py cli

# Run tests (if you have tests configured)
test:
	pytest

# Install dependencies (adjust as needed)
install:
	pip install -r requirements.txt

# Lint your code (optional)
lint:
	flake8 .

# Format your code (optional)
format:
	black .