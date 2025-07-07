"""
Configuration file for pytest.
This file ensures that the src directory is in the Python path when running tests.
"""
import os
import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.resolve()
src_dir = project_root / ".." / "src"
sys.path.insert(0, str(src_dir))

# Optional: Add any pytest fixtures here that should be available across all test files
