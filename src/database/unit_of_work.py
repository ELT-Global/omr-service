"""
Unit of Work pattern implementation
Provides transaction management across multiple repositories
"""

from contextlib import contextmanager
from typing import Generator
from .connection import db_connection, DatabaseConnection
from .repositories.operator_repository import OperatorRepository
from .repositories.parsing_job_repository import ParsingJobRepository
from .repositories.omr_sheet_repository import OMRSheetRepository


class UnitOfWork:
    """
    Unit of Work pattern for managing transactions across repositories
    
    Provides centralized access to all repositories and transaction management.
    Ensures that all database operations within a transaction are committed or 
    rolled back together.
    
    Example:
        # Using context manager (recommended)
        uow = UnitOfWork()
        with uow.transaction():
            operator = uow.operators.create(new_operator)
            job = uow.parsing_jobs.create(new_job)
            # Both committed together or both rolled back on error
        
        # Manual transaction management
        uow = UnitOfWork()
        try:
            operator = uow.operators.create(new_operator)
            job = uow.parsing_jobs.create(new_job)
            uow.commit()
        except Exception:
            uow.rollback()
            raise
    """
    
    def __init__(self, db_conn: DatabaseConnection = None):
        """
        Initialize Unit of Work
        
        Args:
            db_conn: Optional database connection manager (defaults to singleton)
        """
        if db_conn is None:
            db_conn = db_connection
        
        self.connection = db_conn.get_connection()
        
        # Initialize repositories
        self.operators = OperatorRepository(self.connection)
        self.parsing_jobs = ParsingJobRepository(self.connection)
        self.omr_sheets = OMRSheetRepository(self.connection)
    
    def commit(self) -> None:
        """
        Commit the current transaction
        
        Saves all changes made through the repositories.
        """
        self.connection.commit()
    
    def rollback(self) -> None:
        """
        Rollback the current transaction
        
        Discards all changes made through the repositories.
        """
        self.connection.rollback()
    
    @contextmanager
    def transaction(self) -> Generator['UnitOfWork', None, None]:
        """
        Context manager for transactions
        
        Automatically commits on success or rolls back on exception.
        
        Yields:
            UnitOfWork: This instance
            
        Example:
            uow = UnitOfWork()
            with uow.transaction():
                uow.operators.create(operator)
                uow.parsing_jobs.create(job)
        """
        try:
            yield self
            self.commit()
        except Exception:
            self.rollback()
            raise
    
    def close(self) -> None:
        """
        Close the database connection
        
        Note: Usually not needed as the connection is managed by the singleton.
        Only use this if you created a custom DatabaseConnection instance.
        """
        self.connection.close()
