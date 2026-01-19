"""
Database Usage Examples
Demonstrates how to use the database layer with repository pattern

Run this file to see the database in action:
    python examples/database_usage.py
"""

import uuid
from datetime import datetime

from src.database import db_connection, DatabaseSchema, UnitOfWork
from src.database.models import (
    Operator, ParsingJob, OMRSheet,
    JobStatus, CallbackStatus, SheetStatus
)


def initialize_database():
    """Initialize the database schema"""
    print("Initializing database...")
    conn = db_connection.get_connection()
    DatabaseSchema.initialize_database(conn)
    print("✓ Database initialized\n")


def example_basic_operations():
    """Example: Basic CRUD operations"""
    print("=" * 60)
    print("EXAMPLE 1: Basic CRUD Operations")
    print("=" * 60)
    
    # Create operator
    uow = UnitOfWork()
    
    operator = Operator(
        id=str(uuid.uuid4()),
        uuid=str(uuid.uuid4()),
        webhook_url="https://example.com/webhook",
        created_at=datetime.now()
    )
    
    uow.operators.create(operator)
    print(f"✓ Created operator: {operator.id}")
    
    # Find operator by UUID
    found = uow.operators.find_by_uuid(operator.uuid)
    print(f"✓ Found operator by UUID: {found.webhook_url}")
    
    # Update operator
    found.webhook_url = "https://example.com/new-webhook"
    uow.operators.update(found)
    print(f"✓ Updated operator webhook URL")
    
    # List all operators
    all_operators = uow.operators.find_all()
    print(f"✓ Total operators: {len(all_operators)}\n")
    
    return operator


def example_transaction_management(operator: Operator):
    """Example: Using transactions"""
    print("=" * 60)
    print("EXAMPLE 2: Transaction Management")
    print("=" * 60)
    
    uow = UnitOfWork()
    
    # Transaction: Create job and multiple sheets atomically
    with uow.transaction():
        # Create parsing job
        job = ParsingJob(
            id=str(uuid.uuid4()),
            operator_id=operator.id,
            status=JobStatus.PENDING,
            total_sheets=3,
            processed_sheets=0,
            callback_status=CallbackStatus.NOT_SENT,
            created_at=datetime.now()
        )
        uow.parsing_jobs.create(job)
        print(f"✓ Created parsing job: {job.id}")
        
        # Create multiple sheets
        for i in range(3):
            sheet = OMRSheet(
                id=str(uuid.uuid4()),
                parsing_job_id=job.id,
                image_url=f"https://example.com/sheet{i+1}.jpg",
                answered_options_json={"answers": []},
                status=SheetStatus.PENDING,
                created_at=datetime.now()
            )
            uow.omr_sheets.create(sheet)
        
        print(f"✓ Created 3 OMR sheets")
    
    print("✓ Transaction committed successfully\n")
    return job


def example_querying_data(job: ParsingJob):
    """Example: Querying and filtering data"""
    print("=" * 60)
    print("EXAMPLE 3: Querying and Filtering")
    print("=" * 60)
    
    uow = UnitOfWork()
    
    # Find all sheets for a job
    sheets = uow.omr_sheets.find_by_job(job.id)
    print(f"✓ Found {len(sheets)} sheets for job {job.id}")
    
    # Find pending sheets
    pending_sheets = uow.omr_sheets.find_by_job_and_status(job.id, SheetStatus.PENDING)
    print(f"✓ Pending sheets: {len(pending_sheets)}")
    
    # Find jobs by operator
    jobs = uow.parsing_jobs.find_by_operator(job.operator_id)
    print(f"✓ Jobs for operator: {len(jobs)}")
    
    # Find jobs by status
    pending_jobs = uow.parsing_jobs.find_by_status(JobStatus.PENDING)
    print(f"✓ Pending jobs: {len(pending_jobs)}\n")
    
    return sheets[0] if sheets else None


def example_updating_job_progress(job: ParsingJob, sheet: OMRSheet):
    """Example: Updating job progress"""
    print("=" * 60)
    print("EXAMPLE 4: Updating Job Progress")
    print("=" * 60)
    
    uow = UnitOfWork()
    
    # Start processing
    uow.parsing_jobs.update_status(job.id, JobStatus.PROCESSING)
    print(f"✓ Job status: PROCESSING")
    
    # Parse a sheet
    parsed_answers = {
        "Q1": "A",
        "Q2": "B",
        "Q3": "C"
    }
    uow.omr_sheets.update_parsed(sheet.id, parsed_answers, datetime.now())
    print(f"✓ Sheet parsed: {sheet.id}")
    
    # Update progress
    uow.parsing_jobs.increment_progress(job.id)
    print(f"✓ Job progress incremented")
    
    # Check progress
    updated_job = uow.parsing_jobs.find_by_id(job.id)
    print(f"✓ Progress: {updated_job.processed_sheets}/{updated_job.total_sheets}")
    
    # Complete job
    if updated_job.processed_sheets >= updated_job.total_sheets:
        uow.parsing_jobs.update_status(
            job.id, 
            JobStatus.COMPLETED, 
            datetime.now()
        )
        print(f"✓ Job completed\n")


def example_error_handling(operator: Operator):
    """Example: Error handling with transactions"""
    print("=" * 60)
    print("EXAMPLE 5: Error Handling")
    print("=" * 60)
    
    uow = UnitOfWork()
    
    try:
        with uow.transaction():
            job = ParsingJob(
                id=str(uuid.uuid4()),
                operator_id=operator.id,
                status=JobStatus.PROCESSING,
                total_sheets=1,
                processed_sheets=0,
                callback_status=CallbackStatus.NOT_SENT,
                created_at=datetime.now()
            )
            uow.parsing_jobs.create(job)
            print(f"✓ Created job: {job.id}")
            
            sheet = OMRSheet(
                id=str(uuid.uuid4()),
                parsing_job_id=job.id,
                image_url="https://example.com/failed-sheet.jpg",
                answered_options_json={"answers": []},
                status=SheetStatus.PENDING,
                created_at=datetime.now()
            )
            uow.omr_sheets.create(sheet)
            
            # Simulate parsing failure
            uow.omr_sheets.update_failed(sheet.id, "Image quality too low")
            print(f"✓ Sheet marked as failed")
            
            # Update job status
            uow.parsing_jobs.update_status(job.id, JobStatus.FAILED, datetime.now())
            print(f"✓ Job marked as failed")
    
    except Exception as e:
        print(f"✗ Transaction rolled back: {e}")
    
    print("✓ Error handling completed\n")


def example_statistics():
    """Example: Getting statistics"""
    print("=" * 60)
    print("EXAMPLE 6: Statistics")
    print("=" * 60)
    
    uow = UnitOfWork()
    
    # Count operators
    operators = uow.operators.find_all()
    print(f"✓ Total operators: {len(operators)}")
    
    # Count jobs by status
    for status in JobStatus:
        jobs = uow.parsing_jobs.find_by_status(status)
        print(f"  - {status.value} jobs: {len(jobs)}")
    
    # Find pending callbacks
    pending_callbacks = uow.parsing_jobs.find_pending_callbacks()
    print(f"✓ Jobs with pending callbacks: {len(pending_callbacks)}\n")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("DATABASE USAGE EXAMPLES")
    print("=" * 60 + "\n")
    
    # Initialize database
    initialize_database()
    
    # Run examples
    operator = example_basic_operations()
    job = example_transaction_management(operator)
    sheet = example_querying_data(job)
    if sheet:
        example_updating_job_progress(job, sheet)
    example_error_handling(operator)
    example_statistics()
    
    print("=" * 60)
    print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
    print("=" * 60 + "\n")
    
    print("Database file: omr_checker.db")
    print("You can inspect it with: sqlite3 omr_checker.db")


if __name__ == "__main__":
    main()
