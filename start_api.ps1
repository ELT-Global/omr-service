# Start the OMRChecker API server

# Check if virtual environment exists
if (-not (Test-Path "venv\Scripts\uvicorn.exe")) {
    Write-Host "Error: Virtual environment not found or uvicorn not installed!"
    Write-Host "Please create it first with: py -m venv venv"
    Write-Host "Then install dependencies with: .\venv\Scripts\pip.exe install -r requirements.txt -r requirements.api.txt"
    exit 1
}

# Start the server with uvicorn (using direct path to avoid activation issues)
Write-Host "Starting OMRChecker API server on http://localhost:8000" -ForegroundColor Green
Write-Host "Swagger docs available at http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""

& ".\venv\Scripts\uvicorn.exe" api:app --reload --host 0.0.0.0 --port 8000
