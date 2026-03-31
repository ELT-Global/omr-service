FROM ubuntu:noble

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    MPLBACKEND=Agg

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    gcc \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender1 \
    libglib2.0-0 \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3 -m venv --copies /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt requirements.api.txt ./
RUN . /opt/venv/bin/activate && pip install -r requirements.txt -r requirements.api.txt

# Copy application code
COPY . .

# Expose port if needed (adjust as necessary)
EXPOSE 8000

# Run the API application using the virtual environment
CMD ["/opt/venv/bin/uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
