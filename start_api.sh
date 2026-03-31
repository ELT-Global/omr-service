#!/bin/bash

# Start the OMRChecker API server

# Headless display settings (no monitor required)
export DISPLAY=:99
export QT_QPA_PLATFORM=offscreen
export MPLBACKEND=Agg
export OPENCV_IO_ENABLE_OPENEXR=0

# Activate virtual environment
source venv/bin/activate

# Start the server with uvicorn
echo "Starting OMRChecker API server on http://localhost:8000"
echo "Swagger docs available at http://localhost:8000/docs"
echo ""

uvicorn api:app --reload --host 0.0.0.0 --port 8000
