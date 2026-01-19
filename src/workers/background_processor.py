"""
Background Processor
Handles asynchronous processing of parsing jobs
"""

import asyncio
import tempfile
import os
from typing import Optional
from pathlib import Path

import httpx

from ..services.parsing_job_service import ParsingJobService
from ..services.webhook_service import WebhookService
from ..database.models import SheetStatus
from ..api_utils import process_single_omr_image
from ..logger import logger


class BackgroundProcessor:
    """
    Background processor for parsing jobs
    
    Processes OMR sheets asynchronously in the background.
    Uses FastAPI's BackgroundTasks for simplicity.
    """
    
    def __init__(
        self,
        job_service: Optional[ParsingJobService] = None,
        webhook_service: Optional[WebhookService] = None
    ):
        """
        Initialize processor
        
        Args:
            job_service: ParsingJobService instance (optional)
            webhook_service: WebhookService instance (optional)
        """
        self.job_service = job_service if job_service else ParsingJobService()
        self.webhook_service = webhook_service if webhook_service else WebhookService(self.job_service)
    
    async def process_job(self, job_id: str, config_dir: str) -> None:
        """
        Process all sheets in a parsing job
        
        This is the main background task that processes all pending sheets.
        
        Args:
            job_id: Job identifier
            config_dir: Configuration directory path
        """
        logger.info(f"Starting background processing for job {job_id}")
        
        try:
            # Update job status to PROCESSING
            self.job_service.start_job_processing(job_id)
            
            # Get all pending sheets
            sheets = self.job_service.get_pending_sheets(job_id)
            
            logger.info(f"Processing {len(sheets)} sheets for job {job_id}")
            
            # Process each sheet
            for sheet in sheets:
                await self._process_single_sheet(sheet.id, sheet.image_url, config_dir)
                
                # Increment processed count
                self.job_service.increment_processed_count(job_id)
            
            # Complete the job
            self.job_service.complete_job(job_id)
            
            # Send webhook callback
            await self.webhook_service.send_job_completion(job_id)
            
            logger.info(f"Completed background processing for job {job_id}")
            
        except Exception as e:
            logger.error(f"Error in background processing for job {job_id}: {str(e)}")
            # Job will remain in PROCESSING state, can be retried manually
    
    async def _process_single_sheet(
        self,
        sheet_id: str,
        image_url: str,
        config_dir: str
    ) -> None:
        """
        Process a single OMR sheet
        
        Args:
            sheet_id: Sheet identifier
            image_url: URL of the sheet image
            config_dir: Configuration directory path
        """
        temp_image_path = None
        
        try:
            # Download image
            temp_image_path = await self._download_image(image_url)
            
            # Process OMR
            result = process_single_omr_image(
                image_path=temp_image_path,
                config_dir=config_dir
            )
            
            # Update sheet with success
            self.job_service.update_sheet_success(
                sheet_id=sheet_id,
                answers=result["response"],
                multi_marked_count=result["multi_marked_count"]
            )
            
            logger.info(f"Successfully processed sheet {sheet_id}")
            
        except Exception as e:
            error_msg = str(e)
            # Update sheet with failure
            self.job_service.update_sheet_failure(sheet_id, error_msg)
            logger.error(f"Failed to process sheet {sheet_id}: {error_msg}")
        
        finally:
            # Clean up temporary file
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.unlink(temp_image_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {temp_image_path}: {e}")
    
    async def _download_image(self, url: str) -> str:
        """
        Download image from URL
        
        Args:
            url: Image URL
            
        Returns:
            str: Path to temporary file
            
        Raises:
            Exception: If download fails
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Determine file extension
                content_type = response.headers.get('content-type', '')
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = '.jpg'
                elif 'png' in content_type:
                    ext = '.png'
                else:
                    ext = '.jpg'
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                    temp_file.write(response.content)
                    return temp_file.name
                    
        except httpx.HTTPError as e:
            raise Exception(f"Failed to download image from URL: {str(e)}")
        except Exception as e:
            raise Exception(f"Error downloading image: {str(e)}")


# Global singleton instance
_background_processor = None


def get_background_processor() -> BackgroundProcessor:
    """
    Get global background processor instance
    
    Returns:
        BackgroundProcessor: Singleton instance
    """
    global _background_processor
    if _background_processor is None:
        _background_processor = BackgroundProcessor()
    return _background_processor
