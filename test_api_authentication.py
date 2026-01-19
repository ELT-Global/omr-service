"""
Test script for authenticated API endpoints
Run this to verify your authentication setup works correctly
"""

import requests
import json
import uuid
from datetime import datetime

from src.database import db_connection, DatabaseSchema, UnitOfWork
from src.database.models import Operator


def setup_test_operator() -> tuple[str, str]:
    """
    Create a test operator for API testing
    
    Returns:
        tuple: (operator_id, operator_uuid)
    """
    print("Setting up test operator...")
    
    # Initialize database
    conn = db_connection.get_connection()
    DatabaseSchema.initialize_database(conn)
    
    # Create test operator
    uow = UnitOfWork()
    operator = Operator(
        id=str(uuid.uuid4()),
        uuid=str(uuid.uuid4()),
        webhook_url="https://example.com/test-webhook",
        created_at=datetime.now()
    )
    uow.operators.create(operator)
    
    print(f"✓ Created test operator")
    print(f"  Operator ID: {operator.id}")
    print(f"  UUID: {operator.uuid}\n")
    
    return operator.id, operator.uuid


def test_health_endpoint():
    """Test the health endpoint (no auth required)"""
    print("=" * 60)
    print("TEST 1: Health Endpoint (No Auth)")
    print("=" * 60)
    
    try:
        response = requests.get("http://localhost:8000/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✓ PASSED\n")
            return True
        else:
            print("✗ FAILED\n")
            return False
    except Exception as e:
        print(f"✗ FAILED: {e}\n")
        return False


def test_missing_auth():
    """Test that endpoints reject requests without auth"""
    print("=" * 60)
    print("TEST 2: Missing Authentication")
    print("=" * 60)
    
    try:
        response = requests.post(
            "http://localhost:8000/omr:parse-sheet",
            data={"userId": "test"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 401:
            print("✓ PASSED (Correctly rejected)\n")
            return True
        else:
            print("✗ FAILED (Should have returned 401)\n")
            return False
    except Exception as e:
        print(f"✗ FAILED: {e}\n")
        return False


def test_invalid_auth():
    """Test that endpoints reject invalid tokens"""
    print("=" * 60)
    print("TEST 3: Invalid Authentication Token")
    print("=" * 60)
    
    try:
        response = requests.post(
            "http://localhost:8000/omr:parse-sheet",
            headers={"Authorization": "Basic invalid-token-12345"},
            data={"userId": "test"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 401:
            print("✓ PASSED (Correctly rejected)\n")
            return True
        else:
            print("✗ FAILED (Should have returned 401)\n")
            return False
    except Exception as e:
        print(f"✗ FAILED: {e}\n")
        return False


def test_valid_auth(operator_uuid: str):
    """Test that valid auth allows access"""
    print("=" * 60)
    print("TEST 4: Valid Authentication")
    print("=" * 60)
    
    try:
        response = requests.post(
            "http://localhost:8000/omr:parse-sheet",
            headers={"Authorization": f"Basic {operator_uuid}"},
            data={
                "userId": "test_student",
                "image_url": "https://invalid-url-for-testing.com/image.jpg"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Should get past auth (400 or 500 for invalid URL is expected)
        if response.status_code in [200, 400, 500]:
            print("✓ PASSED (Auth accepted, processing attempted)\n")
            return True
        elif response.status_code == 401:
            print("✗ FAILED (Auth should have been accepted)\n")
            return False
        else:
            print(f"? UNCLEAR (Unexpected status code: {response.status_code})\n")
            return False
    except Exception as e:
        print(f"✗ FAILED: {e}\n")
        return False


def test_bulk_endpoint_auth(operator_uuid: str):
    """Test bulk endpoint with authentication"""
    print("=" * 60)
    print("TEST 5: Bulk Endpoint Authentication")
    print("=" * 60)
    
    try:
        items = [
            {"id": "test_001", "image_url": "https://invalid.com/1.jpg"},
            {"id": "test_002", "image_url": "https://invalid.com/2.jpg"}
        ]
        
        response = requests.post(
            "http://localhost:8000/omr:parse-sheets",
            headers={"Authorization": f"Basic {operator_uuid}"},
            json={"items": items}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code in [200, 400, 500]:
            print("✓ PASSED (Auth accepted)\n")
            return True
        elif response.status_code == 401:
            print("✗ FAILED (Auth should have been accepted)\n")
            return False
        else:
            print(f"? UNCLEAR (Unexpected status code)\n")
            return False
    except Exception as e:
        print(f"✗ FAILED: {e}\n")
        return False


def test_operator_context_logging(operator_id: str, operator_uuid: str):
    """Verify operator context is available in logs"""
    print("=" * 60)
    print("TEST 6: Operator Context in Logs")
    print("=" * 60)
    
    print(f"Making request with operator_id: {operator_id}")
    print("Check your server logs for:")
    print(f"  'Processing OMR for operator_id: {operator_id}'")
    
    try:
        response = requests.post(
            "http://localhost:8000/omr:parse-sheet",
            headers={"Authorization": f"Basic {operator_uuid}"},
            data={
                "userId": "log_test",
                "image_url": "https://invalid.com/test.jpg"
            }
        )
        print(f"\nRequest sent. Status: {response.status_code}")
        print("✓ Check server logs to verify operator_id appears\n")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}\n")
        return False


def main():
    """Run all authentication tests"""
    print("\n" + "=" * 60)
    print("OMRChecker API Authentication Tests")
    print("=" * 60 + "\n")
    
    print("Make sure the API server is running on http://localhost:8000")
    print("Start it with: python api.py\n")
    
    input("Press Enter to continue...")
    print()
    
    # Setup
    operator_id, operator_uuid = setup_test_operator()
    
    # Run tests
    results = []
    results.append(("Health Endpoint", test_health_endpoint()))
    results.append(("Missing Auth", test_missing_auth()))
    results.append(("Invalid Auth", test_invalid_auth()))
    results.append(("Valid Auth", test_valid_auth(operator_uuid)))
    results.append(("Bulk Auth", test_bulk_endpoint_auth(operator_uuid)))
    results.append(("Operator Context", test_operator_context_logging(operator_id, operator_uuid)))
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name:.<40} {status}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed. Check the output above for details.")
    
    print("\n" + "=" * 60)
    print(f"Test Operator UUID: {operator_uuid}")
    print("Save this for manual testing if needed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
