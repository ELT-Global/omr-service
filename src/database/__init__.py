"""
Database module for OMRChecker
Provides SQLite database connection, schema management, and repository pattern implementation
"""

from .connection import db_connection, DatabaseConnection
from .schema import DatabaseSchema
from .unit_of_work import UnitOfWork

__all__ = [
    'db_connection',
    'DatabaseConnection',
    'DatabaseSchema',
    'UnitOfWork',
]
