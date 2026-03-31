# OMR Processing Service

**A pure REST API for processing Optical Mark Recognition (OMR) sheets.**

Fast, stateless, and simple - process OMR sheets via HTTP endpoints with support for file uploads, URLs, and base64 images.

> 📖 **Documentation:**
> - Full API documentation available at `/docs` when running
> - [Contributing Guide](CONTRIBUTING.md) - How to contribute to the project

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Environment Variables](#environment-variables)

## Features

- **Stateless & Pure**: No database, no authentication, no job tracking
- **Two Simple Endpoints**: 
  - `/process-sheet` - Process a single OMR sheet
  - `/process-batch` - Process up to 20 sheets synchronously
- **Flexible Input**: Upload files, URLs, or base64 encoded images
- **Custom Templates**: Optional custom config and template JSON

## Quick Start

### Installation

```bash
# Install all dependencies
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Running the Server

```bash
# Start the API server
python api.py

# Or use uvicorn directly
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# Or use the bash script (Linux/Mac)
./start_api.sh
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### 1. Process Single Sheet

**POST** `/process-sheet`

Process a single OMR sheet and get results immediately.

**Parameters:**
- `sheet_id` (form): Unique identifier for the sheet
- `image` (file): OMR sheet image file
- `image_url` (form): URL to download the image
- `image_base64` (form): Base64 encoded image data
- `config_json` (form): Optional custom config JSON string
- `template_json` (form): Optional custom template JSON string

**Note:** Provide exactly one of: `image`, `image_url`, or `image_base64`

**Example using curl:**

```bash
# Upload a file
curl -X POST "http://localhost:8000/process-sheet" \
  -F "sheet_id=student_001" \
  -F "image=@path/to/sheet.jpg"

# Or use a URL
curl -X POST "http://localhost:8000/process-sheet" \
  -F "sheet_id=student_001" \
  -F "image_url=https://example.com/sheet.jpg"

# Or use base64
curl -X POST "http://localhost:8000/process-sheet" \
  -F "sheet_id=student_001" \
  -F "image_base64=iVBORw0KGgoAAAANSUhEUg..."
```

**Response:**

```json
{
  "id": "student_001",
  "answers": {
    "q1": "A",
    "q2": "B",
    "q3": "C"
  },
  "multi_marked_count": 0,
  "error": null
}
```

### 2. Process Batch

**POST** `/process-batch`

Process multiple OMR sheets synchronously (up to 20 sheets). You can mix URLs and base64 images in the same batch.

**Request Body:**

```json
{
  "sheets": [
    {
      "id": "student_001",
      "image_url": "https://example.com/sheet1.jpg"
    },
    {
      "id": "student_002",
      "image_base64": "iVBORw0KGgoAAAANSUhEUg..."
    }
  ],
  "config_json": null,
  "template_json": null
}
```

**Note:** Each sheet must have either `image_url` or `image_base64`, but not both. You can mix different types in the same batch.

**Example using curl:**

```bash
# Mix URLs and base64 in the same batch
curl -X POST "http://localhost:8000/process-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "sheets": [
      {"id": "student_001", "image_url": "https://example.com/sheet1.jpg"},
      {"id": "student_002", "image_base64": "iVBORw0KGgoAAAANSUhEUg..."}
    ]
  }'

# Or all URLs
curl -X POST "http://localhost:8000/process-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "sheets": [
      {"id": "student_001", "image_url": "https://example.com/sheet1.jpg"},
      {"id": "student_002", "image_url": "https://example.com/sheet2.jpg"}
    ]
  }'
```

**Response:**

```json
{
  "total": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "id": "student_001",
      "answers": {"q1": "A", "q2": "B"},
      "multi_marked_count": 0,
      "error": null
    },
    {
      "id": "student_002",
      "answers": {"q1": "C", "q2": "D"},
      "multi_marked_count": 1,
      "error": null
    }
  ]
}
```

## Configuration

### Default Configuration

By default, the API uses the configuration from `samples/sample1/`. You can override this by setting the environment variable:

```bash
export OMR_DEFAULT_CONFIG_DIR=/path/to/your/config
```

### Custom Configuration Per Request

You can provide custom `config.json` and `template.json` for each request:

```bash
curl -X POST "http://localhost:8000/process-sheet" \
  -F "sheet_id=student_001" \
  -F "image=@sheet.jpg" \
  -F 'config_json={"some_config": "value"}' \
  -F 'template_json={"some_template": "value"}'
```

## Project Structure

```
omr-service/
├── api.py                 # Main API server
├── pyproject.toml         # Project configuration and dependencies
├── src/
│   ├── api_utils.py       # API utility functions
│   ├── core.py            # Core OMR processing logic
│   ├── evaluation.py      # Evaluation logic
│   ├── template.py        # Template handling
│   ├── logger.py          # Logging configuration
│   ├── constants/         # Constants and configs
│   ├── defaults/          # Default configurations
│   ├── processors/        # Image processors
│   ├── schemas/           # JSON schemas
│   ├── utils/             # Utility functions
│   └── tests/             # Unit tests
├── tests/                 # API integration tests
│   ├── test_api.py
│   ├── test_api_simple.py
│   ├── test_api_complete.py
│   └── test_api_base64.py
├── docs/                  # Documentation
│   ├── BASE64_SUPPORT.md
│   ├── QUICKSTART.md
│   └── SIMPLIFICATION_SUMMARY.md
└── samples/               # Sample configurations and templates
```

## Testing

Test the API endpoints:

```bash
# Run all tests
pytest

# Or run specific test files
python tests/test_api_simple.py
python tests/test_api_complete.py
python tests/test_api_base64.py
```

## Environment Variables

- `OMR_DEFAULT_CONFIG_DIR`: Path to default configuration directory (default: `samples/sample1`)

## License

See LICENSE file for details.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Support

- **Documentation**: Check the [docs/](docs/) directory
- **Issues**: Open an issue on GitHub
- **Questions**: See [docs/QUICKSTART.md](docs/QUICKSTART.md) for common questions

## Credits

Based on OMRChecker by Udayraj Deshmukh

---

**Project Status**: Active and maintained  
**Latest Version**: 2.0.0  
**API Documentation**: http://localhost:8000/docs (when running)
