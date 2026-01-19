#!/usr/bin/env python3
"""
Simple test script for OMRChecker API without custom config

This script demonstrates that config.json and template.json are optional.
The API will use the default configuration automatically.
"""
import requests
import sys
from pathlib import Path

API_URL = "http://localhost:8000"


def test_parse_with_defaults(image_path: str, user_id: str = "test_user_001"):
    """
    Test the parse-omr endpoint WITHOUT providing config or template.
    The API will use default config automatically.
    """
    print(f"Testing /parse-omr with default config...")
    print(f"Image: {image_path}")
    print(f"User ID: {user_id}")
    print()
    
    if not Path(image_path).exists():
        print(f"Error: Image file not found: {image_path}")
        return False
    
    with open(image_path, 'rb') as img_file:
        # Notice: We're ONLY sending image and userId
        # No config_json or template_json needed!
        files = {"image": img_file}
        data = {"userId": user_id}
        
        response = requests.post(f"{API_URL}/parse-omr", files=files, data=data)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Success! Using default config/template")
            print(f"\nUser ID: {result['id']}")
            print(f"Multi-marked count: {result['multi_marked_count']}")
            print(f"\nDetected answers:")
            for key, value in result['answers'].items():
                print(f"  {key}: {value}")
            print()
            return True
        else:
            print(f"✗ Error: {response.text}")
            print()
            return False


def main():
    print("=" * 70)
    print("OMRChecker API - Simple Test (Using Default Config)")
    print("=" * 70)
    print()
    print("This test demonstrates that config.json and template.json are OPTIONAL")
    print("The API automatically uses default configuration when not provided.")
    print()
    
    # Find a sample image to test
    sample_dir = Path(__file__).parent / "samples" / "sample1" / "MobileCamera"
    
    if not sample_dir.exists():
        print(f"Sample directory not found: {sample_dir}")
        sys.exit(1)
    
    # Get first image from sample directory
    image_files = list(sample_dir.glob("*.jpg")) + list(sample_dir.glob("*.png"))
    
    if not image_files:
        print(f"No images found in {sample_dir}")
        sys.exit(1)
    
    # Test with the first image - NO config/template provided!
    test_image = image_files[0]
    success = test_parse_with_defaults(str(test_image))
    
    if success:
        print("=" * 70)
        print("✓ Test completed successfully!")
        print("=" * 70)
        print()
        print("Key takeaways:")
        print("  • config_json and template_json are OPTIONAL parameters")
        print("  • When omitted, the API uses default config from samples/sample1/")
        print("  • You can change the default via OMR_DEFAULT_CONFIG_DIR env var")
        print("  • Custom config can be provided per-request when needed")
    else:
        print("✗ Test failed!")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Use provided image path
        test_parse_with_defaults(sys.argv[1])
    else:
        main()
