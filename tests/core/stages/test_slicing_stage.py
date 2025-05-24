"""
Unit tests for the SlicingStage.
"""
import pytest
import os
import shutil
import wave
import logging
import numpy as np # For librosa mocking
from unittest.mock import patch, MagicMock, ANY
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.core.processing_stages import DATA_TYPE_FILE_PATH, DATA_TYPE_LIST_OF_SAMPLE_DATA
from src.core.stages.slicing_stage import SlicingStage, _get_audio_details_for_slicing
from src.database.models import Base, Recording as RecordingModel, Sample as SampleModel, Project as ProjectModel
from src.database.utils import init_db as initialize_db_utils, get_db as get_db_utils

# Configure basic logging for tests
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG) # Uncomment for detailed test logging

# --- Test Fixtures ---
DUMMY_AUDIO_DIR = "tests/fixtures"
DUMMY_AUDIO_FILENAME = "dummy_audio.wav" # Created in a previous step
DUMMY_AUDIO_PATH = os.path.join(DUMMY_AUDIO_DIR, DUMMY_AUDIO_FILENAME)

# Ensure the dummy audio file exists for tests that need it.
if not os.path.exists(DUMMY_AUDIO_PATH):
    logger.warning(f"Dummy audio file for testing not found at {DUMMY_AUDIO_PATH}. Some tests may fail or be skipped.")
    # Consider raising an error or creating it here if critical for all tests in this file.

@pytest.fixture(scope="function")
def test_engine():
    """Creates an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine) # Ensure tables are created
    return engine

@pytest.fixture(scope="function")
def db_session(test_engine):
    """Creates a new database session for a test, ensuring a clean state."""
    # Using sessionmaker directly for more control in tests
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback() # Rollback any uncommitted changes
        session.close()

@pytest.fixture
def temp_output_dir_for_samples():
    """Creates a temporary directory for generated sample files."""
    path = "/tmp/pytest_slicing_stage_samples"
    if os.path.exists(path): # Clean up from previous runs if any
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    logger.info(f"Created temp output dir for samples: {path}")
    yield path
    try:
        shutil.rmtree(path) # Teardown: remove after test
        logger.info(f"Cleaned up temp output dir: {path}")
    except OSError as e:
        logger.error(f"Error cleaning up temp output dir {path}: {e}")


@pytest.fixture
def setup_test_recording(db_session: Session) -> RecordingModel:
    """Sets up a Project and a Recording in the test DB."""
    project = ProjectModel(name="Test Slicing Project")
    db_session.add(project)
    db_session.commit()

    # Use the actual dummy audio file for the recording
    # Ensure dummy_audio.wav exists and is valid
    if not os.path.exists(DUMMY_AUDIO_PATH):
        pytest.fail(f"Required dummy audio file not found: {DUMMY_AUDIO_PATH}")

    try:
        sr, frames, channels = _get_audio_details_for_slicing(DUMMY_AUDIO_PATH)
        duration = frames / float(sr) if sr > 0 else 0
    except ValueError as e: # If _get_audio_details_for_slicing fails
        pytest.fail(f"Could not get audio details for dummy file {DUMMY_AUDIO_PATH}: {e}")


    recording = RecordingModel(
        project_id=project.id,
        name="Test Recording for SlicingStage",
        file_path=DUMMY_AUDIO_PATH,
        samplerate=sr,
        duration_seconds=duration,
        channels=channels,
        status="pending"
    )
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)
    logger.info(f"Created test recording ID: {recording.id} for project ID: {project.id}")
    return recording

# --- SlicingStage Tests ---

def test_slicing_stage_properties():
    stage = SlicingStage()
    assert stage.name == "slicing"
    assert stage.input_type == DATA_TYPE_FILE_PATH
    assert stage.output_type == DATA_TYPE_LIST_OF_SAMPLE_DATA
    assert "hop_size" in stage.default_params

@patch('src.core.stages.slicing_stage.librosa.onset.onset_detect')
@patch('src.core.stages.slicing_stage.librosa.load')
@patch('src.core.stages.slicing_stage._get_audio_details_for_slicing') # Keep this mock for simplicity here
def test_slicing_stage_process_success(mock_get_details, mock_librosa_load, mock_librosa_onset_detect, db_session, setup_test_recording, temp_output_dir_for_samples):
    recording = setup_test_recording
    stage = SlicingStage()

    # --- Mock _get_audio_details_for_slicing ---
    # This function is now complex due to librosa/wave fallback. Mocking its direct output simplifies this test.
    # It's tested separately in test_internal_get_audio_details_*.
    mock_get_details.return_value = (recording.samplerate, int(recording.duration_seconds * recording.samplerate), recording.channels)

    # --- Mock Librosa ---
    # librosa.load (for the process method's direct use for onset detection)
    # y: mono audio signal (numpy array), sr: sample rate
    mock_y_mono = np.random.rand(int(recording.duration_seconds * recording.samplerate)) 
    mock_librosa_load.return_value = (mock_y_mono, recording.samplerate)

    # librosa.onset.onset_detect
    # Returns frame indices of onsets. Let's say these are frame indices.
    # These are *not* sample indices if units='frames' was used, they are hop-scaled.
    # The SlicingStage uses these directly as start_frame.
    # For a 1s file at 44100Hz, hop_size 256:
    # onset at 0.1s -> sample 4410 -> frame 4410 (if units='samples') or 4410/256 = 17 (if units='frames')
    # The code uses units='frames', so these are indices like 17, 30 etc.
    # Let's simulate two onsets.
    # The default hop_size is 256.
    # onset1_frame_idx = int(0.1 * recording.samplerate / stage.default_params["hop_size"]) # Example: onset at 0.1s
    # onset2_frame_idx = int(0.5 * recording.samplerate / stage.default_params["hop_size"]) # Example: onset at 0.5s
    # For simplicity, let's use direct frame numbers that would be plausible.
    # The stage code converts these to sample numbers for slicing.
    # The stage code uses these directly as `start_frame`.
    onset_frames = np.array([50, 150]) # Example frame indices for onsets
    mock_librosa_onset_detect.return_value = onset_frames
    
    # --- Prepare Context ---
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
    expected_min_ioi_seconds = (expected_hop_length * min_ioi_seconds_factor) / float(recording.samplerate)
    expected_wait_samples = int(expected_min_ioi_seconds * recording.samplerate / expected_hop_length)

    mock_librosa_onset_detect.assert_called_once_with(
        y=mock_y_mono, 
        sr=recording.samplerate, 
        hop_length=expected_hop_length,
        units='frames',
        wait=expected_wait_samples
        # backtrack=True # if we decide to enable it
    )

def test_slicing_stage_input_file_not_found(db_session, setup_test_recording, temp_output_dir_for_samples):
    recording = setup_test_recording
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples
    }
    
    with pytest.raises(FileNotFoundError, match="Input audio file not found: /path/to/nonexistent.wav"):
        stage.process(data="/path/to/nonexistent.wav", params=stage.default_params, context=context)

    db_session.refresh(recording)
    assert recording.status == "slicing_failed"

def test_slicing_stage_recording_not_found_in_db(db_session, temp_output_dir_for_samples):
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": 9999, # Non-existent recording ID
        "project_id": 1,
        "output_sample_dir": temp_output_dir_for_samples
    }
    with pytest.raises(ValueError, match="Recording with id 9999 not found"):
        stage.process(data=DUMMY_AUDIO_PATH, params=stage.default_params, context=context)

def test_slicing_stage_missing_context_keys(db_session, setup_test_recording):
    recording = setup_test_recording
    stage = SlicingStage()
    
    # Missing db_session
    with pytest.raises(ValueError, match="Missing required key 'db_session' in context"):
        stage.process(DUMMY_AUDIO_PATH, {}, {"recording_id": recording.id, "project_id":1, "output_sample_dir": "/tmp"})
    
    # Missing recording_id
    with pytest.raises(ValueError, match="Missing required key 'recording_id' in context"):
        stage.process(DUMMY_AUDIO_PATH, {}, {"db_session": db_session, "project_id":1, "output_sample_dir": "/tmp"})


@patch('src.core.stages.slicing_stage._get_audio_details_for_slicing', side_effect=RuntimeError("Failed to get audio details"))
def test_slicing_stage_audio_detail_error(mock_get_details, db_session, setup_test_recording, temp_output_dir_for_samples):
    recording = setup_test_recording
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples
    }
    
    with pytest.raises(RuntimeError, match="Failed to get audio details"):
        stage.process(data=recording.file_path, params=stage.default_params, context=context)

    db_session.refresh(recording)
    assert recording.status == "slicing_failed"


@patch('src.core.stages.slicing_stage.librosa.onset.onset_detect')
@patch('src.core.stages.slicing_stage.librosa.load')
@patch('src.core.stages.slicing_stage._get_audio_details_for_slicing')
def test_slicing_stage_no_notes_detected(mock_get_details, mock_librosa_load, mock_librosa_onset_detect, db_session, setup_test_recording, temp_output_dir_for_samples):
    recording = setup_test_recording
    stage = SlicingStage()

    mock_get_details.return_value = (recording.samplerate, int(recording.duration_seconds * recording.samplerate), recording.channels)
    
    mock_y_mono = np.random.rand(int(recording.duration_seconds * recording.samplerate))
    mock_librosa_load.return_value = (mock_y_mono, recording.samplerate)
    
    mock_librosa_onset_detect.return_value = np.array([]) # No onsets detected
    
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples
    }
    
    result_samples_info = stage.process(data=recording.file_path, params=stage.default_params, context=context)
    
    db_session.refresh(recording)
    assert recording.status == "slicing_completed" # Process completed, even if no samples
    assert len(result_samples_info) == 0
    db_samples = db_session.query(SampleModel).filter(SampleModel.recording_id == recording.id).all()
    assert len(db_samples) == 0
    assert len(os.listdir(temp_output_dir_for_samples)) == 0 # No sample files created


# Test for _get_audio_details_for_slicing helper
@patch('src.core.stages.slicing_stage.wave.open')
@patch('src.core.stages.slicing_stage.librosa.load')
def test_internal_get_audio_details_librosa_success(mock_librosa_load_gad, mock_wave_open_gad):
    # Simulate librosa.load returning a stereo audio signal (2 channels) of 1 second duration at 48kHz
    mock_sr = 48000
    mock_total_frames = 48000 # 1 second
    mock_channels = 2
    mock_audio_array = np.zeros((mock_channels, mock_total_frames)) # (channels, samples)
    mock_librosa_load_gad.return_value = (mock_audio_array, mock_sr)

    samplerate, total_frames, channels = _get_audio_details_for_slicing("fake_path.wav")
    assert samplerate == mock_sr
    assert total_frames == mock_total_frames
    assert channels == mock_channels
    mock_wave_open_gad.assert_not_called()
    mock_librosa_load_gad.assert_called_once_with("fake_path.wav", sr=None, mono=False)

@patch('src.core.stages.slicing_stage.librosa.load', side_effect=RuntimeError("Librosa error"))
@patch('src.core.stages.slicing_stage.wave.open')
def test_internal_get_audio_details_librosa_fails_wave_success(mock_wave_open_gad, mock_librosa_load_gad_fails):
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


@patch('src.core.stages.slicing_stage.librosa.load', side_effect=RuntimeError("Librosa error"))
@patch('src.core.stages.slicing_stage.wave.open', side_effect=wave.Error("Wave error"))
def test_internal_get_audio_details_all_fail(mock_wave_open_gad_fails, mock_librosa_load_gad_fails):
    with pytest.raises(ValueError, match="Could not determine audio details .* using librosa or wave"):
        _get_audio_details_for_slicing("fake_path.wav")

