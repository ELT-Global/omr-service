#!/bin/bash

# Start the OMRChecker API server

# Activate virtual environment
source venv/bin/activate

# Start the server with uvicorn
echo "Starting OMRChecker API server on http://localhost:8000"
echo "Swagger docs available at http://localhost:8000/docs"
echo ""

uvicorn api:app --reload --host 0.0.0.0 --port 8000
