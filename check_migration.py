#!/usr/bin/env python3
"""
Migration helper script for OMR Service reorganization

This script helps migrate from the old project structure to the new one.
"""
import os
import sys
from pathlib import Path


def main():
    print("=" * 70)
    print(" OMR Service - Migration Check")
    print("=" * 70)
    print()
    
    project_root = Path(__file__).parent
    
    # Check if old test files exist in root
    old_test_files = list(project_root.glob("test_*.py"))
    if old_test_files:
        print("⚠️  Found test files in root directory:")
        for f in old_test_files:
            print(f"   - {f.name}")
        print("\n   These should be moved to tests/ directory")
        print("   Run: Move-Item test_*.py tests/")
        print()
    else:
        print("✅ No test files in root (already migrated)")
        print()
    
    # Check tests directory
    tests_dir = project_root / "tests"
    if tests_dir.exists():
        test_count = len(list(tests_dir.glob("test_*.py")))
        print(f"✅ tests/ directory exists with {test_count} test files")
    else:
        print("⚠️  tests/ directory not found")
        print("   Run: mkdir tests")
    print()
    
    # Check docs directory
    docs_dir = project_root / "docs"
    if docs_dir.exists():
        doc_count = len(list(docs_dir.glob("*.md")))
        print(f"✅ docs/ directory exists with {doc_count} documentation files")
    else:
        print("⚠️  docs/ directory not found")
    print()
    
    # Check pyproject.toml
    pyproject_file = project_root / "pyproject.toml"
    if pyproject_file.exists():
        content = pyproject_file.read_text()
        if "[project]" in content:
            print("✅ pyproject.toml configured with dependencies")
        else:
            print("⚠️  pyproject.toml exists but not configured")
            print("   Need to add [project] section with dependencies")
    else:
        print("❌ pyproject.toml not found")
    print()
    
    # Check for duplicate api files
    api_files = list(project_root.glob("api*.py"))
    api_files = [f for f in api_files if f.name != "api_utils.py"]
    if len(api_files) > 1:
        print("⚠️  Multiple API files found:")
        for f in api_files:
            print(f"   - {f.name}")
        print("   You should only have api.py")
    else:
        print("✅ Only one API file (api.py)")
    print()
    
    # Installation recommendation
    print("=" * 70)
    print(" Recommended Installation")
    print("=" * 70)
    print()
    print("New way (recommended):")
    print("  pip install -e .")
    print()
    print("Old way (still works):")
    print("  pip install -r requirements.txt")
    print()
    
    # Summary
    print("=" * 70)
    print(" Summary")
    print("=" * 70)
    print()
    print("The project has been reorganized for better structure:")
    print("  • Tests moved to tests/ directory")
    print("  • Documentation organized in docs/")
    print("  • Dependencies managed via pyproject.toml")
    print("  • Removed duplicate files")
    print()
    print("For full details, see REORGANIZATION.md")
    print()


if __name__ == "__main__":
    main()
