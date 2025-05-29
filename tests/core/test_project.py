import pytest
import os
import shutil
from unittest.mock import patch, MagicMock, call
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker # Added sessionmaker
from src.database.models import (
    Base,
    Project as ProjectModel,
    Recording as RecordingModel,
)
from src.core.project import Project as CoreProject
from src.database.utils import (
    init_db as initialize_db_utils,
    get_db as get_db_utils,
    get_session_local,
)


# --- Test Database Fixtures (similar to test_models.py) ---
@pytest.fixture(scope="function")
def test_engine():
    engine = create_engine("sqlite:///:memory:")
    initialize_db_utils(engine_instance=engine)
    return engine


@pytest.fixture(scope="function")
def test_session_factory(test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function")
def db_session(test_session_factory: sessionmaker): # db_session now uses the factory from the same engine
    session = test_session_factory()
    try:
        yield session
    finally:
        session.close()


# --- Core Project Test Fixtures ---
@pytest.fixture
def test_project_instance(db_session: Session, test_session_factory: sessionmaker): # Add factory here
    """Creates a ProjectModel in the DB and returns a CoreProject instance for it."""
    project_model = ProjectModel(
        name="Test Core Project", description="Project for core tests"
    )
    db_session.add(project_model)
    db_session.commit()
    db_session.refresh(project_model)
    # Pass the factory to CoreProject
    core_project = CoreProject(project_id=project_model.id, session_factory=test_session_factory)
    return (
        core_project,
        project_model,
    )  # Return both CoreProject and the SQLAlchemy model


# --- Test Project Class ---


# Test __init__
def test_project_init_success(db_session: Session, test_session_factory: sessionmaker):
    project_model = ProjectModel(
        name="Init Test", description="Testing CoreProject init"
    )
    db_session.add(project_model)
    db_session.commit()
    db_session.refresh(project_model)

    core_project = CoreProject(project_id=project_model.id, session_factory=test_session_factory)
    assert core_project.project_id == project_model.id
    assert core_project.project_model is not None
    assert core_project.project_model.name == "Init Test"


def test_project_init_not_found(db_session: Session, test_session_factory: sessionmaker):
    with pytest.raises(ValueError, match="Project with id 999 not found"):
        CoreProject(project_id=999, session_factory=test_session_factory)  # Assuming project 999 does not exist


# Test add_recording
@patch("src.core.project.wave.open")
@patch("src.core.project.source")  # Mock aubio.source
@patch("os.path.exists")
def test_add_recording(
    mock_os_exists,
    mock_aubio_source,
    mock_wave_open,
    test_project_instance,
    db_session: Session,
):
    core_project, project_model = test_project_instance

    mock_os_exists.return_value = True  # Assume file exists

    # Mock for aubio.source
    mock_s = MagicMock()
    mock_s.samplerate = 44100
    mock_aubio_source.return_value = mock_s

    # Mock for wave.open
    mock_wf = MagicMock()
    mock_wf.__enter__.return_value.getnframes.return_value = 44100 * 2  # 2 seconds
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

    # Verify in DB
    # Use a new session for verification to ensure data is committed and read
    # fresh
    verify_session = get_session_local(
        db_session.bind
    )()  # db_session.bind is the engine
    db_rec = (
        verify_session.query(RecordingModel)
        .filter(RecordingModel.id == new_recording_model.id)
        .first()
    )
    assert db_rec is not None
    assert db_rec.name == recording_name
    verify_session.close()

    mock_aubio_source.assert_called_with(dummy_file_path, 0, 512)
    mock_wave_open.assert_called_with(dummy_file_path, "rb")

# The get_session_local(db_session.bind)() call for verify_session is problematic
# because db_session.bind is not how the engine is typically accessed from a session.
# It should use the test_session_factory for consistency if creating a new session.
# However, CoreProject methods will soon use self.session_factory, so direct DB verification
# might need to align with that or the test db_session fixture is sufficient.
# For now, focusing on CoreProject using its passed factory.
# The original verify_session logic:
# verify_session = get_session_local(db_session.bind)()
# For now, let's assume the main db_session is enough for verification after commit.
# If issues arise, we can revisit how verify_session is created.


@patch("os.path.exists")
def test_add_recording_file_not_found(
    mock_os_exists, test_project_instance, db_session: Session
):
    core_project, _ = test_project_instance
    mock_os_exists.return_value = False  # File does not exist

    with pytest.raises(
        FileNotFoundError, match="Recording file not found: /fake/nonexistent.wav"
    ):
        core_project.add_recording(
            file_path="/fake/nonexistent.wav", name="NonExistent File Rec"
        )

    # Ensure no recording was added to the DB
    # CoreProject.add_recording will use self.session_factory (which is test_session_factory here)
    # So, querying with db_session (which comes from the same factory) should see the data.
    count = (
        db_session.query(RecordingModel)
        .filter(RecordingModel.project_id == core_project.project_id)
        .count()
    )
    assert count == 0


# Test get_recording
def test_get_recording(test_project_instance, db_session: Session): # db_session comes from test_session_factory
    core_project, project_model = test_project_instance

    # First, add a recording using the model directly for setup
    rec_model = RecordingModel(
        project_id=project_model.id,
        name="Gettable Recording",
        file_path="get.wav")
    db_session.add(rec_model)
    db_session.commit()
    db_session.refresh(rec_model)

    retrieved_rec = core_project.get_recording(recording_id=rec_model.id)
    assert retrieved_rec is not None
    assert retrieved_rec.id == rec_model.id
    assert retrieved_rec.name == "Gettable Recording"


def test_get_recording_not_found(test_project_instance):
    core_project, _ = test_project_instance
    retrieved_rec = core_project.get_recording(
        recording_id=999)  # Non-existent
    assert retrieved_rec is None


# Test list_recordings
def test_list_recordings(test_project_instance, db_session: Session):
    core_project, project_model = test_project_instance

    # Add some recordings
    rec1 = RecordingModel(
        project_id=project_model.id, name="List Rec 1", file_path="lr1.wav"
    )
    rec2 = RecordingModel(
        project_id=project_model.id, name="List Rec 2", file_path="lr2.wav"
    )
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


# Tests for process_recording (test_process_recording, test_process_recording_output_dir_exists, 
# test_process_recording_recording_not_found) are removed as the method now raises NotImplementedError.

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
    if os.path.exists(path):  # cleanup from previous failed run
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    yield path
    shutil.rmtree(path)  # Teardown


# Example of using it:
# def test_something_with_real_dir(temp_output_dir):
#     # ... test logic that uses temp_output_dir ...
#     assert os.path.exists(temp_output_dir)
pass
