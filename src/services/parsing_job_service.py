"""
Parsing Job Service
Manages the lifecycle of parsing jobs and OMR sheet processing
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from ..database.models import ParsingJob, OMRSheet, JobStatus, SheetStatus, CallbackStatus
from ..database.unit_of_work import UnitOfWork
from ..logger import logger


class ParsingJobService:
    """
    Service for managing parsing job lifecycle
    
    Handles creation, processing, and completion of parsing jobs.
    """
    
    def __init__(self, uow: Optional[UnitOfWork] = None):
        """
        Initialize service
        
        Args:
            uow: Unit of Work instance (optional, creates new if not provided)
        """
        self.uow = uow if uow else UnitOfWork()
    
    def create_job(
        self,
        operator_id: str,
        items: List[Dict[str, str]],
        config_dir: str
    ) -> ParsingJob:
        """
        Create a new parsing job with all OMR sheets
        
        Args:
            operator_id: ID of the operator creating the job
            items: List of items with 'id' and 'image_url'
            config_dir: Configuration directory path for processing
            
        Returns:
            ParsingJob: Created job
        """
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        
        # Create job
        job = ParsingJob(
            id=job_id,
            operator_id=operator_id,
            status=JobStatus.PENDING,
            total_sheets=len(items),
            processed_sheets=0,
            callback_status=CallbackStatus.NOT_SENT,
            created_at=datetime.utcnow(),
            completed_at=None
        )
        
        with self.uow.transaction():
            # Save job
            self.uow.parsing_jobs.create(job)
            
            # Create sheets
            for item in items:
                sheet_id = f"sheet_{uuid.uuid4().hex[:12]}"
                sheet = OMRSheet(
                    id=sheet_id,
                    parsing_job_id=job_id,
                    image_url=item['image_url'],
                    answered_options_json={},
                    status=SheetStatus.PENDING,
                    created_at=datetime.utcnow(),
                    error_message=None,
                    parsed_at=None
                )
                self.uow.omr_sheets.create(sheet)
        
        logger.info(f"Created parsing job {job_id} with {len(items)} sheets for operator {operator_id}")
        return job
    
    def get_job(self, job_id: str) -> Optional[ParsingJob]:
        """
        Get job by ID
        
        Args:
            job_id: Job identifier
            
        Returns:
            Optional[ParsingJob]: Job or None if not found
        """
        return self.uow.parsing_jobs.find_by_id(job_id)
    
    def get_job_sheets(self, job_id: str) -> List[OMRSheet]:
        """
        Get all sheets for a job
        
        Args:
            job_id: Job identifier
            
        Returns:
            List[OMRSheet]: List of sheets
        """
        return self.uow.omr_sheets.find_by_job(job_id)
    
    def get_pending_sheets(self, job_id: str) -> List[OMRSheet]:
        """
        Get pending sheets for a job
        
        Args:
            job_id: Job identifier
            
        Returns:
            List[OMRSheet]: List of pending sheets
        """
        return self.uow.omr_sheets.find_by_job_and_status(job_id, SheetStatus.PENDING)
    
    def start_job_processing(self, job_id: str) -> None:
        """
        Mark job as processing
        
        Args:
            job_id: Job identifier
        """
        self.uow.parsing_jobs.update_status(job_id, JobStatus.PROCESSING)
        logger.info(f"Job {job_id} status updated to PROCESSING")
    
    def update_sheet_success(
        self,
        sheet_id: str,
        answers: Dict[str, Any],
        multi_marked_count: int
    ) -> None:
        """
        Update sheet with successful parsing results
        
        Args:
            sheet_id: Sheet identifier
            answers: Parsed answers dictionary
            multi_marked_count: Number of multi-marked questions
        """
        self.uow.omr_sheets.update_parsed(
            sheet_id=sheet_id,
            answers=answers,
            multi_marked_count=multi_marked_count
        )
        logger.info(f"Sheet {sheet_id} parsed successfully")
    
    def update_sheet_failure(self, sheet_id: str, error_message: str) -> None:
        """
        Update sheet with failure status and error
        
        Args:
            sheet_id: Sheet identifier
            error_message: Error description
        """
        self.uow.omr_sheets.update_failed(sheet_id, error_message)
        logger.error(f"Sheet {sheet_id} failed: {error_message}")
    
    def increment_processed_count(self, job_id: str) -> int:
        """
        Increment the processed sheets count for a job
        
        Args:
            job_id: Job identifier
            
        Returns:
            int: New processed count
        """
        return self.uow.parsing_jobs.increment_processed(job_id)
    
    def complete_job(self, job_id: str) -> None:
        """
        Mark job as completed
        
        Checks if all sheets are processed and updates job status accordingly.
        
        Args:
            job_id: Job identifier
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        # Check if all sheets are processed
        sheets = self.get_job_sheets(job_id)
        all_processed = all(sheet.status in [SheetStatus.PARSED, SheetStatus.FAILED] for sheet in sheets)
        
        if not all_processed:
            logger.warning(f"Job {job_id} completion attempted but not all sheets are processed")
            return
        
        # Determine job status based on sheet statuses
        failed_count = sum(1 for sheet in sheets if sheet.status == SheetStatus.FAILED)
        
        if failed_count == len(sheets):
            # All sheets failed
            final_status = JobStatus.FAILED
        else:
            # At least one sheet succeeded
            final_status = JobStatus.COMPLETED
        
        self.uow.parsing_jobs.update_status(job_id, final_status)
        self.uow.parsing_jobs.update_completed_at(job_id, datetime.utcnow())
        
        logger.info(f"Job {job_id} completed with status {final_status.value}")
    
    def update_callback_status(self, job_id: str, status: CallbackStatus) -> None:
        """
        Update webhook callback status
        
        Args:
            job_id: Job identifier
            status: Callback status
        """
        self.uow.parsing_jobs.update_callback_status(job_id, status)
        logger.info(f"Job {job_id} callback status updated to {status.value}")
    
    def get_job_statistics(self, job_id: str) -> Dict[str, Any]:
        """
        Get statistics for a job
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dict: Job statistics including counts
        """
        job = self.get_job(job_id)
        if not job:
            return {}
        
        sheets = self.get_job_sheets(job_id)
        
        successful = sum(1 for sheet in sheets if sheet.status == SheetStatus.PARSED)
        failed = sum(1 for sheet in sheets if sheet.status == SheetStatus.FAILED)
        pending = sum(1 for sheet in sheets if sheet.status == SheetStatus.PENDING)
        
        return {
            'job_id': job.id,
            'status': job.status.value,
            'total_sheets': job.total_sheets,
            'processed_sheets': job.processed_sheets,
            'successful_sheets': successful,
            'failed_sheets': failed,
            'pending_sheets': pending,
            'callback_status': job.callback_status.value,
            'created_at': job.created_at.isoformat(),
            'completed_at': job.completed_at.isoformat() if job.completed_at else None
        }
