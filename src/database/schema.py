"""
Database schema definitions and migration management
Defines all tables and indexes for the OMRChecker database
"""

from typing import List
import sqlite3


class DatabaseSchema:
    """
    Database schema management for OMRChecker
    
    Defines tables:
    - operators: API operators with authentication tokens
    - parsing_jobs: OMR parsing job records
    - omr_sheets: Individual sheet processing records
    """
    
    @staticmethod
    def get_create_tables_sql() -> List[str]:
        """
        Get SQL statements for creating all tables and indexes
        
        Returns:
            List[str]: SQL CREATE statements
        """
        return [
            """
            CREATE TABLE IF NOT EXISTS operators (
                id TEXT PRIMARY KEY,
                uuid TEXT UNIQUE NOT NULL,
                webhook_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS parsing_jobs (
                id TEXT PRIMARY KEY,
                operator_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
                total_sheets INTEGER NOT NULL DEFAULT 0,
                processed_sheets INTEGER NOT NULL DEFAULT 0,
                callback_status TEXT NOT NULL DEFAULT 'NOT_SENT' CHECK(callback_status IN ('NOT_SENT', 'SENT', 'FAILED')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (operator_id) REFERENCES operators(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS omr_sheets (
                id TEXT PRIMARY KEY,
                parsing_job_id TEXT NOT NULL,
                image_url TEXT NOT NULL,
                answered_options_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING', 'PARSED', 'FAILED')),
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                parsed_at TIMESTAMP,
                FOREIGN KEY (parsing_job_id) REFERENCES parsing_jobs(id) ON DELETE CASCADE
            )
            """,
            # Indexes for performance
            """
            CREATE INDEX IF NOT EXISTS idx_parsing_jobs_operator_id 
            ON parsing_jobs(operator_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_parsing_jobs_status 
            ON parsing_jobs(status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_omr_sheets_parsing_job_id 
            ON omr_sheets(parsing_job_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_omr_sheets_status 
            ON omr_sheets(status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_operators_uuid 
            ON operators(uuid)
            """
        ]
    
    @staticmethod
    def initialize_database(connection: sqlite3.Connection) -> None:
        """
        Initialize database with schema
        
        Creates all tables and indexes if they don't exist.
        Safe to call multiple times (idempotent).
        
        Args:
            connection: SQLite database connection
            
        Example:
            from src.database.connection import db_connection
            from src.database.schema import DatabaseSchema
            
            conn = db_connection.get_connection()
            DatabaseSchema.initialize_database(conn)
        """
        cursor = connection.cursor()
        
        # Enable foreign key support
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create tables and indexes
        for sql in DatabaseSchema.get_create_tables_sql():
            cursor.execute(sql)
        
        connection.commit()
    
    @staticmethod
    def drop_all_tables(connection: sqlite3.Connection) -> None:
        """
        Drop all tables from the database
        
        WARNING: This will delete all data. Use only for testing or cleanup.
        
        Args:
            connection: SQLite database connection
        """
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        tables = ['omr_sheets', 'parsing_jobs', 'operators']
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        
        cursor.execute("PRAGMA foreign_keys = ON")
        connection.commit()
