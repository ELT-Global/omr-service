"""
Add a test operator to the database for API testing
Run this script to create an operator with UUID: test-uuid
"""

import sqlite3
from datetime import datetime

from src.database import db_connection, DatabaseSchema

# Database configuration
DB_PATH = "omr_checker.db"
TEST_OPERATOR_ID = "test-operator-3"
TEST_OPERATOR_UUID = "test-uuid1"
TEST_WEBHOOK_URL = "https://whe023c4da039a53c08f.free.beeceptor.com/"


def add_test_operator():
    """Add a test operator to the database"""
    # Initialize database with all tables
    conn = db_connection.get_connection()
    DatabaseSchema.initialize_database(conn)
    
    cursor = conn.cursor()
    
    # Check if test operator already exists
    cursor.execute("SELECT id FROM operators WHERE uuid = ?", (TEST_OPERATOR_UUID,))
    existing = cursor.fetchone()
    
    if existing:
        print(f"✓ Test operator already exists in database")
        print(f"  - Operator ID: {TEST_OPERATOR_ID}")
        print(f"  - UUID (Token): {TEST_OPERATOR_UUID}")
        print(f"  - Webhook URL: {TEST_WEBHOOK_URL}")
    else:
        # Insert test operator
        cursor.execute(
            """
            INSERT INTO operators (id, uuid, webhook_url, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (TEST_OPERATOR_ID, TEST_OPERATOR_UUID, TEST_WEBHOOK_URL, datetime.now())
        )
        conn.commit()
        print(f"✓ Successfully added test operator to database")
        print(f"  - Operator ID: {TEST_OPERATOR_ID}")
        print(f"  - UUID (Token): {TEST_OPERATOR_UUID}")
        print(f"  - Webhook URL: {TEST_WEBHOOK_URL}")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("You can now test the API using:")
    print(f'  Authorization: Basic {TEST_OPERATOR_UUID}')
    print("=" * 60)
    print("\nExample curl command:")
    print(f'''
curl -X POST "http://localhost:8000/omr:parse-sheet" \\
  -H "Authorization: Basic {TEST_OPERATOR_UUID}" \\
  -F "userId=student_001" \\
  -F "image=@path/to/your/image.jpg"
''')


if __name__ == "__main__":
    add_test_operator()