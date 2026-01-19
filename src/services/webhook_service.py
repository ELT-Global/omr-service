"""
Webhook Service
Handles webhook callbacks to operators upon job completion
"""

from typing import Optional, Dict, Any
import httpx
from datetime import datetime

from ..database.models import CallbackStatus
from ..logger import logger
from .parsing_job_service import ParsingJobService


class WebhookService:
    """
    Service for sending webhook callbacks
    
    Sends job completion notifications to operator webhook URLs.
    """
    
    def __init__(self, job_service: Optional[ParsingJobService] = None):
        """
        Initialize service
        
        Args:
            job_service: ParsingJobService instance (optional)
        """
        self.job_service = job_service if job_service else ParsingJobService()
    
    async def send_job_completion(self, job_id: str) -> bool:
        """
        Send job completion webhook
        
        Args:
            job_id: Job identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get job details
            job = self.job_service.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found for webhook")
                return False
            
            # Get operator to retrieve webhook URL
            operator = self.job_service.uow.operators.find_by_id(job.operator_id)
            if not operator:
                logger.error(f"Operator {job.operator_id} not found for webhook")
                return False
            
            # Get sheets data
            sheets = self.job_service.get_job_sheets(job_id)
            
            # Format payload
            payload = self._format_callback_payload(job_id, job, sheets)
            
            # Send webhook
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    operator.webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                )
                response.raise_for_status()
            
            # Update callback status
            self.job_service.update_callback_status(job_id, CallbackStatus.SENT)
            logger.info(f"Webhook sent successfully for job {job_id} to {operator.webhook_url}")
            
            return True
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending webhook for job {job_id}: {str(e)}")
            self.job_service.update_callback_status(job_id, CallbackStatus.FAILED)
            return False
        except Exception as e:
            logger.error(f"Error sending webhook for job {job_id}: {str(e)}")
            self.job_service.update_callback_status(job_id, CallbackStatus.FAILED)
            return False
    
    def _format_callback_payload(self, job_id: str, job, sheets) -> Dict[str, Any]:
        """
        Format webhook payload
        
        Args:
            job_id: Job identifier
            job: ParsingJob model
            sheets: List of OMRSheet models
            
        Returns:
            Dict: Formatted payload
        """
        from ..database.models import SheetStatus
        
        successful_sheets = [s for s in sheets if s.status == SheetStatus.PARSED]
        failed_sheets = [s for s in sheets if s.status == SheetStatus.FAILED]
        
        sheet_results = []
        for sheet in sheets:
            sheet_data = {
                'id': sheet.id,
                'image_url': sheet.image_url,
                'status': sheet.status.value,
            }
            
            if sheet.status == SheetStatus.PARSED:
                sheet_data['answers'] = sheet.answered_options_json
            elif sheet.status == SheetStatus.FAILED:
                sheet_data['error'] = sheet.error_message
            
            sheet_results.append(sheet_data)
        
        payload = {
            'jobId': job_id,
            'status': job.status.value,
            'totalSheets': job.total_sheets,
            'processedSheets': job.processed_sheets,
            'successfulSheets': len(successful_sheets),
            'failedSheets': len(failed_sheets),
            'createdAt': job.created_at.isoformat(),
            'completedAt': job.completed_at.isoformat() if job.completed_at else None,
            'sheets': sheet_results
        }
        
        return payload
    
    async def retry_failed_callbacks(self, max_retries: int = 3) -> int:
        """
        Retry failed webhook callbacks
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            int: Number of successfully retried webhooks
        """
        from ..database.models import JobStatus
        
        # Find jobs with failed callbacks
        jobs = self.job_service.uow.parsing_jobs.find_by_callback_status(CallbackStatus.FAILED)
        
        # Filter to only completed jobs
        completed_jobs = [j for j in jobs if j.status in [JobStatus.COMPLETED, JobStatus.FAILED]]
        
        retry_count = 0
        for job in completed_jobs:
            success = await self.send_job_completion(job.id)
            if success:
                retry_count += 1
        
        logger.info(f"Retried {retry_count}/{len(completed_jobs)} failed webhooks")
        return retry_count
