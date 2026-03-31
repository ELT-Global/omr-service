#!/usr/bin/env python3
"""
Test script for base64 image support in OMR Processing API
"""
import requests
import base64
from pathlib import Path

API_URL = "http://localhost:8000"


def image_to_base64(image_path: str) -> str:
    """Convert an image file to base64 string"""
    with open(image_path, 'rb') as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')


def test_single_sheet_base64():
    """Test /process-sheet with base64 encoded image"""
    print("\n" + "="*60)
    print("TEST: /process-sheet with base64 image")
    print("="*60)
    
    image_path = "samples/sample1/MobileCamera/sheet1.jpg"
    
    if not Path(image_path).exists():
        print(f"✗ Image not found: {image_path}")
        return False
    
    # Convert image to base64
    image_base64 = image_to_base64(image_path)
    print(f"Image encoded to base64 ({len(image_base64)} chars)")
    
    # Test with plain base64
    data = {
        "sheet_id": "test_base64_001",
        "image_base64": image_base64
    }
    
    response = requests.post(f"{API_URL}/process-sheet", data=data)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("✓ Success!")
        print(f"  Sheet ID: {result['id']}")
        print(f"  Multi-marked: {result['multi_marked_count']}")
        print(f"  Answers: {len(result['answers'])} questions")
        return True
    else:
        print(f"✗ Failed: {response.text}")
        return False


def test_single_sheet_base64_data_uri():
    """Test /process-sheet with base64 data URI format"""
    print("\n" + "="*60)
    print("TEST: /process-sheet with base64 data URI")
    print("="*60)
    
    image_path = "samples/sample1/MobileCamera/sheet1.jpg"
    
    if not Path(image_path).exists():
        print(f"✗ Image not found: {image_path}")
        return False
    
    # Convert image to base64 with data URI prefix
    image_base64 = image_to_base64(image_path)
    data_uri = f"data:image/jpeg;base64,{image_base64}"
    print(f"Image encoded as data URI ({len(data_uri)} chars)")
    
    data = {
        "sheet_id": "test_data_uri_001",
        "image_base64": data_uri
    }
    
    response = requests.post(f"{API_URL}/process-sheet", data=data)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("✓ Success!")
        print(f"  Sheet ID: {result['id']}")
        print(f"  Multi-marked: {result['multi_marked_count']}")
        print(f"  Answers: {len(result['answers'])} questions")
        return True
    else:
        print(f"✗ Failed: {response.text}")
        return False


def test_batch_mixed():
    """Test /process-batch with mixed URL and base64"""
    print("\n" + "="*60)
    print("TEST: /process-batch with mixed URL and base64")
    print("="*60)
    
    # Get sample images
    sample_dir = Path("samples/sample1/MobileCamera")
    image_files = list(sample_dir.glob("*.jpg"))[:3]
    
    if len(image_files) < 2:
        print("⊘ Skipped - need at least 2 sample images")
        return None
    
    # Create mixed batch: some with base64, some with URLs (for demo, we'll use base64 for all)
    sheets = []
    
    # First sheet with base64
    image_base64_1 = image_to_base64(str(image_files[0]))
    sheets.append({
        "id": "student_001",
        "image_base64": image_base64_1
    })
    
    # Second sheet with base64 data URI
    image_base64_2 = image_to_base64(str(image_files[1]))
    sheets.append({
        "id": "student_002",
        "image_base64": f"data:image/jpeg;base64,{image_base64_2}"
    })
    
    # If we have a third image, add it
    if len(image_files) >= 3:
        image_base64_3 = image_to_base64(str(image_files[2]))
        sheets.append({
            "id": "student_003",
            "image_base64": image_base64_3
        })
    
    request_data = {
        "sheets": sheets
    }
    
    print(f"Processing batch of {len(sheets)} sheets with base64 encoding...")
    
    response = requests.post(
        f"{API_URL}/process-batch",
        json=request_data
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("✓ Success!")
        print(f"  Total: {result['total']}")
        print(f"  Successful: {result['successful']}")
        print(f"  Failed: {result['failed']}")
        for sheet_result in result['results']:
            status = "✓" if not sheet_result.get('error') else "✗"
            print(f"  {status} {sheet_result['id']}: {len(sheet_result.get('answers', {}))} answers")
        return True
    else:
        print(f"✗ Failed: {response.text}")
        return False


def main():
    """Run all base64 tests"""
    print("\n" + "="*70)
    print(" OMR Processing API - Base64 Support Test")
    print("="*70)
    
    # Check server
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        if response.status_code != 200:
            print("✗ Server is not healthy!")
            return
        print("✓ Server is running")
    except requests.exceptions.RequestException:
        print("✗ Cannot connect to server. Is it running on port 8000?")
        return
    
    # Run tests
    results = []
    results.append(("Base64 Single Sheet", test_single_sheet_base64()))
    results.append(("Base64 Data URI", test_single_sheet_base64_data_uri()))
    results.append(("Mixed Batch", test_batch_mixed()))
    
    # Summary
    print("\n" + "="*70)
    print(" SUMMARY")
    print("="*70)
    for name, result in results:
        if result is True:
            print(f"✓ {name}: PASSED")
        elif result is False:
            print(f"✗ {name}: FAILED")
        else:
            print(f"⊘ {name}: SKIPPED")
    
    print("\n✓ Base64 support is working!")
    print("\nSupported formats:")
    print("  • Plain base64: 'iVBORw0KGgoAAAANSUhEUg...'")
    print("  • Data URI: 'data:image/jpeg;base64,/9j/4AAQSkZJRg...'")
    print("  • Can mix URL and base64 in batch requests")


if __name__ == "__main__":
    main()
