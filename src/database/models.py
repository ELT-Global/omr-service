"""
Data models for database entities
Defines dataclasses and enums for type-safe database operations
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class JobStatus(Enum):
    """Status of a parsing job"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CallbackStatus(Enum):
    """Status of webhook callback for a job"""
    NOT_SENT = "NOT_SENT"
    SENT = "SENT"
    FAILED = "FAILED"


class SheetStatus(Enum):
    """Status of an individual OMR sheet"""
    PENDING = "PENDING"
    PARSED = "PARSED"
    FAILED = "FAILED"


@dataclass
class Operator:
    """
    Operator (API user) model
    
    Attributes:
        id: Unique operator identifier
        uuid: Authentication token (UUID)
        webhook_url: URL for webhook callbacks
        created_at: Registration timestamp
    """
    id: str
    uuid: str
    webhook_url: str
    created_at: datetime


@dataclass
class ParsingJob:
    """
    Parsing job model
    
    Represents a batch of OMR sheets to be processed.
    
    Attributes:
        id: Unique job identifier
        operator_id: Foreign key to operators table
        status: Current job status
        total_sheets: Total number of sheets in job
        processed_sheets: Number of sheets processed so far
        callback_status: Status of webhook callback
        created_at: Job creation timestamp
        completed_at: Job completion timestamp (nullable)
    """
    id: str
    operator_id: str
    status: JobStatus
    total_sheets: int
    processed_sheets: int
    callback_status: CallbackStatus
    created_at: datetime
    completed_at: Optional[datetime] = None


@dataclass
class OMRSheet:
    """
    OMR sheet model
    
    Represents a single OMR sheet to be processed.
    
    Attributes:
        id: Unique sheet identifier
        parsing_job_id: Foreign key to parsing_jobs table
        image_url: URL or path to sheet image
        answered_options_json: Parsed answers as JSON object
        status: Current sheet status
        created_at: Sheet creation timestamp
        error_message: Error details if parsing failed (nullable)
        parsed_at: Parsing completion timestamp (nullable)
    """
    id: str
    parsing_job_id: str
    image_url: str
    answered_options_json: Dict[str, Any]
    status: SheetStatus
    created_at: datetime
    error_message: Optional[str] = None
    parsed_at: Optional[datetime] = None
