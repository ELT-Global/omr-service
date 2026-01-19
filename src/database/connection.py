"""
Database connection management
Provides thread-safe SQLite connection handling with transaction support
"""

import sqlite3
from contextlib import contextmanager
from typing import Generator
import threading


class DatabaseConnection:
    """
    Thread-safe database connection manager for SQLite
    
    Each thread gets its own connection to avoid threading issues.
    Provides transaction management through context managers.
    """
    
    def __init__(self, db_path: str = "omr_checker.db"):
        """
        Initialize database connection manager
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get or create a connection for the current thread
        
        Returns:
            sqlite3.Connection: Database connection for current thread
        """
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database transactions
        
        Automatically commits on success or rolls back on exception.
        
        Yields:
            sqlite3.Connection: Database connection
            
        Example:
            with db_connection.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO table VALUES (?)", (value,))
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def close(self):
        """Close the connection for the current thread"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')


# Singleton instance for application-wide use
db_connection = DatabaseConnection()
