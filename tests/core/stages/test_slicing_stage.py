# pylint: disable=too-many-lines
"""
Unit tests for the SlicingStage audio processing stage.

This module tests the SlicingStage's properties, its core `process` method
(including successful slicing, handling of no onsets, and various error
conditions), and its internal helper `_get_audio_details_for_slicing`.
Mocks are used for librosa calls and database interactions to isolate the
stage's logic.
"""
import logging
import os
import shutil
import wave
from unittest.mock import patch, MagicMock # ANY is not used in current snippet

import numpy as np # For librosa mocking
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.core.processing_stages import DATA_TYPE_FILE_PATH, DATA_TYPE_LIST_OF_SAMPLE_DATA
from src.core.stages.slicing_stage import SlicingStage, _get_audio_details_for_slicing
from src.database.models import Base, Recording as RecordingModel, Sample as SampleModel, Project as ProjectModel
# initialize_db_utils and get_db_utils are not used directly in this file's fixtures.

# Configure basic logging for tests
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG) # Uncomment for detailed test logging

# --- Test Fixtures ---
DUMMY_AUDIO_DIR = "tests/fixtures" # Module-level constant
DUMMY_AUDIO_FILENAME = "dummy_audio.wav" # Module-level constant
DUMMY_AUDIO_PATH = os.path.join(DUMMY_AUDIO_DIR, DUMMY_AUDIO_FILENAME) # Module-level constant

# Ensure the dummy audio file exists for tests that need it.
if not os.path.exists(DUMMY_AUDIO_PATH):
    # Using logger.warning for consistency with existing logging style
    logger.warning(
        "Dummy audio file for testing not found at %s. Some tests may fail or be skipped.",
        DUMMY_AUDIO_PATH
    )

@pytest.fixture(scope="function")
def test_engine():
    """
    Creates an in-memory SQLite engine for function-scoped tests.
    Ensures that database tables are created before yielding the engine.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine) # Create tables
    return engine

@pytest.fixture(scope="function")
def db_session(test_engine) -> Session: # Added return type hint
    """
    Creates a new SQLAlchemy database session for each test function,
    using the `test_engine` fixture. Ensures the session is rolled back
    and closed after the test.
    """
    # TestSessionLocal variable name is fine as it's a factory/class
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback() # Rollback any uncommitted changes from the test
        session.close()

@pytest.fixture
def temp_output_dir_for_samples() -> str: # Added return type hint
    """
    Creates a temporary directory for storing generated sample files during tests.
    The directory is created before each test that uses this fixture and
    removed after the test completes.
    """
    path = "/tmp/pytest_slicing_stage_samples" # Consider making this more unique if tests run in parallel
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    logger.info("Created temp output dir for samples: %s", path)
    yield path
    try:
        shutil.rmtree(path)
        logger.info("Cleaned up temp output dir: %s", path)
    except OSError as e:
        logger.error("Error cleaning up temp output dir %s: %s", path, e)


@pytest.fixture
def setup_test_recording(db_session: Session) -> RecordingModel:
    """
    Sets up a sample Project and a Recording (associated with the dummy audio file)
    in the test database. Returns the created RecordingModel instance.
    Fails the test if the dummy audio file or its details cannot be accessed.
    """
    project = ProjectModel(name="Test Slicing Project")
    db_session.add(project)
    db_session.commit() # Commit to get project.id

    if not os.path.exists(DUMMY_AUDIO_PATH):
        # Using f-string for pytest.fail is standard and readable
        pytest.fail(f"Required dummy audio file not found for test setup: {DUMMY_AUDIO_PATH}")

    try:
        # Get actual details from the dummy audio file for realism
        sr, frames, channels = _get_audio_details_for_slicing(DUMMY_AUDIO_PATH)
        duration = frames / float(sr) if sr > 0 else 0.0
    except ValueError as e:
        # Using f-string for pytest.fail is standard and readable
        pytest.fail(
            f"Could not get audio details for dummy file {DUMMY_AUDIO_PATH} " # Wrapped
            f"during test setup: {e}"
        )

    recording = RecordingModel(
        project_id=project.id,
        name="Test Recording for SlicingStage",
        file_path=DUMMY_AUDIO_PATH,
        samplerate=int(sr), # Ensure samplerate is int
        duration_seconds=duration,
        channels=channels,
        status="pending" # Initial status for processing tests
    )
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)
    logger.info("Created test recording ID: %s for project ID: %s", recording.id, project.id)
    return recording

# --- SlicingStage Tests ---

def test_slicing_stage_properties():
    """Test the basic properties of the SlicingStage."""
    stage = SlicingStage()
    assert stage.name == "slicing"
    assert stage.description, "Description should not be empty."
    assert stage.input_type == DATA_TYPE_FILE_PATH
    assert stage.output_type == DATA_TYPE_LIST_OF_SAMPLE_DATA
    assert "hop_size" in stage.default_params, "'hop_size' should be a default parameter."

# pylint: disable=too-many-arguments,too-many-locals
@patch('src.core.stages.slicing_stage.librosa.onset.onset_detect')
@patch('src.core.stages.slicing_stage.librosa.load')
@patch('src.core.stages.slicing_stage._get_audio_details_for_slicing')
def test_slicing_stage_process_success(
    mock_get_details,
    mock_librosa_load,
    mock_librosa_onset_detect,
    db_session: Session, # db_session is a fixture
    setup_test_recording: RecordingModel, # setup_test_recording is a fixture
    temp_output_dir_for_samples: str # temp_output_dir_for_samples is a fixture
):
    """
    Test the `SlicingStage.process` method for successful slicing.
    Mocks librosa calls and `_get_audio_details_for_slicing`.
    Verifies recording status update, sample creation in DB, file output,
    and correct calls to mocked librosa functions.
    """
    recording = setup_test_recording # Use the recording from the fixture
    stage = SlicingStage()

    # Mock _get_audio_details_for_slicing
    # This mock simplifies the test by providing consistent audio details.
    mock_get_details.return_value = (
        recording.samplerate,
        int(recording.duration_seconds * (recording.samplerate or 0)), # Handle potential None for samplerate
        recording.channels
    )

    # Mock librosa.load
    # Ensure duration_seconds and samplerate from recording are valid before multiplication
    duration_samples = 0
    if recording.duration_seconds is not None and recording.samplerate is not None:
        duration_samples = int(recording.duration_seconds * recording.samplerate)
    
    mock_y_mono = np.random.rand(duration_samples if duration_samples > 0 else 1024) # Default to 1024 if no duration
    mock_librosa_load.return_value = (mock_y_mono, recording.samplerate or 44100) # Default sr if None

    # Mock librosa.onset.onset_detect to return specific onset frames
    onset_frames = np.array([50, 150]) # Example frame indices
    mock_librosa_onset_detect.return_value = onset_frames
    
    # Prepare context for the process method
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples
    }

    # --- Execute Process ---
    result_samples_info = stage.process(data=recording.file_path, params=stage.default_params, context=context)

    # --- Assertions ---
    db_session.refresh(recording)
    assert recording.status == "slicing_completed"
    
    assert len(result_samples_info) == 2
    
    # Sample 1
    sample1_info = result_samples_info[0]
    # Midi pitch is now a placeholder (0) and velocity (100)
    assert sample1_info["name"].startswith(f"rec_{recording.id}_sample_midi0") # MIDI is now placeholder
    assert sample1_info["midi_pitch"] == 0 # Placeholder
    assert os.path.exists(sample1_info["file_path"])
    assert sample1_info["file_path"].startswith(temp_output_dir_for_samples)
    
    # Sample 2
    sample2_info = result_samples_info[1]
    assert sample2_info["name"].startswith(f"rec_{recording.id}_sample_midi0") # MIDI is now placeholder
    assert sample2_info["midi_pitch"] == 0 # Placeholder
    assert os.path.exists(sample2_info["file_path"])

    # Check DB
    db_samples = db_session.query(SampleModel).filter(SampleModel.recording_id == recording.id).order_by(SampleModel.id).all()
    assert len(db_samples) == 2
    assert db_samples[0].name == sample1_info["name"]
    assert db_samples[0].midi_pitch == 0 # Placeholder
    assert db_samples[1].name == sample2_info["name"]
    assert db_samples[1].midi_pitch == 0 # Placeholder

    # Verify librosa calls
    mock_librosa_load.assert_called_once_with(recording.file_path, sr=recording.samplerate, mono=True)
    
    # Expected hop_length for onset_detect
    expected_hop_length = stage.default_params["hop_size"]
    # Expected min_ioi_seconds_factor from defaults
    min_ioi_seconds_factor = stage.default_params["min_ioi_seconds_factor"]
    # Calculate expected wait_samples based on how SlicingStage does it
    # Ensure recording.samplerate is not None before float conversion
    current_samplerate = recording.samplerate if recording.samplerate is not None else 44100.0
    expected_min_ioi_seconds = (
        expected_hop_length * min_ioi_seconds_factor
    ) / float(current_samplerate)
    expected_wait_samples = int(
        expected_min_ioi_seconds * current_samplerate / expected_hop_length
    )

    mock_librosa_onset_detect.assert_called_once_with(
        y=mock_y_mono, 
        sr=current_samplerate, # Use the validated samplerate
        hop_length=expected_hop_length,
        units='frames',
        wait=expected_wait_samples
    )

def test_slicing_stage_input_file_not_found(
    db_session: Session, setup_test_recording: RecordingModel, temp_output_dir_for_samples: str
):
    """
    Test that `SlicingStage.process` correctly handles a FileNotFoundError
    if the input audio file does not exist, and updates recording status.
    """
    recording = setup_test_recording
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples
    }
    
    non_existent_file = "/path/to/nonexistent_audio_file.wav"
    with pytest.raises(FileNotFoundError, match=f"Input audio file not found: {non_existent_file}"):
        stage.process(data=non_existent_file, params=stage.default_params, context=context)

    db_session.refresh(recording) # Get updated status from DB
    assert recording.status == "slicing_failed", "Recording status should be 'slicing_failed'."

def test_slicing_stage_recording_not_found_in_db(
    db_session: Session, temp_output_dir_for_samples: str
):
    """
    Test that `SlicingStage.process` raises ValueError if the recording_id
    provided in the context does not correspond to an existing recording.
    """
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": 99999, # Non-existent recording ID
        "project_id": 1, # Dummy project ID
        "output_sample_dir": temp_output_dir_for_samples
    }
    with pytest.raises(ValueError, match="Recording with id 99999 not found"):
        stage.process(data=DUMMY_AUDIO_PATH, params=stage.default_params, context=context)

def test_slicing_stage_missing_context_keys(
    db_session: Session, setup_test_recording: RecordingModel
):
    """
    Test that `SlicingStage.process` raises ValueError if essential keys
    are missing from the `context` dictionary.
    """
    recording = setup_test_recording
    stage = SlicingStage()
    base_context = {
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": "/tmp/dummy_output"
    }
    
    # Test missing db_session
    context_no_db = base_context.copy()
    # context_no_db.pop("db_session") # This key isn't in base_context
    with pytest.raises(ValueError, match="Missing required key 'db_session' in context"):
        stage.process(DUMMY_AUDIO_PATH, {}, {"output_sample_dir": "/tmp"}) # Minimal context without db

    # Test missing recording_id
    context_no_rec_id = {"db_session": db_session, "project_id": 1, "output_sample_dir": "/tmp"}
    with pytest.raises(ValueError, match="Missing required key 'recording_id' in context"):
        stage.process(DUMMY_AUDIO_PATH, {}, context_no_rec_id)


@patch('src.core.stages.slicing_stage._get_audio_details_for_slicing',
       side_effect=RuntimeError("Simulated audio detail extraction failure"))
def test_slicing_stage_audio_detail_error(
    mock_get_audio_details, # Renamed mock for clarity
    db_session: Session,
    setup_test_recording: RecordingModel,
    temp_output_dir_for_samples: str
):
    """
    Test `SlicingStage.process` error handling when `_get_audio_details_for_slicing`
    fails (e.g., raises RuntimeError). Expects recording status to be 'slicing_failed'.
    """
    recording = setup_test_recording
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples
    }
    
    with pytest.raises(RuntimeError, match="Simulated audio detail extraction failure"):
        stage.process(data=recording.file_path, params=stage.default_params, context=context)

    db_session.refresh(recording)
    assert recording.status == "slicing_failed"


# pylint: disable=too-many-arguments
@patch('src.core.stages.slicing_stage.librosa.onset.onset_detect')
@patch('src.core.stages.slicing_stage.librosa.load')
@patch('src.core.stages.slicing_stage._get_audio_details_for_slicing')
def test_slicing_stage_no_notes_detected(
    mock_get_details,
    mock_librosa_load,
    mock_librosa_onset_detect,
    db_session: Session,
    setup_test_recording: RecordingModel,
    temp_output_dir_for_samples: str
):
    """
    Test `SlicingStage.process` behavior when no onsets (notes) are detected.
    Expects the process to complete, status to be 'slicing_completed',
    but no samples created in DB or on disk.
    """
    recording = setup_test_recording
    stage = SlicingStage()

    mock_get_details.return_value = (
        recording.samplerate,
        int(recording.duration_seconds * (recording.samplerate or 0)),
        recording.channels
    )
    mock_y_mono = np.random.rand(
        int(recording.duration_seconds * (recording.samplerate or 0)) if recording.duration_seconds and recording.samplerate else 1024
    )
    mock_librosa_load.return_value = (mock_y_mono, recording.samplerate or 44100)
    mock_librosa_onset_detect.return_value = np.array([]) # Simulate no onsets
    
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples
    }
    
    result_samples_info = stage.process(
        data=recording.file_path, params=stage.default_params, context=context
    )
    
    db_session.refresh(recording)
    assert recording.status == "slicing_completed"
    assert not result_samples_info, "Result list should be empty if no samples created."
    db_samples = db_session.query(SampleModel).filter(
        SampleModel.recording_id == recording.id
    ).all()
    assert not db_samples, "No samples should be created in the database."
    assert not os.listdir(temp_output_dir_for_samples), \
        "Output directory should be empty if no samples were created."


# Test for _get_audio_details_for_slicing helper
@patch('src.core.stages.slicing_stage.wave.open')
@patch('src.core.stages.slicing_stage.librosa.load')
def test_internal_get_audio_details_librosa_success(
    mock_librosa_load_gad, mock_wave_open_gad
):
    """
    Test `_get_audio_details_for_slicing` successfully extracts details using librosa.
    """
    mock_sr, mock_total_frames, mock_channels = 48000, 48000, 2
    mock_audio_array = np.zeros((mock_channels, mock_total_frames))
    mock_librosa_load_gad.return_value = (mock_audio_array, mock_sr)

    samplerate, total_frames, channels = _get_audio_details_for_slicing("fake_path.wav")
    
    assert samplerate == mock_sr
    assert total_frames == mock_total_frames
    assert channels == mock_channels
    mock_wave_open_gad.assert_not_called()
    mock_librosa_load_gad.assert_called_once_with("fake_path.wav", sr=None, mono=False)

@patch('src.core.stages.slicing_stage.librosa.load', side_effect=RuntimeError("Simulated Librosa error"))
@patch('src.core.stages.slicing_stage.wave.open')
def test_internal_get_audio_details_librosa_fails_wave_success(
    mock_wave_open_gad, mock_librosa_load_gad_fails
):
    """
    Test `_get_audio_details_for_slicing` falls back to `wave` module when librosa fails,
    and successfully extracts details using `wave`.
    """
    mock_wf_gad = MagicMock()
    mock_wf_gad.__enter__.return_value.getframerate.return_value = 44100
    mock_wf_gad.__enter__.return_value.getnframes.return_value = 88200
    mock_wf_gad.__enter__.return_value.getnchannels.return_value = 2
    mock_wave_open_gad.return_value = mock_wf_gad

    samplerate, total_frames, channels = _get_audio_details_for_slicing("fake_path.wav")
    
    assert samplerate == 44100
    assert total_frames == 88200
    assert channels == 2
    mock_librosa_load_gad_fails.assert_called_once_with("fake_path.wav", sr=None, mono=False)
    mock_wave_open_gad.assert_called_once_with("fake_path.wav", "rb")


@patch('src.core.stages.slicing_stage.librosa.load', side_effect=RuntimeError("Simulated Librosa error"))
@patch('src.core.stages.slicing_stage.wave.open', side_effect=wave.Error("Simulated Wave error"))
def test_internal_get_audio_details_all_fail(
    mock_wave_open_gad_fails, mock_librosa_load_gad_fails # Parameter order matters for patch
):
    """
    Test `_get_audio_details_for_slicing` raises ValueError when both librosa and wave fail.
    """
    expected_error_match = "Could not determine audio details .* using librosa or wave"
    with pytest.raises(ValueError, match=expected_error_match):
        _get_audio_details_for_slicing("fake_path.wav")
