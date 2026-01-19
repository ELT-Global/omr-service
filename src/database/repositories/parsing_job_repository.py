"""
Parsing job repository
Handles database operations for parsing jobs
"""

from typing import Optional, List
from datetime import datetime
from .base import BaseRepository
from ..models import ParsingJob, JobStatus, CallbackStatus


class ParsingJobRepository(BaseRepository):
    """
    Repository for parsing job operations
    
    Provides CRUD operations and queries for the parsing_jobs table.
    """
    
    def create(self, job: ParsingJob) -> ParsingJob:
        """
        Create a new parsing job
        
        Args:
            job: ParsingJob model instance
            
        Returns:
            ParsingJob: Created parsing job
        """
        query = """
            INSERT INTO parsing_jobs 
            (id, operator_id, status, total_sheets, processed_sheets, 
             callback_status, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self._execute(query, (
            job.id,
            job.operator_id,
            job.status.value,
            job.total_sheets,
            job.processed_sheets,
            job.callback_status.value,
            job.created_at.isoformat(),
            job.completed_at.isoformat() if job.completed_at else None
        ))
        self.connection.commit()
        return job
    
    def find_by_id(self, job_id: str) -> Optional[ParsingJob]:
        """
        Find parsing job by ID
        
        Args:
            job_id: Job identifier
            
        Returns:
            Optional[ParsingJob]: Parsing job or None if not found
        """
        query = "SELECT * FROM parsing_jobs WHERE id = ?"
        row = self._fetchone(query, (job_id,))
        return self._row_to_job(row) if row else None
    
    def find_by_operator(self, operator_id: str) -> List[ParsingJob]:
        """
        Find all jobs for an operator
        
        Args:
            operator_id: Operator identifier
            
        Returns:
            List[ParsingJob]: List of jobs, ordered by creation date
        """
        query = """
            SELECT * FROM parsing_jobs 
            WHERE operator_id = ? 
            ORDER BY created_at DESC
        """
        rows = self._fetchall(query, (operator_id,))
        return [self._row_to_job(row) for row in rows]
    
    def find_by_status(self, status: JobStatus) -> List[ParsingJob]:
        """
        Find jobs by status
        
        Args:
            status: Job status to filter by
            
        Returns:
            List[ParsingJob]: List of jobs with specified status
        """
        query = "SELECT * FROM parsing_jobs WHERE status = ? ORDER BY created_at DESC"
        rows = self._fetchall(query, (status.value,))
        return [self._row_to_job(row) for row in rows]
    
    def find_pending_callbacks(self) -> List[ParsingJob]:
        """
        Find completed jobs with pending callbacks
        
        Returns:
            List[ParsingJob]: Jobs that need webhook callbacks
        """
        query = """
            SELECT * FROM parsing_jobs 
            WHERE status = 'COMPLETED' 
            AND callback_status = 'NOT_SENT'
            ORDER BY completed_at ASC
        """
        rows = self._fetchall(query)
        return [self._row_to_job(row) for row in rows]
    
    def update(self, job: ParsingJob) -> ParsingJob:
        """
        Update a parsing job
        
        Args:
            job: ParsingJob model with updated data
            
        Returns:
            ParsingJob: Updated job
        """
        query = """
            UPDATE parsing_jobs 
            SET operator_id = ?, status = ?, total_sheets = ?, 
                processed_sheets = ?, callback_status = ?, completed_at = ?
            WHERE id = ?
        """
        self._execute(query, (
            job.operator_id,
            job.status.value,
            job.total_sheets,
            job.processed_sheets,
            job.callback_status.value,
            job.completed_at.isoformat() if job.completed_at else None,
            job.id
        ))
        self.connection.commit()
        return job
    
    def update_status(self, job_id: str, status: JobStatus, 
                      completed_at: Optional[datetime] = None) -> bool:
        """
        Update job status
        
        Args:
            job_id: Job identifier
            status: New job status
            completed_at: Completion timestamp (for COMPLETED/FAILED status)
            
        Returns:
            bool: True if job was updated
        """
        query = """
            UPDATE parsing_jobs 
            SET status = ?, completed_at = ?
            WHERE id = ?
        """
        cursor = self._execute(query, (
            status.value, 
            completed_at.isoformat() if completed_at else None, 
            job_id
        ))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def update_completed_at(self, job_id: str, completed_at: datetime) -> bool:
        """
        Update job completion timestamp
        
        Args:
            job_id: Job identifier
            completed_at: Completion timestamp
            
        Returns:
            bool: True if job was updated
        """
        query = """
            UPDATE parsing_jobs 
            SET completed_at = ?
            WHERE id = ?
        """
        cursor = self._execute(query, (completed_at.isoformat(), job_id))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def increment_processed(self, job_id: str) -> int:
        """
        Increment processed sheets counter and return new count
        
        Args:
            job_id: Job identifier
            
        Returns:
            int: New processed count
        """
        query = """
            UPDATE parsing_jobs 
            SET processed_sheets = processed_sheets + 1
            WHERE id = ?
        """
        self._execute(query, (job_id,))
        self.connection.commit()
        
        # Return updated count
        job = self.find_by_id(job_id)
        return job.processed_sheets if job else 0
    
    def find_by_callback_status(self, callback_status: CallbackStatus) -> List[ParsingJob]:
        """
        Find jobs by callback status
        
        Args:
            callback_status: Callback status to filter by
            
        Returns:
            List[ParsingJob]: List of jobs with specified callback status
        """
        query = "SELECT * FROM parsing_jobs WHERE callback_status = ? ORDER BY created_at DESC"
        rows = self._fetchall(query, (callback_status.value,))
        return [self._row_to_job(row) for row in rows]
    
    def update_progress(self, job_id: str, processed_sheets: int) -> bool:
        """
        Update job progress
        
        Args:
            job_id: Job identifier
            processed_sheets: Number of sheets processed
            
        Returns:
            bool: True if job was updated
        """
        query = """
            UPDATE parsing_jobs 
            SET processed_sheets = ?
            WHERE id = ?
        """
        cursor = self._execute(query, (processed_sheets, job_id))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def increment_progress(self, job_id: str, increment: int = 1) -> bool:
        """
        Increment processed sheets counter
        
        Args:
            job_id: Job identifier
            increment: Number to increment by (default: 1)
            
        Returns:
            bool: True if job was updated
        """
        query = """
            UPDATE parsing_jobs 
            SET processed_sheets = processed_sheets + ?
            WHERE id = ?
        """
        cursor = self._execute(query, (increment, job_id))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def update_callback_status(self, job_id: str, 
                               callback_status: CallbackStatus) -> bool:
        """
        Update callback status
        
        Args:
            job_id: Job identifier
            callback_status: New callback status
            
        Returns:
            bool: True if job was updated
        """
        query = """
            UPDATE parsing_jobs 
            SET callback_status = ?
            WHERE id = ?
        """
        cursor = self._execute(query, (callback_status.value, job_id))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def delete(self, job_id: str) -> bool:
        """
        Delete a parsing job
        
        Note: This will cascade delete all associated OMR sheets
        
        Args:
            job_id: Job identifier
            
        Returns:
            bool: True if job was deleted
        """
        query = "DELETE FROM parsing_jobs WHERE id = ?"
        cursor = self._execute(query, (job_id,))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def _row_to_job(self, row) -> ParsingJob:
        """
        Convert database row to ParsingJob model
        
        Args:
            row: SQLite row object
            
        Returns:
            ParsingJob: ParsingJob model instance
        """
        return ParsingJob(
            id=row['id'],
            operator_id=row['operator_id'],
            status=JobStatus(row['status']),
            total_sheets=row['total_sheets'],
            processed_sheets=row['processed_sheets'],
            callback_status=CallbackStatus(row['callback_status']),
            created_at=datetime.fromisoformat(row['created_at']),
            completed_at=datetime.fromisoformat(row['completed_at']) 
                if row['completed_at'] else None
        )
