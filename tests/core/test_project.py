"""
Unit tests for the `src.core.project.Project` class.

These tests cover project initialization, adding recordings,
retrieving recordings, and listing recordings associated with a project.
Database interactions are tested using an in-memory SQLite database.
"""

import os
# import shutil # No longer used after removing temp_output_dir fixture
from unittest.mock import patch, MagicMock # call removed as it's not used

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database.models import Base, Project as ProjectModel, Recording as RecordingModel
from src.core.project import Project as CoreProject
from src.database.utils import init_db as initialize_db_utils
from src.database.utils import get_db
# get_session_local is no longer needed as verification will use get_db

# --- Test Database Fixtures ---

@pytest.fixture(scope="function")
def test_engine():
    """
    Creates an in-memory SQLite engine for function-scoped tests.
    Initializes the database schema using this engine.
    """
    engine = create_engine("sqlite:///:memory:")
    initialize_db_utils(engine_instance=engine) # Uses the new module-level ENGINE if not passed
    return engine

@pytest.fixture(scope="function")
def db_session(test_engine) -> Session: # Added return type hint
    """
    Provides a SQLAlchemy session for function-scoped tests, ensuring it's
    closed after the test. Uses the `test_engine` fixture.
    """
    session_generator = get_db(engine_instance=test_engine)
    session_instance: Session = next(session_generator)
    try:
        yield session_instance
    finally:
        # The get_db generator is responsible for closing the session.
        next(session_generator, None)

# --- Core Project Test Fixtures ---

@pytest.fixture
def test_project_instance(db_session: Session) -> CoreProject: # Return CoreProject
    """
    Creates a ProjectModel in the DB and returns a CoreProject instance for it.
    This fixture provides a CoreProject object ready for testing its methods.
    """
    project_model = ProjectModel(
        name="Test Core Project", description="Project for core tests"
    )
    db_session.add(project_model)
    db_session.commit()
    db_session.refresh(project_model)
    # CoreProject's __init__ loads the project model using its own session.
    core_project_instance = CoreProject(project_id=project_model.id)
    # Returning only CoreProject as project_model is accessible via core_project_instance.project_model
    return core_project_instance

# --- Test Project Class ---

# Test __init__
def test_project_init_success(db_session: Session):
    """
    Test successful initialization of a CoreProject instance
    when a valid project_id is provided.
    """
    project_model = ProjectModel(name="Init Test", description="Testing CoreProject init")
    db_session.add(project_model)
    db_session.commit()
    db_session.refresh(project_model)

    core_project = CoreProject(project_id=project_model.id)
    assert core_project.project_id == project_model.id
    assert core_project.project_model is not None
    assert core_project.project_model.name == "Init Test"

def test_project_init_not_found(): # db_session not needed as CoreProject handles its own session
    """
    Test that CoreProject initialization raises ValueError
    if the provided project_id does not exist in the database.
    """
    with pytest.raises(ValueError, match="Project with id 999 not found"):
        CoreProject(project_id=999) # Assuming project 999 does not exist

# Test add_recording
@patch('src.core.project.wave.open') # Patch wave.open in the correct module
@patch('os.path.exists')
def test_add_recording(
    mock_os_exists, mock_wave_open, test_project_instance: CoreProject, db_session: Session
):
    """
    Test successfully adding a new recording to a project.
    Mocks file existence and wave.open for audio metadata extraction.
    """
    core_project = test_project_instance
    
    mock_os_exists.return_value = True # Assume file exists

    # Mock for wave.open context manager
    mock_wf = MagicMock()
    mock_wf.__enter__.return_value.getnframes.return_value = 44100 * 2 # 2 seconds
    mock_wf.__enter__.return_value.getframerate.return_value = 44100
    mock_wf.__enter__.return_value.getnchannels.return_value = 1
    mock_wave_open.return_value = mock_wf

    dummy_file_path = "/fake/path/to/audio.wav"
    recording_name = "Test Recording Add"

    new_recording_model = core_project.add_recording(
        file_path=dummy_file_path, name=recording_name
    )

    assert new_recording_model is not None
    assert new_recording_model.id is not None
    assert new_recording_model.project_id == core_project.project_id
    assert new_recording_model.name == recording_name
    assert new_recording_model.file_path == dummy_file_path
    assert new_recording_model.status == "pending"
    assert new_recording_model.samplerate == 44100
    assert new_recording_model.duration_seconds == 2.0
    assert new_recording_model.channels == 1

    # Verify in DB using a new session to ensure data is committed and read fresh.
    # The add_recording method uses its own session from get_db().
    verify_db_gen = get_db(engine_instance=db_session.bind) # Use same engine for verification
    verify_db_session = next(verify_db_gen)
    try:
        db_rec = verify_db_session.query(RecordingModel).filter(
            RecordingModel.id == new_recording_model.id
        ).first()
        assert db_rec is not None, "Recording was not found in DB after add_recording."
        assert db_rec.name == recording_name, "Recording name in DB does not match."
    finally:
        next(verify_db_gen, None) # Ensure verification session is closed
    
    mock_wave_open.assert_called_with(dummy_file_path, 'rb')

@patch('os.path.exists')
def test_add_recording_file_not_found(
    mock_os_exists, test_project_instance: CoreProject, db_session: Session
):
    """
    Test `add_recording` raises FileNotFoundError if the audio file does not exist
    and ensures no recording is added to the database.
    """
    core_project = test_project_instance
    mock_os_exists.return_value = False # Simulate file does not exist

    with pytest.raises(FileNotFoundError, match="Recording file not found: /fake/nonexistent.wav"):
        core_project.add_recording(
            file_path="/fake/nonexistent.wav", name="NonExistent File Rec"
        )
    
    # Ensure no recording was added to the DB
    verify_db_gen = get_db(engine_instance=db_session.bind)
    verify_db_session = next(verify_db_gen)
    try:
        count = verify_db_session.query(RecordingModel).filter(
            RecordingModel.project_id == core_project.project_id
        ).count()
        assert count == 0, "No recording should be added to DB if file not found."
    finally:
        next(verify_db_gen, None)

# Test get_recording
def test_get_recording(test_project_instance: CoreProject, db_session: Session):
    """
    Test retrieving an existing recording associated with the project by its ID.
    """
    core_project = test_project_instance
    
    # Add a recording using the model directly for setup via the test's db_session
    rec_model = RecordingModel(
        project_id=core_project.project_id, name="Gettable Recording", file_path="get.wav"
    )
    db_session.add(rec_model)
    db_session.commit()
    db_session.refresh(rec_model)

    retrieved_rec = core_project.get_recording(recording_id=rec_model.id)
    assert retrieved_rec is not None
    assert retrieved_rec.id == rec_model.id
    assert retrieved_rec.name == "Gettable Recording"

def test_get_recording_not_found(test_project_instance: CoreProject):
    """
    Test that `get_recording` returns None if the recording ID does not exist
    or is not associated with the current project.
    """
    core_project = test_project_instance
    retrieved_rec = core_project.get_recording(recording_id=999) # Non-existent ID
    assert retrieved_rec is None

# Test list_recordings
def test_list_recordings(test_project_instance: CoreProject, db_session: Session):
    """
    Test listing all recordings associated with the project.
    """
    core_project = test_project_instance

    # Add some recordings for the test
    rec1 = RecordingModel(project_id=core_project.project_id, name="List Rec 1", file_path="lr1.wav")
    rec2 = RecordingModel(project_id=core_project.project_id, name="List Rec 2", file_path="lr2.wav")
    db_session.add_all([rec1, rec2])
    db_session.commit()

    recordings_list = core_project.list_recordings()
    assert len(recordings_list) == 2
    # Sort by name to ensure consistent order for assertion
    names = sorted([r.name for r in recordings_list])
    assert names == ["List Rec 1", "List Rec 2"]

def test_list_recordings_empty(test_project_instance: CoreProject):
    """
    Test `list_recordings` when the project has no recordings; expects an empty list.
    """
    core_project = test_project_instance
    recordings_list = core_project.list_recordings()
    assert not recordings_list, "Recordings list should be empty for a new project."

# Removed tests for process_recording as the method was removed from CoreProject.
# Removed temp_output_dir fixture as it's no longer used.
