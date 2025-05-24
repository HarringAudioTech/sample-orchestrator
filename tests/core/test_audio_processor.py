"""
Unit tests for the (now minimal) audio_processor module.

This file previously contained tests for `detect_and_slice_recording` and
`get_audio_details`. Since those functions have been removed from
`src/core/audio_processor.py` (presumably because their functionality was
refactored or moved into processing stages like SlicingStage), this test
file will be significantly reduced or cleared.

If there are any new, simple utility functions in `audio_processor.py`
that require testing, those tests would go here. Otherwise, this file
might become empty or be removed if `audio_processor.py` is also removed.
"""

# import os # Unused after removing DUMMY_AUDIO_PATH
# from unittest.mock import patch # Unused

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session # Session is used for type hinting db_session_instance

from src.database.models import Base # Only Base is needed for metadata operations
# Removed imports for ProjectModel, RecordingModel, SampleModel as they are no longer used
from src.database.utils import init_db as initialize_db_utils
from src.database.utils import get_db

# --- Test Database Fixtures ---

@pytest.fixture(scope="function")
def test_engine():
    """
    Creates an in-memory SQLite engine for function-scoped tests.
    Initializes the database schema using this engine.
    """
    engine = create_engine("sqlite:///:memory:")
    # Assuming initialize_db_utils uses the new module-level ENGINE by default,
    # or can accept an engine_instance. The refactored utils.py's init_db
    # takes an optional engine_instance.
    initialize_db_utils(engine_instance=engine)
    return engine

@pytest.fixture(scope="function")
def db_session(test_engine):
    """
    Provides a SQLAlchemy session for function-scoped tests, ensuring it's
    closed after the test. Uses the `test_engine` fixture.
    Handles the StopIteration for the generator correctly.
    """
    # get_db is now a generator that yields a session.
    session_generator = get_db(engine_instance=test_engine)
    db_session_instance: Session = next(session_generator) # Renamed for clarity
    try:
        yield db_session_instance
    finally:
        # The get_db generator is responsible for closing the session.
        # Exhausting the generator ensures its finally block is executed.
        next(session_generator, None)


# --- Potentially Kept Fixtures (if any remaining tests use them) ---

DUMMY_AUDIO_DIR = "tests/fixtures"
DUMMY_AUDIO_FILENAME = "dummy_audio.wav" # Created in previous step
DUMMY_AUDIO_PATH = os.path.join(DUMMY_AUDIO_DIR, DUMMY_AUDIO_FILENAME)

# The fixture `test_project_and_recording` heavily relied on `get_audio_details`.
# If `get_audio_details` is gone, this fixture needs to be removed or simplified
# to not depend on it (e.g., use hardcoded metadata).
# Since all tests using it are being removed, this fixture can also be removed.

# The fixture `temp_output_dir_for_slicing` was for `detect_and_slice_recording`.
# It can be removed.

# --- No tests remain after removing obsolete functionality ---

def test_placeholder_to_keep_file_if_needed():
    """
    A placeholder test. If audio_processor.py is now empty or contains
    no testable public functions, this test file might be removed or
    this placeholder can confirm the (empty) state.
    """
    # This test now primarily serves to ensure the test file itself remains valid
    # and that the audio_processor module (if it still exists) is minimal.
    try:
        # Attempt to import the module
        # pylint: disable=import-outside-toplevel
        import src.core.audio_processor as audio_processor_module
        # pylint: enable=import-outside-toplevel

        # If the module exists, check if it's empty of the old functions.
        # This is an indirect way to test that refactoring was done.
        assert not hasattr(audio_processor_module, "detect_and_slice_recording"), \
            "detect_and_slice_recording should be removed from audio_processor."
        assert not hasattr(audio_processor_module, "get_audio_details"), \
            "get_audio_details should be removed from audio_processor."
        # Add more assertions here if other specific items should have been removed.
    except ImportError:
        # This case handles if src/core/audio_processor.py was deleted entirely.
        # For this test, we'll assume that's an acceptable outcome of the refactoring.
        print("src.core.audio_processor module not found (possibly deleted, which may be intended).")
        assert True
