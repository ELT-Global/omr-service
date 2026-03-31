"""
Simplified OMR Processing API - Stateless & Pure

A minimal REST API providing two endpoints:
1. /process-sheet - Process a single OMR sheet
2. /process-batch - Process up to 20 OMR sheets synchronously

No authentication, no database, no job tracking - just pure OMR processing.
"""
import os
import tempfile
import json
import base64
import binascii
import asyncio
from pathlib import Path
from typing import Optional, List

import httpx
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from src.api_utils import process_single_omr_image
from src.logger import logger


# Initialize FastAPI app
app = FastAPI(
    title="OMR Processing API",
    description="""
Simple, stateless API for processing Optical Mark Recognition (OMR) sheets.

## Endpoints

- **POST /process-sheet**: Process a single OMR sheet
- **POST /process-batch**: Process up to 20 OMR sheets synchronously

No authentication required. All processing is synchronous and stateless.
    """,
    version="2.0.0",
)


# Response models
class OMRResult(BaseModel):
    """Result model for a single OMR sheet"""
    id: str = Field(..., description="Sheet identifier")
    answers: dict = Field(..., description="Detected answers")
    multi_marked_count: int = Field(..., description="Number of multi-marked questions")
    error: Optional[str] = Field(None, description="Error message if processing failed")


class BatchRequest(BaseModel):
    """Request model for batch processing"""
    sheets: List[dict] = Field(
        ...,
        description="Array of sheets to process. Each sheet must have 'id' and either 'image_url' or 'image_base64'",
        min_length=1,
        max_length=20
    )
    config_json: Optional[str] = Field(None, description="Optional custom config.json as JSON string")
    template_json: Optional[str] = Field(None, description="Optional custom template.json as JSON string")

    @field_validator('sheets')
    @classmethod
    def validate_sheets(cls, sheets):
        if len(sheets) > 20:
            raise ValueError("Maximum 20 sheets allowed per batch")
        
        for i, sheet in enumerate(sheets):
            if 'id' not in sheet:
                raise ValueError(f"Sheet at index {i} missing required field 'id'")
            if 'image_url' not in sheet and 'image_base64' not in sheet:
                raise ValueError(f"Sheet at index {i} must have either 'image_url' or 'image_base64'")
            if 'image_url' in sheet and 'image_base64' in sheet:
                raise ValueError(f"Sheet at index {i} cannot have both 'image_url' and 'image_base64'")
        
        return sheets

    class Config:
        json_schema_extra = {
            "example": {
                "sheets": [
                    {"id": "student_001", "image_url": "https://example.com/sheet1.jpg"},
                    {"id": "student_002", "image_base64": "iVBORw0KGgoAAAANSUhEUg..."}
                ],
                "config_json": None,
                "template_json": None
            }
        }


class BatchResponse(BaseModel):
    """Response model for batch processing"""
    total: int = Field(..., description="Total number of sheets in the batch")
    successful: int = Field(..., description="Number of successfully processed sheets")
    failed: int = Field(..., description="Number of failed sheets")
    results: List[OMRResult] = Field(..., description="Results for each sheet")


# Default configuration directory (can be overridden via environment variable)
DEFAULT_CONFIG_DIR = Path(os.getenv(
    "OMR_DEFAULT_CONFIG_DIR",
    str(Path(__file__).parent / "samples" / "sample1")
))


# Helper functions

def _save_temp_file(content: bytes, suffix: str) -> str:
    """Synchronous helper to save content to a temp file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(content)
        return temp_file.name

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
            
            # Save to temporary file asynchronously
            return await asyncio.to_thread(_save_temp_file, response.content, ext)
                
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


def decode_base64_image(base64_string: str) -> str:
    """
    Decode a base64 image string and save it temporarily.
    
    Args:
        base64_string: Base64 encoded image data (with or without data URI prefix)
        
    Returns:
        str: Path to the temporary file
        
    Raises:
        HTTPException: If decoding fails
    """
    try:
        # Remove data URI prefix if present (e.g., "data:image/jpeg;base64,")
        if ',' in base64_string and base64_string.startswith('data:'):
            base64_string = base64_string.split(',', 1)[1]
        
        # Decode base64
        image_data = base64.b64decode(base64_string)
        
        # Determine file extension from image data signature
        if image_data.startswith(b'\xff\xd8\xff'):
            ext = '.jpg'
        elif image_data.startswith(b'\x89PNG'):
            ext = '.png'
        else:
            ext = '.jpg'  # default
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            temp_file.write(image_data)
            return temp_file.name
            
    except binascii.Error as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid base64 image data: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error decoding base64 image: {str(e)}"
        )


def save_config_files(config_json: Optional[str], template_json: Optional[str]) -> Optional[str]:
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


def cleanup_temp_files(*paths):
    """Clean up temporary files and directories"""
    import shutil
    for path in paths:
        if path and os.path.exists(path):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.unlink(path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {path}: {e}")


# API Endpoints
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API health check"""
    return {
        "message": "OMR Processing API is running",
        "version": "2.0.0",
        "endpoints": {
            "/process-sheet": "Process a single OMR sheet",
            "/process-batch": "Process up to 20 OMR sheets synchronously"
        }
    }


@app.post(
    "/process-sheet",
    response_model=OMRResult,
    tags=["OMR Processing"],
    summary="Process Single OMR Sheet",
    description="Process a single OMR sheet and return detected answers immediately."
)
async def process_sheet(
    sheet_id: str = Form(..., description="Unique identifier for the sheet"),
    image: Optional[UploadFile] = File(None, description="OMR sheet image file (JPG, PNG, etc.)"),
    image_url: Optional[str] = Form(None, description="URL of the OMR sheet image"),
    image_base64: Optional[str] = Form(None, description="Base64 encoded image data"),
    config_json: Optional[str] = Form(None, description="Optional custom config.json as JSON string"),
    template_json: Optional[str] = Form(None, description="Optional custom template.json as JSON string")
):
    """
    Process a single OMR sheet.
    
    - **sheet_id**: Unique identifier for this sheet (returned in response)
    - **image**: The OMR sheet image file (one of image/image_url/image_base64 required)
    - **image_url**: URL to download the OMR sheet image
    - **image_base64**: Base64 encoded image data (with or without data URI prefix)
    - **config_json**: OPTIONAL - Custom config.json as JSON string
    - **template_json**: OPTIONAL - Custom template.json as JSON string
    
    Returns the detected answers immediately.
    """
    
    # Validate that exactly one image source is provided
    provided_sources = sum([bool(image), bool(image_url), bool(image_base64)])
    
    if provided_sources == 0:
        raise HTTPException(
            status_code=400,
            detail="One of 'image', 'image_url', or 'image_base64' must be provided"
        )
    
    if provided_sources > 1:
        raise HTTPException(
            status_code=400,
            detail="Provide only one of 'image', 'image_url', or 'image_base64'"
        )
    
    # Validate file type if image is provided
    if image and hasattr(image, 'content_type') and image.content_type and not image.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {image.content_type}. Please upload an image file."
        )
    
    temp_image_path = None
    custom_config_dir = None
    
    try:
        # Get image (from upload, URL, or base64)
        if image:
            # Save uploaded file temporarily
            suffix = Path(image.filename).suffix if image.filename else '.jpg'
            content = await image.read()
            temp_image_path = await asyncio.to_thread(_save_temp_file, content, suffix)
        elif image_url:
            # Download from URL
            temp_image_path = await download_image_from_url(image_url)
        elif image_base64:
            # Decode from base64
            temp_image_path = decode_base64_image(image_base64)
        else:
            raise HTTPException(
                status_code=400,
                detail="No image source provided"
            )
        
        logger.info(f"Processing OMR for sheet_id: {sheet_id}")
        
        # Save custom config files if provided
        custom_config_dir = save_config_files(config_json, template_json)
        
        # Determine which config directory to use
        config_dir = custom_config_dir if custom_config_dir else str(DEFAULT_CONFIG_DIR)
        
        # Process the OMR image
        result = process_single_omr_image(
            image_path=temp_image_path,
            config_dir=config_dir
        )
        
        logger.info(f"Successfully processed OMR for sheet_id: {sheet_id}")
        
        return OMRResult(
            id=sheet_id,
            answers=result["response"],
            multi_marked_count=result["multi_marked_count"],
            error=None
        )
        
    except Exception as e:
        logger.error(f"Error processing OMR for sheet_id {sheet_id}: {str(e)}")
        return OMRResult(
            id=sheet_id,
            answers={},
            multi_marked_count=0,
            error=str(e)
        )
    
    finally:
        # Clean up temporary files
        cleanup_temp_files(temp_image_path, custom_config_dir)


@app.post(
    "/process-batch",
    response_model=BatchResponse,
    tags=["OMR Processing"],
    summary="Process Multiple OMR Sheets Synchronously",
    description="Process up to 20 OMR sheets synchronously. Returns results for all sheets immediately."
)
async def process_batch(request: BatchRequest):
    """
    Process multiple OMR sheets synchronously (max 20 sheets).
    
    **Request Body**: JSON object with:
    - **sheets**: Array of sheet objects (max 20), each with:
      - **id**: Unique identifier for the sheet (required)
      - **image_url**: URL of the OMR sheet image (either this or image_base64)
      - **image_base64**: Base64 encoded image data (either this or image_url)
    - **config_json**: OPTIONAL - Custom config.json as JSON string (applies to all sheets)
    - **template_json**: OPTIONAL - Custom template.json as JSON string (applies to all sheets)
    
    You can mix image_url and image_base64 in the same batch.
    Returns results for all sheets immediately. Processing happens synchronously.
    """
    
    custom_config_dir = None
    temp_image_paths = []
    
    try:
        logger.info(f"Processing batch of {len(request.sheets)} sheets")
        
        # Save custom config files if provided
        custom_config_dir = save_config_files(request.config_json, request.template_json)
        config_dir = custom_config_dir if custom_config_dir else str(DEFAULT_CONFIG_DIR)
        
        # Process all sheets
        results = []
        successful = 0
        failed = 0
        
        for sheet in request.sheets:
            sheet_id = sheet['id']
            temp_image_path = None
            
            try:
                # Get image (from URL or base64)
                if 'image_url' in sheet:
                    temp_image_path = await download_image_from_url(sheet['image_url'])
                else:
                    temp_image_path = decode_base64_image(sheet['image_base64'])
                
                temp_image_paths.append(temp_image_path)
                
                # Process the OMR image
                result = process_single_omr_image(
                    image_path=temp_image_path,
                    config_dir=config_dir
                )
                
                results.append(OMRResult(
                    id=sheet_id,
                    answers=result["response"],
                    multi_marked_count=result["multi_marked_count"],
                    error=None
                ))
                successful += 1
                logger.info(f"Successfully processed sheet: {sheet_id}")
                
            except Exception as e:
                logger.error(f"Error processing sheet {sheet_id}: {str(e)}")
                results.append(OMRResult(
                    id=sheet_id,
                    answers={},
                    multi_marked_count=0,
                    error=str(e)
                ))
                failed += 1
        
        logger.info(f"Batch processing complete: {successful} successful, {failed} failed")
        
        return BatchResponse(
            total=len(request.sheets),
            successful=successful,
            failed=failed,
            results=results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing batch: {str(e)}"
        )
    
    finally:
        # Clean up all temporary files
        cleanup_temp_files(custom_config_dir, *temp_image_paths)


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
