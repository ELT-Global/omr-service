"""
FastAPI server for OMRChecker

This module provides RESTful API endpoints to process OMR sheets.
"""
import os
import tempfile
import json
import httpx
from pathlib import Path
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api_utils import process_single_omr_image
from src.api.auth import get_current_operator
from src.database.models import Operator
from src.database import db_connection, DatabaseSchema
from src.logger import logger
from src.services.parsing_job_service import ParsingJobService
from src.workers.background_processor import get_background_processor

# Initialize FastAPI app
app = FastAPI(
    title="OMRChecker API",
    description="""
API for processing Optical Mark Recognition (OMR) sheets.

## Authentication

All endpoints (except /health and /) require HTTP Basic Authentication.

### Using Swagger UI:
1. Click the **"Authorize" 🔓** button at the top right
2. **Username**: Enter anything (e.g., "api" or "user") - this field is ignored
3. **Password**: Enter your operator UUID (e.g., "test-uuid")
4. Click **"Authorize"** and then **"Close"**
5. Now all your API requests will include the authentication automatically!

### Using curl:
```bash
# Option 1: Using -u flag (recommended)
curl -u "api:test-uuid" \\
  -X POST "http://localhost:8000/omr:parse-sheet" \\
  -F "userId=student_001" \\
  -F "image=@sheet.jpg"

# Option 2: Manual Authorization header
curl -X POST "http://localhost:8000/omr:parse-sheet" \\
  -H "Authorization: Basic $(echo -n 'api:test-uuid' | base64)" \\
  -F "userId=student_001" \\
  -F "image=@sheet.jpg"
```

### Using Python requests:
```python
import requests

response = requests.post(
    "http://localhost:8000/omr:parse-sheet",
    auth=("api", "test-uuid"),  # (username, password/UUID)
    data={"userId": "student_001"},
    files={"image": open("sheet.jpg", "rb")}
)
print(response.json())
```

### Using JavaScript/fetch:
```javascript
const auth = btoa('api:test-uuid'); // Base64 encode
fetch('http://localhost:8000/omr:parse-sheet', {
  method: 'POST',
  headers: {
    'Authorization': `Basic ${auth}`
  },
  body: formData
});
```

**Note**: Contact your administrator to obtain an operator UUID.
    """,
    version="1.0.0",
)


# Database initialization on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup"""
    logger.info("Initializing database...")
    try:
        conn = db_connection.get_connection()
        DatabaseSchema.initialize_database(conn)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


# Response models
class OMRResponse(BaseModel):
    """Response model for OMR processing"""
    id: str
    answers: dict
    multi_marked_count: int


class SheetItem(BaseModel):
    """Model for individual sheet in parse-sheets request"""
    id: str = Field(..., description="Unique identifier for the sheet")
    image_url: str = Field(..., description="URL of the OMR sheet image")


class ParseSheetsRequest(BaseModel):
    """Request model for bulk OMR parsing"""
    items: List[SheetItem] = Field(..., description="Array of sheets to process", min_items=1)
    config_json: Optional[str] = Field(None, description="Optional: Custom config.json content as JSON string. If not provided, uses default config.")
    template_json: Optional[str] = Field(None, description="Optional: Custom template.json content as JSON string. If not provided, uses default template.")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {"id": "student_001", "image_url": "https://example.com/sheet1.jpg"},
                    {"id": "student_002", "image_url": "https://example.com/sheet2.jpg"}
                ],
                "config_json": {"some_config_key": "some_value"},
                "template_json": {"some_template_key": "some_value"}
            }
        }


class BulkOMRItem(BaseModel):
    """Model for bulk OMR processing item"""
    id: str
    image_url: Optional[str] = None
    error: Optional[str] = None
    answers: Optional[dict] = None
    multi_marked_count: Optional[int] = None


class BulkOMRResponse(BaseModel):
    """Response model for bulk OMR processing"""
    total: int
    successful: int
    failed: int
    results: List[BulkOMRItem]


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None


class JobResponse(BaseModel):
    """Response model for job creation"""
    jobId: str
    status: str


class SheetStatusResponse(BaseModel):
    """Model for sheet status in job details"""
    id: str
    image_url: str
    status: str
    answers: Optional[dict] = None
    error: Optional[str] = None


class JobDetailsResponse(BaseModel):
    """Response model for job details"""
    jobId: str
    status: str
    totalSheets: int
    processedSheets: int
    successfulSheets: int
    failedSheets: int
    pendingSheets: int
    callbackStatus: str
    createdAt: str
    completedAt: Optional[str] = None
    sheets: Optional[List[SheetStatusResponse]] = None


# Default configuration directory (can be overridden via environment variable)
DEFAULT_CONFIG_DIR = Path(os.getenv(
    "OMR_DEFAULT_CONFIG_DIR",
    str(Path(__file__).parent / "samples" / "sample1")
))


# Helper functions
async def download_image_from_url(url: str) -> str:
    """
    Download an image from a URL and save it temporarily.
    
    Args:
        url: The URL of the image to download
        
    Returns:
        str: Path to the temporary file
        
    Raises:
        HTTPException: If download fails
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Determine file extension from URL or content-type
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'png' in content_type:
                ext = '.png'
            else:
                ext = '.jpg'  # default
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                temp_file.write(response.content)
                return temp_file.name
                
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download image from URL: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading image: {str(e)}"
        )


async def save_config_files(config_json: Optional[str], template_json: Optional[str]) -> Optional[str]:
    """
    Save custom config and template JSON to a temporary directory.
    
    Args:
        config_json: JSON string for config.json
        template_json: JSON string for template.json
        
    Returns:
        Optional[str]: Path to temporary directory with config files, or None if no custom config
    """
    if not config_json and not template_json:
        return None
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        if config_json:
            config_path = Path(temp_dir) / "config.json"
            config_data = json.loads(config_json)
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
        
        if template_json:
            template_path = Path(temp_dir) / "template.json"
            template_data = json.loads(template_json)
            with open(template_path, 'w') as f:
                json.dump(template_data, f, indent=2)
        
        return temp_dir
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON in config or template: {str(e)}"
        )


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API health check"""
    return {
        "message": "OMRChecker API is running",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.post(
    "/omr:parse-sheet",
    response_model=OMRResponse,
    tags=["OMR Processing"],
    summary="Parse OMR Sheet",
    description="Upload an OMR sheet image or provide a URL, and get the detected answers in JSON format. Requires authentication."
)
async def parse_omr(
    userId: str = Form(..., description="Unique identifier for the sheet"),
    operator: Operator = Depends(get_current_operator),
    image: Optional[UploadFile] = File(None, description="OMR sheet image file (JPG, PNG, etc.)"),
    image_url: Optional[str] = Form(None, description="URL of the OMR sheet image (alternative to file upload)"),
    config_json: Optional[str] = Form(None, description="Optional: Custom config.json content as JSON string. If not provided, uses default config."),
    template_json: Optional[str] = Form(None, description="Optional: Custom template.json content as JSON string. If not provided, uses default template.")
):
    """
    Parse an OMR sheet and return detected answers.
    
    **Authentication Required**: Include Authorization header with Basic <operator_uuid>
    
    - **userId**: Unique identifier for this sheet (returned in response)
    - **image**: The OMR sheet image file to process (either this or image_url required)
    - **image_url**: URL to download the OMR sheet image (either this or image required)
    - **config_json**: OPTIONAL - Custom config.json as JSON string. If omitted, uses default config.
    - **template_json**: OPTIONAL - Custom template.json as JSON string. If omitted, uses default template.
    
    Note: config_json and template_json are optional. When not provided, the API uses a default
    configuration from the samples directory (configurable via OMR_DEFAULT_CONFIG_DIR environment variable).
    
    Returns the detected answers as a JSON object.
    """
    
    # Operator is now available for future use (e.g., saving to database)
    logger.info(f"Processing OMR for operator_id: {operator.id}, userId: {userId}")
    
    # Validate that either image or image_url is provided
    if not image and not image_url:
        raise HTTPException(
            status_code=400,
            detail="Either 'image' file or 'image_url' must be provided"
        )
    
    if image and image_url:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'image' file or 'image_url', not both"
        )
    
    # Validate file type if image is provided
    if image and hasattr(image, 'content_type') and not image.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {image.content_type}. Please upload an image file."
        )
    
    temp_image_path = None
    custom_config_dir = None
    
    try:
        # Get image (either from upload or URL)
        if image:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(image.filename).suffix) as temp_file:
                content = await image.read()
                temp_file.write(content)
                temp_image_path = temp_file.name
        else:
            # Download from URL
            temp_image_path = await download_image_from_url(image_url)
        
        # logger.info removed from here - moved to top with operator context
        
        # Save custom config files if provided
        custom_config_dir = await save_config_files(config_json, template_json)
        
        # Determine which config directory to use
        config_dir = custom_config_dir if custom_config_dir else str(DEFAULT_CONFIG_DIR)
        
        # Process the OMR image
        result = process_single_omr_image(
            image_path=temp_image_path,
            config_dir=config_dir
        )
        
        logger.info(f"Successfully processed OMR for operator_id: {operator.id}, userId: {userId}")
        
        return OMRResponse(
            id=userId,
            answers=result["response"],
            multi_marked_count=result["multi_marked_count"]
        )
        
    except Exception as e:
        logger.error(f"Error processing OMR for operator_id: {operator.id}, userId {userId}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing OMR image: {str(e)}"
        )
    
    finally:
        # Clean up temporary files
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.unlink(temp_image_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary image file: {e}")
        
        if custom_config_dir and os.path.exists(custom_config_dir):
            try:
                import shutil
                shutil.rmtree(custom_config_dir)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {e}")


@app.post(
    "/omr:parse-sheets",
    response_model=JobResponse,
    tags=["OMR Processing"],
    summary="Parse Multiple OMR Sheets (Async)",
    description="Process multiple OMR sheets asynchronously. Creates a parsing job and returns immediately. Use /jobs/{jobId} to check status. Requires authentication."
)
async def parse_omr_bulk(
    background_tasks: BackgroundTasks,
    request: ParseSheetsRequest,
    operator: Operator = Depends(get_current_operator)
):
    """
    Parse multiple OMR sheets asynchronously.
    
    **Authentication Required**: Include Authorization header with Basic <operator_uuid>
    
    **Request Body**: JSON object with the following fields:
    - **items**: Array of sheet objects, each containing:
      - **id**: Unique identifier for the sheet (required)
      - **image_url**: URL of the OMR sheet image (required)
    - **config_json**: OPTIONAL - Custom config.json as JSON string (applies to all sheets). If omitted, uses default config.
    - **template_json**: OPTIONAL - Custom template.json as JSON string (applies to all sheets). If omitted, uses default template.
    
    **Example Request Body**:
    ```json
    {
      "items": [
        {"id": "student_001", "image_url": "https://example.com/sheet1.jpg"},
        {"id": "student_002", "image_url": "https://example.com/sheet2.jpg"}
      ],
      "config_json": null,
      "template_json": null
    }
    ```
    
    Returns a job ID immediately. The job will be processed in the background.
    Check job status using GET /jobs/{jobId}.
    A webhook will be sent to your registered webhook_url upon completion.
    """
    
    custom_config_dir = None
    
    try:
        # Extract validated data from request
        items_data = [item.dict() for item in request.items]
        
        logger.info(f"Creating parsing job for operator_id: {operator.id} with {len(items_data)} sheets")
        
        # Save custom config files if provided
        custom_config_dir = await save_config_files(request.config_json, request.template_json)
        config_dir = custom_config_dir if custom_config_dir else str(DEFAULT_CONFIG_DIR)
        
        # Create parsing job with all sheets in database
        job_service = ParsingJobService()
        job = job_service.create_job(
            operator_id=operator.id,
            items=items_data,
            config_dir=config_dir
        )
        
        # Submit job to background processor
        background_processor = get_background_processor()
        background_tasks.add_task(
            background_processor.process_job,
            job.id,
            config_dir
        )
        
        logger.info(f"Parsing job {job.id} created and submitted for background processing")
        
        return JobResponse(
            jobId=job.id,
            status=job.status.value
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating parsing job: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating parsing job: {str(e)}"
        )
    
    finally:
        # Note: We can't clean up custom_config_dir here because background task needs it
        # Background processor will need to handle cleanup or we keep it until job completes
        pass


@app.get(
    "/jobs/{job_id}",
    response_model=JobDetailsResponse,
    tags=["Job Management"],
    summary="Get Job Status",
    description="Retrieve detailed status and results of a parsing job. Requires authentication."
)
async def get_job_status(
    job_id: str,
    operator: Operator = Depends(get_current_operator),
    include_sheets: bool = False
):
    """
    Get parsing job status and details.
    
    **Authentication Required**: Include Authorization header with Basic <operator_uuid>
    
    - **job_id**: The job identifier returned from /omr:parse-sheets
    - **include_sheets**: Whether to include detailed sheet results (default: False)
    
    Returns job status, progress, and optionally detailed sheet results.
    """
    job_service = ParsingJobService()
    
    # Get job
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    # Verify job belongs to operator
    if job.operator_id != operator.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Job belongs to different operator"
        )
    
    # Get sheets
    sheets = job_service.get_job_sheets(job_id)
    
    # Calculate statistics
    from src.database.models import SheetStatus
    successful = sum(1 for s in sheets if s.status == SheetStatus.PARSED)
    failed = sum(1 for s in sheets if s.status == SheetStatus.FAILED)
    pending = sum(1 for s in sheets if s.status == SheetStatus.PENDING)
    
    # Prepare response
    response = JobDetailsResponse(
        jobId=job.id,
        status=job.status.value,
        totalSheets=job.total_sheets,
        processedSheets=job.processed_sheets,
        successfulSheets=successful,
        failedSheets=failed,
        pendingSheets=pending,
        callbackStatus=job.callback_status.value,
        createdAt=job.created_at.isoformat(),
        completedAt=job.completed_at.isoformat() if job.completed_at else None
    )
    
    # Include sheet details if requested
    if include_sheets:
        sheet_responses = []
        for sheet in sheets:
            sheet_data = SheetStatusResponse(
                id=sheet.id,
                image_url=sheet.image_url,
                status=sheet.status.value
            )
            
            if sheet.status == SheetStatus.PARSED and sheet.answered_options_json:
                # Extract answers from stored data
                data = sheet.answered_options_json
                if isinstance(data, dict) and 'answers' in data:
                    sheet_data.answers = data['answers']
                else:
                    sheet_data.answers = data
            elif sheet.status == SheetStatus.FAILED:
                sheet_data.error = sheet.error_message
            
            sheet_responses.append(sheet_data)
        
        response.sheets = sheet_responses
    
    return response


@app.get(
    "/jobs",
    tags=["Job Management"],
    summary="List Jobs",
    description="List all parsing jobs for the authenticated operator. Requires authentication."
)
async def list_jobs(
    operator: Operator = Depends(get_current_operator),
    limit: int = 50,
    status: Optional[str] = None
):
    """
    List parsing jobs for the operator.
    
    **Authentication Required**: Include Authorization header with Basic <operator_uuid>
    
    - **limit**: Maximum number of jobs to return (default: 50, max: 200)
    - **status**: Filter by status (PENDING, PROCESSING, COMPLETED, FAILED)
    
    Returns a list of jobs with summary information.
    """
    if limit > 200:
        limit = 200
    
    job_service = ParsingJobService()
    
    # Get all jobs for operator
    jobs = job_service.uow.parsing_jobs.find_by_operator(operator.id)
    
    # Filter by status if provided
    if status:
        from src.database.models import JobStatus
        try:
            status_enum = JobStatus(status.upper())
            jobs = [j for j in jobs if j.status == status_enum]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Must be one of: PENDING, PROCESSING, COMPLETED, FAILED"
            )
    
    # Apply limit
    jobs = jobs[:limit]
    
    # Format response
    job_list = []
    for job in jobs:
        job_list.append({
            'jobId': job.id,
            'status': job.status.value,
            'totalSheets': job.total_sheets,
            'processedSheets': job.processed_sheets,
            'callbackStatus': job.callback_status.value,
            'createdAt': job.created_at.isoformat(),
            'completedAt': job.completed_at.isoformat() if job.completed_at else None
        })
    
    return {
        'total': len(job_list),
        'jobs': job_list
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


def main():
    """Run the FastAPI server"""
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
