"""
OMR sheet repository
Handles database operations for individual OMR sheets
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import json
from .base import BaseRepository
from ..models import OMRSheet, SheetStatus


class OMRSheetRepository(BaseRepository):
    """
    Repository for OMR sheet operations
    
    Provides CRUD operations and queries for the omr_sheets table.
    """
    
    def create(self, sheet: OMRSheet) -> OMRSheet:
        """
        Create a new OMR sheet
        
        Args:
            sheet: OMRSheet model instance
            
        Returns:
            OMRSheet: Created OMR sheet
        """
        query = """
            INSERT INTO omr_sheets 
            (id, parsing_job_id, image_url, answered_options_json, 
             status, error_message, created_at, parsed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self._execute(query, (
            sheet.id,
            sheet.parsing_job_id,
            sheet.image_url,
            json.dumps(sheet.answered_options_json),
            sheet.status.value,
            sheet.error_message,
            sheet.created_at.isoformat(),
            sheet.parsed_at.isoformat() if sheet.parsed_at else None
        ))
        self.connection.commit()
        return sheet
    
    def find_by_id(self, sheet_id: str) -> Optional[OMRSheet]:
        """
        Find sheet by ID
        
        Args:
            sheet_id: Sheet identifier
            
        Returns:
            Optional[OMRSheet]: OMR sheet or None if not found
        """
        query = "SELECT * FROM omr_sheets WHERE id = ?"
        row = self._fetchone(query, (sheet_id,))
        return self._row_to_sheet(row) if row else None
    
    def find_by_job(self, job_id: str) -> List[OMRSheet]:
        """
        Find all sheets for a job
        
        Args:
            job_id: Parsing job identifier
            
        Returns:
            List[OMRSheet]: List of sheets, ordered by creation date
        """
        query = """
            SELECT * FROM omr_sheets 
            WHERE parsing_job_id = ? 
            ORDER BY created_at ASC
        """
        rows = self._fetchall(query, (job_id,))
        return [self._row_to_sheet(row) for row in rows]
    
    def find_by_job_and_status(self, job_id: str, status: SheetStatus) -> List[OMRSheet]:
        """
        Find sheets for a job with specific status
        
        Args:
            job_id: Parsing job identifier
            status: Sheet status to filter by
            
        Returns:
            List[OMRSheet]: List of sheets matching criteria
        """
        query = """
            SELECT * FROM omr_sheets 
            WHERE parsing_job_id = ? AND status = ?
            ORDER BY created_at ASC
        """
        rows = self._fetchall(query, (job_id, status.value))
        return [self._row_to_sheet(row) for row in rows]
    
    def find_pending(self, limit: Optional[int] = None) -> List[OMRSheet]:
        """
        Find pending sheets across all jobs
        
        Args:
            limit: Maximum number of sheets to return
            
        Returns:
            List[OMRSheet]: List of pending sheets
        """
        query = """
            SELECT * FROM omr_sheets 
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
        """
        if limit:
            query += f" LIMIT {limit}"
        
        rows = self._fetchall(query)
        return [self._row_to_sheet(row) for row in rows]
    
    def count_by_job_and_status(self, job_id: str, status: SheetStatus) -> int:
        """
        Count sheets for a job with specific status
        
        Args:
            job_id: Parsing job identifier
            status: Sheet status to count
            
        Returns:
            int: Number of sheets matching criteria
        """
        query = """
            SELECT COUNT(*) as count FROM omr_sheets 
            WHERE parsing_job_id = ? AND status = ?
        """
        row = self._fetchone(query, (job_id, status.value))
        return row['count'] if row else 0
    
    def update(self, sheet: OMRSheet) -> OMRSheet:
        """
        Update an OMR sheet
        
        Args:
            sheet: OMRSheet model with updated data
            
        Returns:
            OMRSheet: Updated sheet
        """
        query = """
            UPDATE omr_sheets 
            SET parsing_job_id = ?, image_url = ?, answered_options_json = ?,
                status = ?, error_message = ?, parsed_at = ?
            WHERE id = ?
        """
        self._execute(query, (
            sheet.parsing_job_id,
            sheet.image_url,
            json.dumps(sheet.answered_options_json),
            sheet.status.value,
            sheet.error_message,
            sheet.parsed_at.isoformat() if sheet.parsed_at else None,
            sheet.id
        ))
        self.connection.commit()
        return sheet
    
    def update_parsed(self, sheet_id: str, answers: Dict[str, Any], 
                     multi_marked_count: int = 0,
                     parsed_at: Optional[datetime] = None) -> bool:
        """
        Update sheet with parsed results
        
        Args:
            sheet_id: Sheet identifier
            answers: Parsed answers dictionary
            multi_marked_count: Number of multi-marked questions
            parsed_at: Parsing completion timestamp (defaults to now)
            
        Returns:
            bool: True if sheet was updated
        """
        if parsed_at is None:
            parsed_at = datetime.utcnow()
        
        # Store both answers and metadata
        result_data = {
            'answers': answers,
            'multi_marked_count': multi_marked_count
        }
        
        query = """
            UPDATE omr_sheets 
            SET answered_options_json = ?, status = ?, parsed_at = ?, error_message = NULL
            WHERE id = ?
        """
        cursor = self._execute(query, (
            json.dumps(result_data),
            SheetStatus.PARSED.value,
            parsed_at.isoformat(),
            sheet_id
        ))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def update_failed(self, sheet_id: str, error_message: str) -> bool:
        """
        Mark sheet as failed with error message
        
        Args:
            sheet_id: Sheet identifier
            error_message: Error description
            
        Returns:
            bool: True if sheet was updated
        """
        query = """
            UPDATE omr_sheets 
            SET status = ?, error_message = ?
            WHERE id = ?
        """
        cursor = self._execute(query, (
            SheetStatus.FAILED.value,
            error_message,
            sheet_id
        ))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def update_status(self, sheet_id: str, status: SheetStatus) -> bool:
        """
        Update sheet status
        
        Args:
            sheet_id: Sheet identifier
            status: New sheet status
            
        Returns:
            bool: True if sheet was updated
        """
        query = """
            UPDATE omr_sheets 
            SET status = ?
            WHERE id = ?
        """
        cursor = self._execute(query, (status.value, sheet_id))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def delete(self, sheet_id: str) -> bool:
        """
        Delete an OMR sheet
        
        Args:
            sheet_id: Sheet identifier
            
        Returns:
            bool: True if sheet was deleted
        """
        query = "DELETE FROM omr_sheets WHERE id = ?"
        cursor = self._execute(query, (sheet_id,))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def delete_by_job(self, job_id: str) -> int:
        """
        Delete all sheets for a job
        
        Args:
            job_id: Parsing job identifier
            
        Returns:
            int: Number of sheets deleted
        """
        query = "DELETE FROM omr_sheets WHERE parsing_job_id = ?"
        cursor = self._execute(query, (job_id,))
        self.connection.commit()
        return cursor.rowcount
    
    def _row_to_sheet(self, row) -> OMRSheet:
        """
        Convert database row to OMRSheet model
        
        Args:
            row: SQLite row object
            
        Returns:
            OMRSheet: OMRSheet model instance
        """
        return OMRSheet(
            id=row['id'],
            parsing_job_id=row['parsing_job_id'],
            image_url=row['image_url'],
            answered_options_json=json.loads(row['answered_options_json']),
            status=SheetStatus(row['status']),
            error_message=row['error_message'],
            created_at=datetime.fromisoformat(row['created_at']),
            parsed_at=datetime.fromisoformat(row['parsed_at']) 
                if row['parsed_at'] else None
        )
