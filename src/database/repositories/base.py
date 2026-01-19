"""
Base repository class
Provides common database operations for all repositories
"""

from abc import ABC
from typing import Optional, List
import sqlite3


class BaseRepository(ABC):
    """
    Base repository with common database operations
    
    All repository classes should inherit from this base class
    to get common query execution methods.
    """
    
    def __init__(self, connection: sqlite3.Connection):
        """
        Initialize repository with database connection
        
        Args:
            connection: SQLite database connection
        """
        self.connection = connection
    
    def _execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a query and return cursor
        
        Args:
            query: SQL query string
            params: Query parameters tuple
            
        Returns:
            sqlite3.Cursor: Database cursor
        """
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor
    
    def _fetchone(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """
        Execute query and fetch one row
        
        Args:
            query: SQL query string
            params: Query parameters tuple
            
        Returns:
            Optional[sqlite3.Row]: Single row or None
        """
        cursor = self._execute(query, params)
        return cursor.fetchone()
    
    def _fetchall(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """
        Execute query and fetch all rows
        
        Args:
            query: SQL query string
            params: Query parameters tuple
            
        Returns:
            List[sqlite3.Row]: List of rows
        """
        cursor = self._execute(query, params)
        return cursor.fetchall()
