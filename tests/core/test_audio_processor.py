"""
Tests for the (currently minimal) audio_processor.py module.
Since audio_processor.py has no active, testable functions after refactoring,
this test file primarily ensures the module can be imported and
contains fixtures that might be used if functionality is added back.
"""

import pytest

# import os # No longer needed
# import shutil # No longer needed
# import wave # No longer needed
# from unittest.mock import patch, MagicMock, ANY # No longer needed for current state
from sqlalchemy import create_engine
from sqlalchemy.orm import Session  # Session is used by db_session fixture

from src.database.models import (
    Base,
    Project as ProjectModel,  # Required for db setup if tests were to add data
    Recording as RecordingModel,  # Required for db setup
    Sample as SampleModel,  # Required for db setup
)

# Import the module itself to ensure it's importable
try:
    from src.core import audio_processor
except ImportError:
    audio_processor = None  # Fallback if import fails, though it shouldn't

from src.database.utils import (
    init_db as initialize_db_utils,
    get_db as get_db_utils,
    # get_session_local, # Not directly used by fixtures here, get_db_utils is preferred
)


# --- Test Database Fixtures (kept for potential future use) ---
@pytest.fixture(scope="function")
def test_engine():
    """Creates an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    # Base.metadata.create_all(engine) # Handled by initialize_db_utils
    initialize_db_utils(engine_instance=engine)  # Creates tables
    return engine


@pytest.fixture(scope="function")
def db_session(test_engine):
    """
    Creates a new database session for a test, ensuring a clean state.
    Uses the get_db utility from src.database.utils.
    """
    session_generator = get_db_utils(engine_instance=test_engine)
    session = next(session_generator)
    try:
        yield session
    finally:
        session.rollback()  # Ensure clean state
        session.close()


# --- Basic Test ---


def test_audio_processor_module_importable():
    """Checks if the audio_processor module can be imported."""
    assert audio_processor is not None, "src.core.audio_processor module failed to import."
    # Can also check for specific attributes if any are expected, e.g.,
    # assert hasattr(audio_processor, 'some_expected_future_function')


# Placeholder for any future tests if audio_processor.py gets new functions.
# For now, this file is very minimal, reflecting the state of audio_processor.py.

# All previous test functions related to detect_and_slice_recording and get_audio_details,
# and their specific fixtures (like test_project_and_recording, temp_output_dir_for_slicing)
# have been removed as those functions are no longer in audio_processor.py.
