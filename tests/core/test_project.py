import pytest
import os
import shutil
from unittest.mock import patch, MagicMock, call
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.database.models import Base, Project as ProjectModel, Recording as RecordingModel
from src.core.project import Project as CoreProject
from src.database.utils import init_db as initialize_db_utils, get_db as get_db_utils, get_session_local

# --- Test Database Fixtures (similar to test_models.py) ---
@pytest.fixture(scope="function")
def test_engine():
    engine = create_engine("sqlite:///:memory:")
    initialize_db_utils(engine_instance=engine)
    return engine

@pytest.fixture(scope="function")
def db_session(test_engine):
    session_generator = get_db_utils(engine_instance=test_engine)
    session = next(session_generator)
    try:
        yield session
    finally:
        session.close()

# --- Core Project Test Fixtures ---
@pytest.fixture
def test_project_instance(db_session: Session):
    """Creates a ProjectModel in the DB and returns a CoreProject instance for it."""
    project_model = ProjectModel(name="Test Core Project", description="Project for core tests")
    db_session.add(project_model)
    db_session.commit()
    db_session.refresh(project_model)
    # CoreProject constructor handles its own session loading the project model
    core_project = CoreProject(project_id=project_model.id)
    return core_project, project_model # Return both CoreProject and the SQLAlchemy model

# --- Test Project Class ---

# Test __init__
def test_project_init_success(db_session: Session):
    project_model = ProjectModel(name="Init Test", description="Testing CoreProject init")
    db_session.add(project_model)
    db_session.commit()
    db_session.refresh(project_model)

    core_project = CoreProject(project_id=project_model.id)
    assert core_project.project_id == project_model.id
    assert core_project.project_model is not None
    assert core_project.project_model.name == "Init Test"

def test_project_init_not_found(db_session: Session):
    with pytest.raises(ValueError, match="Project with id 999 not found"):
        CoreProject(project_id=999) # Assuming project 999 does not exist

# Test add_recording
@patch('src.core.project.wave.open')
@patch('src.core.project.source') # Mock aubio.source
@patch('os.path.exists')
def test_add_recording(mock_os_exists, mock_aubio_source, mock_wave_open, test_project_instance, db_session: Session):
    core_project, project_model = test_project_instance
    
    mock_os_exists.return_value = True # Assume file exists

    # Mock for aubio.source
    mock_s = MagicMock()
    mock_s.samplerate = 44100
    mock_aubio_source.return_value = mock_s

    # Mock for wave.open
    mock_wf = MagicMock()
    mock_wf.__enter__.return_value.getnframes.return_value = 44100 * 2 # 2 seconds
    mock_wf.__enter__.return_value.getframerate.return_value = 44100
    mock_wf.__enter__.return_value.getnchannels.return_value = 1
    mock_wave_open.return_value = mock_wf

    dummy_file_path = "/fake/path/to/audio.wav"
    recording_name = "Test Recording Add"

    new_recording_model = core_project.add_recording(file_path=dummy_file_path, name=recording_name)

    assert new_recording_model is not None
    assert new_recording_model.id is not None
    assert new_recording_model.project_id == core_project.project_id
    assert new_recording_model.name == recording_name
    assert new_recording_model.file_path == dummy_file_path
    assert new_recording_model.status == "pending"
    assert new_recording_model.samplerate == 44100
    assert new_recording_model.duration_seconds == 2.0
    assert new_recording_model.channels == 1

    # Verify in DB
    # Use a new session for verification to ensure data is committed and read fresh
    verify_session = get_session_local(db_session.bind)() # db_session.bind is the engine
    db_rec = verify_session.query(RecordingModel).filter(RecordingModel.id == new_recording_model.id).first()
    assert db_rec is not None
    assert db_rec.name == recording_name
    verify_session.close()
    
    mock_aubio_source.assert_called_with(dummy_file_path, 0, 512)
    mock_wave_open.assert_called_with(dummy_file_path, 'rb')


@patch('os.path.exists')
def test_add_recording_file_not_found(mock_os_exists, test_project_instance, db_session: Session):
    core_project, _ = test_project_instance
    mock_os_exists.return_value = False # File does not exist

    with pytest.raises(FileNotFoundError, match="Recording file not found: /fake/nonexistent.wav"):
        core_project.add_recording(file_path="/fake/nonexistent.wav", name="NonExistent File Rec")
    
    # Ensure no recording was added to the DB
    # CoreProject.add_recording uses its own session, so we need to query with a new one
    verify_session = get_session_local(db_session.bind)()
    count = verify_session.query(RecordingModel).filter(RecordingModel.project_id == core_project.project_id).count()
    assert count == 0
    verify_session.close()


# Test get_recording
def test_get_recording(test_project_instance, db_session: Session):
    core_project, project_model = test_project_instance
    
    # First, add a recording using the model directly for setup
    rec_model = RecordingModel(project_id=project_model.id, name="Gettable Recording", file_path="get.wav")
    db_session.add(rec_model)
    db_session.commit()
    db_session.refresh(rec_model)

    retrieved_rec = core_project.get_recording(recording_id=rec_model.id)
    assert retrieved_rec is not None
    assert retrieved_rec.id == rec_model.id
    assert retrieved_rec.name == "Gettable Recording"

def test_get_recording_not_found(test_project_instance):
    core_project, _ = test_project_instance
    retrieved_rec = core_project.get_recording(recording_id=999) # Non-existent
    assert retrieved_rec is None

# Test list_recordings
def test_list_recordings(test_project_instance, db_session: Session):
    core_project, project_model = test_project_instance

    # Add some recordings
    rec1 = RecordingModel(project_id=project_model.id, name="List Rec 1", file_path="lr1.wav")
    rec2 = RecordingModel(project_id=project_model.id, name="List Rec 2", file_path="lr2.wav")
    db_session.add_all([rec1, rec2])
    db_session.commit()

    recordings_list = core_project.list_recordings()
    assert len(recordings_list) == 2
    names = sorted([r.name for r in recordings_list])
    assert names == ["List Rec 1", "List Rec 2"]

def test_list_recordings_empty(test_project_instance):
    core_project, _ = test_project_instance
    recordings_list = core_project.list_recordings()
    assert len(recordings_list) == 0

# Test process_recording
@patch('src.core.project.detect_and_slice_recording') # Mock the function in project.py's scope
@patch('os.makedirs')
@patch('os.path.exists') # Mock os.path.exists for the output directory check
def test_process_recording(mock_os_path_exists, mock_os_makedirs, mock_detect_slice, test_project_instance, db_session: Session):
    core_project, project_model = test_project_instance
    
    # Add a recording to process
    rec_model = RecordingModel(project_id=project_model.id, name="Processable Rec", file_path="process.wav", status="pending")
    db_session.add(rec_model)
    db_session.commit()
    db_session.refresh(rec_model)

    mock_os_path_exists.return_value = False # Simulate output directory does not exist initially
    output_sample_dir = f"/tmp/project_{project_model.id}/samples_for_{rec_model.id}"

    core_project.process_recording(recording_id=rec_model.id, output_sample_dir=output_sample_dir)

    mock_os_path_exists.assert_called_once_with(output_sample_dir)
    mock_os_makedirs.assert_called_once_with(output_sample_dir)
    # detect_and_slice_recording is called with a SessionLocal() db session, not db_session fixture
    # So we check that it was called with any Session instance and the correct recording_id and output_dir
    assert mock_detect_slice.call_args[0][0] is not None # Check that a db session was passed
    assert mock_detect_slice.call_args[0][1] == rec_model.id
    assert mock_detect_slice.call_args[0][2] == output_sample_dir


@patch('src.core.project.detect_and_slice_recording')
@patch('os.makedirs')
@patch('os.path.exists')
def test_process_recording_output_dir_exists(mock_os_path_exists, mock_os_makedirs, mock_detect_slice, test_project_instance, db_session: Session):
    core_project, project_model = test_project_instance
    rec_model = RecordingModel(project_id=project_model.id, name="Processable Rec Dir Exists", file_path="process_de.wav", status="pending")
    db_session.add(rec_model)
    db_session.commit()
    db_session.refresh(rec_model)

    mock_os_path_exists.return_value = True # Simulate output directory already exists
    output_sample_dir = f"/tmp/project_{project_model.id}/samples_for_{rec_model.id}_de"

    core_project.process_recording(recording_id=rec_model.id, output_sample_dir=output_sample_dir)

    mock_os_path_exists.assert_called_once_with(output_sample_dir)
    mock_os_makedirs.assert_not_called() # Should not be called if directory exists
    mock_detect_slice.assert_called_once()
    assert mock_detect_slice.call_args[0][1] == rec_model.id


def test_process_recording_recording_not_found(test_project_instance, capsys):
    core_project, _ = test_project_instance
    
    output_sample_dir = "/tmp/non_existent_rec_samples"
    core_project.process_recording(recording_id=999, output_sample_dir=output_sample_dir)
    
    captured = capsys.readouterr()
    assert f"Recording with id 999 not found for project {core_project.project_id}" in captured.out
    # Also check that detect_and_slice_recording was not called (implicitly, as it would error or be mocked)

# Cleanup test directories if they were actually created (though most are mocked)
# This is more for illustration, as mocks prevent actual creation.
# If any test *did* create a directory, it should be cleaned.
# For example, if output_sample_dir was not fully mocked in os.makedirs.
# However, with proper mocking, this is usually not needed.
# Test specific cleanup might be done in a fixture's teardown if necessary.

# Example of a fixture that creates and cleans up a directory
@pytest.fixture
def temp_output_dir():
    path = "/tmp/pytest_temp_output_dir"
    if os.path.exists(path): # cleanup from previous failed run
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    yield path
    shutil.rmtree(path) # Teardown
    
# Example of using it:
# def test_something_with_real_dir(temp_output_dir):
#     # ... test logic that uses temp_output_dir ...
#     assert os.path.exists(temp_output_dir)
pass
