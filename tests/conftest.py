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
from flask import Flask
import pytest # Make sure pytest is imported

# Add the project root directory to the Python path
project_root = Path(__file__).parent.resolve()
src_dir = project_root / ".." / "src"
sys.path.insert(0, str(src_dir))

# Optional: Add any pytest fixtures here that should be available across all test files

@pytest.fixture(scope="session")
def app_context(test_database_url: str):
    """Provides a Flask application context for tests.

    This fixture sets up a minimal Flask app and pushes an application context,
    ensuring that `current_app` is available and configured with the test database URL.
    """
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["DATABASE_URL"] = test_database_url

    with app.app_context():
        yield app

