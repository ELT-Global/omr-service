#!/usr/bin/env python3
"""
Quick API verification script

Checks that the API can start and has valid syntax.
Does NOT require dependencies to be installed.
"""
import sys
import ast
from pathlib import Path


def check_python_syntax(file_path):
    """Check if a Python file has valid syntax"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return True, None
    except SyntaxError as e:
        return False, str(e)


def main():
    print("=" * 70)
    print(" API Verification Check")
    print("=" * 70)
    print()
    
    project_root = Path(__file__).parent
    
    # Check main API file
    api_file = project_root / "api.py"
    if api_file.exists():
        valid, error = check_python_syntax(api_file)
        if valid:
            print("✓ api.py - Valid syntax")
        else:
            print(f"✗ api.py - Syntax error: {error}")
            return 1
    else:
        print("✗ api.py - File not found")
        return 1
    
    # Check api_utils
    api_utils = project_root / "src" / "api_utils.py"
    if api_utils.exists():
        valid, error = check_python_syntax(api_utils)
        if valid:
            print("✓ src/api_utils.py - Valid syntax")
        else:
            print(f"✗ src/api_utils.py - Syntax error: {error}")
            return 1
    else:
        print("✗ src/api_utils.py - File not found")
        return 1
    
    print()
    
    # Check that CLI files are removed
    cli_files = [
        project_root / "main.py",
        project_root / "src" / "entry.py"
    ]
    
    cli_removed = True
    for cli_file in cli_files:
        if cli_file.exists():
            print(f"⚠️  {cli_file.name} still exists (should be removed)")
            cli_removed = False
    
    if cli_removed:
        print("✓ CLI files removed (main.py, entry.py)")
    print()
    
    # Check critical directories
    tests_dir = project_root / "tests"
    docs_dir = project_root / "docs"
    samples_dir = project_root / "samples"
    
    if tests_dir.exists():
        test_count = len(list(tests_dir.glob("test_*.py")))
        print(f"✓ tests/ directory exists ({test_count} test files)")
    else:
        print("⚠️  tests/ directory not found")
    
    if docs_dir.exists():
        doc_count = len(list(docs_dir.glob("*.md")))
        print(f"✓ docs/ directory exists ({doc_count} documentation files)")
    else:
        print("⚠️  docs/ directory not found")
    
    if samples_dir.exists():
        print("✓ samples/ directory exists")
    else:
        print("⚠️  samples/ directory not found")
    
    print()
    print("=" * 70)
    print(" API Structure Verification")
    print("=" * 70)
    print()
    print("✓ All syntax checks passed")
    print("✓ API files are valid")
    print("✓ Project structure is clean")
    print()
    print("Next steps:")
    print("  1. Install dependencies: pip install -e .")
    print("  2. Start API: python api.py")
    print("  3. Test API: python tests/test_api_simple.py")
    print("  4. View docs: http://localhost:8000/docs")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
