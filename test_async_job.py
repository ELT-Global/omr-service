"""
Test script for async parsing job functionality

This script demonstrates:
1. Creating a parsing job with multiple sheets
2. Checking job status
3. Retrieving detailed results
"""

import requests
import time
import json

# Configuration
BASE_URL = "http://localhost:8000"
OPERATOR_UUID = "test-uuid"  # Replace with your actual operator UUID

# Sample test data
test_items = [
    {
        "id": "sheet_001",
        "image_url": "https://example.com/sheet1.jpg"
    },
    {
        "id": "sheet_002",
        "image_url": "https://example.com/sheet2.jpg"
    },
    {
        "id": "sheet_003",
        "image_url": "https://example.com/sheet3.jpg"
    }
]


def test_async_parsing_job():
    """Test the async parsing job flow"""
    
    print("=" * 60)
    print("Testing Async Parsing Job Flow")
    print("=" * 60)
    
    # Step 1: Create parsing job
    print("\n1. Creating parsing job...")
    
    response = requests.post(
        f"{BASE_URL}/omr:parse-sheets",
        auth=("api", OPERATOR_UUID),
        json={
            "items": test_items
        }
    )
    
    if response.status_code == 200:
        job_data = response.json()
        job_id = job_data['jobId']
        print(f"   ✓ Job created successfully!")
        print(f"   Job ID: {job_id}")
        print(f"   Status: {job_data['status']}")
    else:
        print(f"   ✗ Error: {response.status_code}")
        print(f"   {response.text}")
        return
    
    # Step 2: Check job status (poll every 2 seconds)
    print(f"\n2. Monitoring job progress...")
    
    max_attempts = 30  # 1 minute max
    for attempt in range(max_attempts):
        time.sleep(2)
        
        response = requests.get(
            f"{BASE_URL}/jobs/{job_id}",
            auth=("api", OPERATOR_UUID)
        )
        
        if response.status_code == 200:
            status_data = response.json()
            status = status_data['status']
            processed = status_data['processedSheets']
            total = status_data['totalSheets']
            
            print(f"   [{attempt + 1}] Status: {status} | Progress: {processed}/{total}")
            
            if status in ['COMPLETED', 'FAILED']:
                print(f"\n   ✓ Job {status.lower()}!")
                break
        else:
            print(f"   ✗ Error checking status: {response.status_code}")
            break
    
    # Step 3: Get detailed results
    print(f"\n3. Fetching detailed results...")
    
    response = requests.get(
        f"{BASE_URL}/jobs/{job_id}?include_sheets=true",
        auth=("api", OPERATOR_UUID)
    )
    
    if response.status_code == 200:
        details = response.json()
        print(f"   ✓ Results retrieved!")
        print(f"\n   Summary:")
        print(f"   - Total Sheets: {details['totalSheets']}")
        print(f"   - Successful: {details['successfulSheets']}")
        print(f"   - Failed: {details['failedSheets']}")
        print(f"   - Pending: {details['pendingSheets']}")
        print(f"   - Callback Status: {details['callbackStatus']}")
        
        if details.get('sheets'):
            print(f"\n   Sheet Details:")
            for sheet in details['sheets']:
                print(f"   - {sheet['id']}: {sheet['status']}")
                if sheet.get('error'):
                    print(f"     Error: {sheet['error']}")
    else:
        print(f"   ✗ Error: {response.status_code}")
        print(f"   {response.text}")
    
    # Step 4: List all jobs
    print(f"\n4. Listing all jobs...")
    
    response = requests.get(
        f"{BASE_URL}/jobs",
        auth=("api", OPERATOR_UUID),
        params={"limit": 10}
    )
    
    if response.status_code == 200:
        jobs_data = response.json()
        print(f"   ✓ Found {jobs_data['total']} job(s)")
        for job in jobs_data['jobs'][:3]:  # Show first 3
            print(f"   - {job['jobId']}: {job['status']} ({job['processedSheets']}/{job['totalSheets']})")
    else:
        print(f"   ✗ Error: {response.status_code}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_async_parsing_job()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
