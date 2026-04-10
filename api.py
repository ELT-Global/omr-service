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
import shutil
from pathlib import Path
from typing import Optional, List, Dict

import httpx
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.openapi.utils import get_openapi
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


# Documentation-only models for Swagger schema
class FieldBlockSchema(BaseModel):
    """Defines a rectangular group of answer fields (questions) on the OMR sheet.
    Either `fieldType` OR (`bubbleValues` + `direction`) must be provided.
    """
    origin: List[int] = Field(
        ...,
        description="[x, y] pixel coordinates of the top-left corner of the first bubble in this block, relative to pageDimensions",
    )
    bubblesGap: float = Field(
        ..., description="Gap in pixels between adjacent bubbles within a single label/question"
    )
    labelsGap: float = Field(
        ..., description="Gap in pixels between adjacent labels (i.e. rows or columns of questions)"
    )
    fieldLabels: List[str] = Field(
        ...,
        description=(
            "Question field label names. Supports compact range syntax: "
            "'q1..10' expands to q1, q2, …, q10. "
            "Labels listed here become keys in the answers response."
        ),
    )
    fieldType: Optional[str] = Field(
        None,
        description=(
            "Predefined question type shorthand. One of: "
            "QTYPE_MCQ4 (bubbles A-D, horizontal), "
            "QTYPE_MCQ5 (bubbles A-E, horizontal), "
            "QTYPE_INT (digits 0-9, vertical), "
            "QTYPE_INT_FROM_1 (digits 1-9 then 0, vertical). "
            "Use this OR bubbleValues+direction, not both."
        ),
    )
    bubbleValues: Optional[List[str]] = Field(
        None,
        description=(
            "Custom list of answer values corresponding to each bubble position "
            "(e.g. ['A','B','C','D'] or ['True','False']). "
            "Must be paired with 'direction'. Use this OR fieldType, not both."
        ),
    )
    direction: Optional[str] = Field(
        None,
        description="Bubble layout direction: 'horizontal' or 'vertical'. Required when using bubbleValues.",
    )
    bubbleDimensions: Optional[List[float]] = Field(
        None,
        description="[width, height] — override the global bubbleDimensions for this block only",
    )
    emptyValue: Optional[str] = Field(
        None,
        description="Value written when no bubble is detected in this block (overrides global emptyValue)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "fieldType": "QTYPE_MCQ4",
                    "origin": [134, 684],
                    "fieldLabels": ["q1..10"],
                    "bubblesGap": 79,
                    "labelsGap": 62,
                }
            ]
        }
    }


class PreProcessorConfig(BaseModel):
    """A single image pre-processor applied before OMR bubble detection."""
    name: str = Field(
        ...,
        description=(
            "Pre-processor name. Supported values: "
            "CropOnMarkers (align/crop using printed corner markers), "
            "CropPage (auto-detect and crop the page boundary), "
            "FeatureBasedAlignment (warp sheet to match a reference image), "
            "GaussianBlur (reduce noise), "
            "MedianBlur (reduce salt-and-pepper noise), "
            "Levels (adjust brightness/contrast)."
        ),
    )
    options: Dict[str, object] = Field(
        ...,
        description=(
            "Options specific to the chosen pre-processor. "
            "CropOnMarkers: relativePath (required), marker_rescale_range, marker_rescale_steps, min_matching_threshold. "
            "CropPage: morphKernel ([w,h]). "
            "FeatureBasedAlignment: reference (required), maxFeatures, goodMatchPercent, 2d. "
            "GaussianBlur: kSize ([w,h]), sigmaX. "
            "MedianBlur: kSize (integer). "
            "Levels: low, high, gamma (all 0-1)."
        ),
    )


class TemplateJsonSchema(BaseModel):
    """Structure of the template.json that defines the OMR sheet layout.

    Pass this as a JSON-encoded string in the `template_json` field of
    `/process-sheet` (form) or `/process-batch` (JSON body).
    All pixel coordinates are expressed in the coordinate space of `pageDimensions`.
    """
    pageDimensions: List[int] = Field(
        ...,
        description="[width, height] — the sheet is resized to these dimensions before any processing. All field block coordinates must be relative to this size.",
    )
    bubbleDimensions: List[int] = Field(
        ...,
        description="[width, height] — default size in pixels of each answer bubble. Can be overridden per field block.",
    )
    fieldBlocks: Dict[str, FieldBlockSchema] = Field(
        ...,
        description=(
            "Named groups of adjacent answer fields. "
            "Each key is an arbitrary descriptive block name (e.g. 'MCQBlock1', 'RollNumber'); "
            "each value is a FieldBlockSchema describing that group's position and layout."
        ),
    )
    preProcessors: Optional[List[PreProcessorConfig]] = Field(
        None,
        description="Ordered list of image pre-processors applied before bubble detection. Common use: CropPage to auto-detect page edges, then GaussianBlur to reduce noise.",
    )
    customLabels: Optional[Dict[str, List[str]]] = Field(
        None,
        description=(
            "Composite answer labels. Maps a combined label name to an ordered list of sub-field labels "
            "whose detected values are concatenated. Example: {'Roll': ['roll1..3']} joins roll1+roll2+roll3 "
            "into a single 'Roll' entry in the answers response."
        ),
    )
    emptyValue: Optional[str] = Field(
        None,
        description="Global default value used when no bubble is marked in a field. Defaults to empty string.",
    )
    outputColumns: Optional[List[str]] = Field(
        None,
        description="Ordered list of field label names to include in CSV output. When omitted, all labels are output in alphabetical order.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pageDimensions": [1189, 1682],
                    "bubbleDimensions": [30, 30],
                    "preProcessors": [
                        {"name": "GaussianBlur", "options": {"kSize": [3, 3], "sigmaX": 0}},
                        {"name": "CropPage", "options": {"morphKernel": [10, 10]}},
                    ],
                    "fieldBlocks": {
                        "MCQBlock1": {
                            "fieldType": "QTYPE_MCQ4",
                            "origin": [134, 684],
                            "fieldLabels": ["q1..11"],
                            "bubblesGap": 79,
                            "labelsGap": 62,
                        }
                    },
                }
            ]
        }
    }


# Response models
class OMRResult(BaseModel):
    """Result model for a single OMR sheet"""
    id: str = Field(..., description="Sheet identifier")
    answers: Dict[str, str] = Field(
        ...,
        description=(
            "Detected answers keyed by field label name. "
            "Values are the detected bubble answer strings: "
            "'A'/'B'/'C'/'D' for MCQ4 fields, "
            "'A'/'B'/'C'/'D'/'E' for MCQ5 fields, "
            "a digit string ('0'–'9') for integer-type fields, "
            "concatenated digits (e.g. '42') for customLabels that join multiple integer fields, "
            "or empty string if no bubble was detected."
        ),
        examples=[{"q1": "A", "q2": "C", "q3": "B", "q4": "D", "Roll": "42"}],
    )
    multi_marked_count: int = Field(
        ...,
        description="Number of questions where multiple bubbles were marked simultaneously",
    )
    error: Optional[str] = Field(None, description="Error message if processing failed, null on success")


class BatchRequest(BaseModel):
    """Request model for batch processing"""
    sheets: List[dict] = Field(
        ...,
        description="Array of sheets to process. Each sheet must have 'id' and either 'image_url' or 'image_base64'",
        min_length=1,
        max_length=20
    )
    config_json: Optional[str] = Field(
        None,
        description="Optional custom config.json as a JSON string. Controls processing thresholds and alignment parameters.",
    )
    template_json: Optional[str] = Field(
        None,
        description=(
            "Optional custom template.json as a JSON string. "
            "Defines the OMR sheet layout: page size, bubble dimensions, field block positions, and pre-processors. "
            "See the TemplateJsonSchema model in the Schemas section below for the full structure and field descriptions."
        ),
        examples=[
            '{"pageDimensions":[1189,1682],"bubbleDimensions":[30,30],"preProcessors":[{"name":"CropPage","options":{"morphKernel":[10,10]}}],"fieldBlocks":{"MCQBlock1":{"fieldType":"QTYPE_MCQ4","origin":[134,684],"fieldLabels":["q1..10"],"bubblesGap":79,"labelsGap":62}}}'
        ],
    )

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


# Inject TemplateJsonSchema (and sub-models) into the OpenAPI spec so that:
# 1) They appear in the Swagger UI "Schemas" section at the bottom of /docs
# 2) template_json string fields link to the schema via contentSchema
def _build_inline_template_schema():
    """Build a fully-resolved (no $refs) JSON Schema for TemplateJsonSchema."""
    raw = TemplateJsonSchema.model_json_schema()
    defs = raw.pop("$defs", {})

    def _resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref_name = node["$ref"].rsplit("/", 1)[-1]
                resolved = defs.get(ref_name, {})
                return _resolve(resolved)
            return {k: _resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_resolve(item) for item in node]
        return node

    return _resolve(raw)


def _patch_template_json_field(schema_obj, inline_schema):
    """Replace a plain string type with the full inline JSON structure."""
    schema_obj["contentMediaType"] = "application/json"
    schema_obj["contentSchema"] = inline_schema


def _walk_and_patch(obj, inline_schema):
    """Recursively find template_json properties in the OpenAPI spec and patch them."""
    if isinstance(obj, dict):
        props = obj.get("properties", {})
        if "template_json" in props:
            tj = props["template_json"]
            if "anyOf" in tj:
                for variant in tj["anyOf"]:
                    if variant.get("type") == "string":
                        _patch_template_json_field(variant, inline_schema)
            elif tj.get("type") == "string":
                _patch_template_json_field(tj, inline_schema)
        for v in obj.values():
            _walk_and_patch(v, inline_schema)
    elif isinstance(obj, list):
        for item in obj:
            _walk_and_patch(item, inline_schema)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Build the fully-expanded template schema (no $ref indirection)
    inline_schema = _build_inline_template_schema()

    # Patch all template_json string fields with the full inline structure
    _walk_and_patch(openapi_schema, inline_schema)

    # Also register the models in components/schemas so they appear
    # in Swagger UI's "Schemas" section at the bottom of /docs
    schemas = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
    template_schema = TemplateJsonSchema.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    defs = template_schema.pop("$defs", {})
    defs["TemplateJsonSchema"] = template_schema
    schemas.update(defs)

    app.openapi_schema = openapi_schema
    return openapi_schema

app.openapi = custom_openapi


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
        # Copy assets from default config directory first
        if DEFAULT_CONFIG_DIR.exists():
            for item in os.listdir(DEFAULT_CONFIG_DIR):
                s = DEFAULT_CONFIG_DIR / item
                if os.path.isfile(s):
                    shutil.copy2(s, temp_dir)

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
    config_json: Optional[str] = Form(
        None,
        description="Optional custom config.json as a JSON string. Controls processing thresholds and alignment parameters.",
    ),
    template_json: Optional[str] = Form(
        None,
        description=(
            "Optional custom template.json as a JSON string. "
            "Defines the OMR sheet layout: page size, bubble dimensions, field block positions, and pre-processors. "
            "See the TemplateJsonSchema model in the Schemas section below for the full structure and field descriptions."
        ),
    )
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
