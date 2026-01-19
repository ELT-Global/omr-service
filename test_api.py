#!/usr/bin/env python3
"""
Test script for OMRChecker API

This script tests the /parse-omr endpoint with a sample image.
"""
import requests
import sys
from pathlib import Path

API_URL = "http://localhost:8000"


def test_health_endpoint():
    """Test the health check endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{API_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()
    return response.status_code == 200


def test_parse_omr_endpoint(image_path: str, user_id: str = "test_user_001"):
    """Test the parse-omr endpoint with an image"""
    print(f"Testing /parse-omr endpoint with image: {image_path}")
    
    if not Path(image_path).exists():
        print(f"Error: Image file not found: {image_path}")
        return False
    
    with open(image_path, 'rb') as img_file:
        files = {"image": img_file}
        data = {"userId": user_id}
        
        response = requests.post(f"{API_URL}/parse-omr", files=files, data=data)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"User ID: {result['id']}")
            print(f"Multi-marked count: {result['multi_marked_count']}")
            print(f"Detected answers:")
            for key, value in result['answers'].items():
                print(f"  {key}: {value}")
            print()
            return True
        else:
            print(f"Error: {response.text}")
            print()
            return False


def main():
    """Main test function"""
    print("=" * 60)
    print("OMRChecker API Test Script")
    print("=" * 60)
    print()
    
    # Test health endpoint
    if not test_health_endpoint():
        print("Health check failed!")
        sys.exit(1)
    
    # Find a sample image to test
    sample_dir = Path(__file__).parent / "samples" / "sample1" / "MobileCamera"
    
    if not sample_dir.exists():
        print(f"Sample directory not found: {sample_dir}")
        print("Please provide an image path as argument:")
        print(f"  python test_api.py /path/to/omr-image.jpg")
        sys.exit(1)
    
    # Get first image from sample directory
    image_files = list(sample_dir.glob("*.jpg")) + list(sample_dir.glob("*.png"))
    
    if not image_files:
        print(f"No images found in {sample_dir}")
        sys.exit(1)
    
    # Test with the first image
    test_image = image_files[0]
    if test_parse_omr_endpoint(str(test_image)):
        print("✓ API test successful!")
    else:
        print("✗ API test failed!")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Use provided image path
        test_parse_omr_endpoint(sys.argv[1])
    else:
        main()
