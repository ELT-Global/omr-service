"""
Operator repository
Handles database operations for operators (API users)
"""

from typing import Optional, List
from datetime import datetime
from .base import BaseRepository
from ..models import Operator


class OperatorRepository(BaseRepository):
    """
    Repository for operator (API user) operations
    
    Provides CRUD operations and queries for the operators table.
    """
    
    def create(self, operator: Operator) -> Operator:
        """
        Create a new operator
        
        Args:
            operator: Operator model instance
            
        Returns:
            Operator: Created operator
        """
        query = """
            INSERT INTO operators (id, uuid, webhook_url, created_at)
            VALUES (?, ?, ?, ?)
        """
        self._execute(query, (
            operator.id,
            operator.uuid,
            operator.webhook_url,
            operator.created_at.isoformat()
        ))
        self.connection.commit()
        return operator
    
    def find_by_id(self, operator_id: str) -> Optional[Operator]:
        """
        Find operator by ID
        
        Args:
            operator_id: Operator identifier
            
        Returns:
            Optional[Operator]: Operator or None if not found
        """
        query = "SELECT * FROM operators WHERE id = ?"
        row = self._fetchone(query, (operator_id,))
        return self._row_to_operator(row) if row else None
    
    def find_by_uuid(self, uuid: str) -> Optional[Operator]:
        """
        Find operator by UUID (auth token)
        
        Args:
            uuid: Operator UUID (authentication token)
            
        Returns:
            Optional[Operator]: Operator or None if not found
        """
        query = "SELECT * FROM operators WHERE uuid = ?"
        row = self._fetchone(query, (uuid,))
        return self._row_to_operator(row) if row else None
    
    def find_all(self) -> List[Operator]:
        """
        Get all operators
        
        Returns:
            List[Operator]: List of all operators, ordered by creation date
        """
        query = "SELECT * FROM operators ORDER BY created_at DESC"
        rows = self._fetchall(query)
        return [self._row_to_operator(row) for row in rows]
    
    def update(self, operator: Operator) -> Operator:
        """
        Update an operator
        
        Args:
            operator: Operator model with updated data
            
        Returns:
            Operator: Updated operator
        """
        query = """
            UPDATE operators 
            SET uuid = ?, webhook_url = ?
            WHERE id = ?
        """
        self._execute(query, (
            operator.uuid,
            operator.webhook_url,
            operator.id
        ))
        self.connection.commit()
        return operator
    
    def delete(self, operator_id: str) -> bool:
        """
        Delete an operator
        
        Args:
            operator_id: Operator identifier
            
        Returns:
            bool: True if operator was deleted, False if not found
        """
        query = "DELETE FROM operators WHERE id = ?"
        cursor = self._execute(query, (operator_id,))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def exists(self, operator_id: str) -> bool:
        """
        Check if operator exists
        
        Args:
            operator_id: Operator identifier
            
        Returns:
            bool: True if operator exists
        """
        query = "SELECT 1 FROM operators WHERE id = ? LIMIT 1"
        row = self._fetchone(query, (operator_id,))
        return row is not None
    
    def _row_to_operator(self, row) -> Operator:
        """
        Convert database row to Operator model
        
        Args:
            row: SQLite row object
            
        Returns:
            Operator: Operator model instance
        """
        return Operator(
            id=row['id'],
            uuid=row['uuid'],
            webhook_url=row['webhook_url'],
            created_at=datetime.fromisoformat(row['created_at'])
        )
