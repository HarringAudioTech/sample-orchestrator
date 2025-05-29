"""
Unit tests for the SlicingStage.
"""

import pytest
import os
import shutil
import wave
import logging
from unittest.mock import patch, MagicMock, ANY
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.core.processing_stages import (
    DATA_TYPE_FILE_PATH,
    DATA_TYPE_LIST_OF_SAMPLE_DATA,
)
from src.core.stages.slicing_stage import SlicingStage, _get_audio_details_for_slicing
from src.database.models import (
    Base,
    Recording as RecordingModel,
    Sample as SampleModel,
    Project as ProjectModel,
)
from src.database.utils import init_db as initialize_db_utils, get_db as get_db_utils

# Configure basic logging for tests
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG) # Uncomment for detailed test
# logging

# --- Test Fixtures ---
DUMMY_AUDIO_DIR = "tests/fixtures"
DUMMY_AUDIO_FILENAME = "dummy_audio.wav"  # Created in a previous step
DUMMY_AUDIO_PATH = os.path.join(DUMMY_AUDIO_DIR, DUMMY_AUDIO_FILENAME)

# Ensure the dummy audio file exists for tests that need it.
if not os.path.exists(DUMMY_AUDIO_PATH):
    logger.warning(
        f"Dummy audio file for testing not found at {DUMMY_AUDIO_PATH}. Some tests may fail or be skipped."
    )
    # Consider raising an error or creating it here if critical for all tests
    # in this file.


@pytest.fixture(scope="function")
def test_engine():
    """Creates an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)  # Ensure tables are created
    return engine


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Creates a new database session for a test, ensuring a clean state."""
    # Using sessionmaker directly for more control in tests
    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()  # Rollback any uncommitted changes
        session.close()


@pytest.fixture
def temp_output_dir_for_samples():
    """Creates a temporary directory for generated sample files."""
    path = "/tmp/pytest_slicing_stage_samples"
    if os.path.exists(path):  # Clean up from previous runs if any
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    logger.info(f"Created temp output dir for samples: {path}")
    yield path
    try:
        shutil.rmtree(path)  # Teardown: remove after test
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
    except ValueError as e:  # If _get_audio_details_for_slicing fails
        pytest.fail(
            f"Could not get audio details for dummy file {DUMMY_AUDIO_PATH}: {e}")

    recording = RecordingModel(
        project_id=project.id,
        name="Test Recording for SlicingStage",
        file_path=DUMMY_AUDIO_PATH,
        samplerate=sr,
        duration_seconds=duration,
        channels=channels,
        status="pending",
    )
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)
    logger.info(
        f"Created test recording ID: {
            recording.id} for project ID: {
            project.id}"
    )
    return recording


# --- SlicingStage Tests ---


def test_slicing_stage_properties():
    stage = SlicingStage()
    assert stage.name == "slicing"
    assert stage.input_type == DATA_TYPE_FILE_PATH
    assert stage.output_type == DATA_TYPE_LIST_OF_SAMPLE_DATA
    assert "hop_size" in stage.default_params


@patch("src.core.stages.slicing_stage.aubio_notes")
@patch("src.core.stages.slicing_stage.aubio_source")
def test_slicing_stage_process_success(
    mock_aubio_src,
    mock_aubio_notes_obj_class,
    db_session,
    setup_test_recording,
    temp_output_dir_for_samples,
):
    recording = setup_test_recording
    stage = SlicingStage()

    # --- Mock Aubio ---
    mock_src_instance = MagicMock()
    mock_src_instance.samplerate = recording.samplerate
    mock_src_instance.channels = recording.channels
    mock_src_instance.duration = int(
        recording.duration_seconds *
        recording.samplerate)
    # Simulate reading audio data in chunks
    # For a 1s file at 44100Hz, hop_size 256 -> 44100/256 = ~172 reads
    # Let's simulate fewer reads for simplicity, assuming some notes are found.
    num_reads_simulated = 10
    frames_per_read_simulated = stage.default_params["hop_size"]
    simulated_reads = [
        (MagicMock(), frames_per_read_simulated)
    ] * num_reads_simulated + [
        (MagicMock(), 0)
    ]  # Last read is 0
    mock_src_instance.side_effect = simulated_reads
    mock_aubio_src.return_value = mock_src_instance

    mock_notes_instance = MagicMock()
    # Simulate detecting two notes
    # Note format: (midi_pitch, velocity, onset_sample_within_chunk_passed_to_notes_o)
    # SlicingStage calculates absolute start_frame based on
    # notes_o.get_last_pos()
    mock_notes_instance.get_last_pos.side_effect = [
        50,
        150,
    ]  # Frame index within the current chunk

    # notes_o(samples) returns a list of new notes.
    # Simulate one note found in the 2nd read, another in the 5th read.
    notes_output_simulation = [[]] * \
        (num_reads_simulated + 1)  # Default to no notes
    notes_output_simulation[1] = [
        (60, 100, 50)
    ]  # Note 1: MIDI 60, vel 100, detected at frame 50 of this chunk
    notes_output_simulation[4] = [
        (62, 110, 150)
    ]  # Note 2: MIDI 62, vel 110, detected at frame 150 of this chunk
    mock_notes_instance.side_effect = notes_output_simulation
    mock_aubio_notes_obj_class.return_value = mock_notes_instance

    # --- Prepare Context ---
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    # --- Execute Process ---
    result_samples_info = stage.process(
        data=recording.file_path, params=stage.default_params, context=context
    )

    # --- Assertions ---
    db_session.refresh(recording)
    assert recording.status == "slicing_completed"

    assert len(result_samples_info) == 2

    # Sample 1
    sample1_info = result_samples_info[0]
    assert sample1_info["name"].startswith(f"rec_{recording.id}_sample_midi60")
    assert sample1_info["midi_pitch"] == 60
    assert os.path.exists(sample1_info["file_path"])
    assert sample1_info["file_path"].startswith(temp_output_dir_for_samples)

    # Sample 2
    sample2_info = result_samples_info[1]
    assert sample2_info["name"].startswith(f"rec_{recording.id}_sample_midi62")
    assert sample2_info["midi_pitch"] == 62
    assert os.path.exists(sample2_info["file_path"])

    # Check DB
    db_samples = (
        db_session.query(SampleModel)
        .filter(SampleModel.recording_id == recording.id)
        .order_by(SampleModel.id)
        .all()
    )
    assert len(db_samples) == 2
    assert db_samples[0].name == sample1_info["name"]
    assert db_samples[0].midi_pitch == 60
    assert db_samples[1].name == sample2_info["name"]
    assert db_samples[1].midi_pitch == 62

    # Verify aubio calls (simplified)
    mock_aubio_src.assert_called_with(
        recording.file_path,
        recording.samplerate,
        stage.default_params["hop_size"])
    mock_aubio_notes_obj_class.assert_called_with(
        "default",
        stage.default_params["window_size"],
        stage.default_params["hop_size"],
        recording.samplerate,
    )


def test_slicing_stage_input_file_not_found(
    db_session, setup_test_recording, temp_output_dir_for_samples
):
    recording = setup_test_recording
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    with pytest.raises(
        FileNotFoundError, match="Input audio file not found: /path/to/nonexistent.wav"
    ):
        stage.process(
            data="/path/to/nonexistent.wav",
            params=stage.default_params,
            context=context,
        )

    db_session.refresh(recording)
    assert recording.status == "slicing_failed"


def test_slicing_stage_recording_not_found_in_db(
    db_session, temp_output_dir_for_samples
):
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": 9999,  # Non-existent recording ID
        "project_id": 1,
        "output_sample_dir": temp_output_dir_for_samples,
    }
    with pytest.raises(ValueError, match="Recording with id 9999 not found"):
        stage.process(
            data=DUMMY_AUDIO_PATH, params=stage.default_params, context=context
        )


def test_slicing_stage_missing_context_keys(db_session, setup_test_recording):
    recording = setup_test_recording
    stage = SlicingStage()

    # Missing db_session
    with pytest.raises(
        ValueError, match="Missing required key 'db_session' in context"
    ):
        stage.process(
            DUMMY_AUDIO_PATH,
            {},
            {
                "recording_id": recording.id,
                "project_id": 1,
                "output_sample_dir": "/tmp",
            },
        )

    # Missing recording_id
    with pytest.raises(
        ValueError, match="Missing required key 'recording_id' in context"
    ):
        stage.process(
            DUMMY_AUDIO_PATH, {}, {
                "db_session": db_session, "project_id": 1, "output_sample_dir": "/tmp"}, )


@patch(
    "src.core.stages.slicing_stage._get_audio_details_for_slicing",
    side_effect=RuntimeError("Failed to get audio details"),
)
def test_slicing_stage_audio_detail_error(
        mock_get_details,
        db_session,
        setup_test_recording,
        temp_output_dir_for_samples):
    recording = setup_test_recording
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    with pytest.raises(RuntimeError, match="Failed to get audio details"):
        stage.process(
            data=recording.file_path,
            params=stage.default_params,
            context=context)

    db_session.refresh(recording)
    assert recording.status == "slicing_failed"


@patch("src.core.stages.slicing_stage.aubio_notes")
@patch("src.core.stages.slicing_stage.aubio_source")
def test_slicing_stage_no_notes_detected(
    mock_aubio_src,
    mock_aubio_notes_obj_class,
    db_session,
    setup_test_recording,
    temp_output_dir_for_samples,
):
    recording = setup_test_recording
    stage = SlicingStage()

    mock_src_instance = MagicMock(
        samplerate=recording.samplerate,
        channels=recording.channels,
        duration=int(recording.duration_seconds * recording.samplerate),
    )
    mock_src_instance.side_effect = [
        (MagicMock(), stage.default_params["hop_size"])
    ] * 5 + [(MagicMock(), 0)]
    mock_aubio_src.return_value = mock_src_instance

    mock_notes_instance = MagicMock()
    # No notes detected in any chunk
    mock_notes_instance.side_effect = [[]] * 6
    mock_aubio_notes_obj_class.return_value = mock_notes_instance

    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    result_samples_info = stage.process(
        data=recording.file_path, params=stage.default_params, context=context
    )

    db_session.refresh(recording)
    assert (
        recording.status == "slicing_completed"
    )  # Process completed, even if no samples
    assert len(result_samples_info) == 0
    db_samples = (
        db_session.query(SampleModel)
        .filter(SampleModel.recording_id == recording.id)
        .all()
    )
    assert len(db_samples) == 0
    assert len(os.listdir(temp_output_dir_for_samples)
               ) == 0  # No sample files created


# Test for _get_audio_details_for_slicing helper (optional, as it's internal)
@patch("src.core.stages.slicing_stage.wave.open")
@patch("src.core.stages.slicing_stage.aubio_source")
def test_internal_get_audio_details_aubio_success(
    mock_aubio_source_gad, mock_wave_open_gad
):
    mock_s_gad = MagicMock(samplerate=48000, duration=96000, channels=1)
    mock_aubio_source_gad.return_value = mock_s_gad

    samplerate, total_frames, channels = _get_audio_details_for_slicing(
        "fake_path.wav")
    assert samplerate == 48000
    assert total_frames == 96000
    assert channels == 1
    mock_wave_open_gad.assert_not_called()


@patch(
    "src.core.stages.slicing_stage.aubio_source",
    side_effect=RuntimeError("Aubio error"),
)
@patch("src.core.stages.slicing_stage.wave.open")
def test_internal_get_audio_details_aubio_fails_wave_success(
    mock_wave_open_gad, mock_aubio_source_gad_fails
):
    mock_wf_gad = MagicMock()
    mock_wf_gad.__enter__.return_value.getframerate.return_value = 44100
    mock_wf_gad.__enter__.return_value.getnframes.return_value = 88200
    mock_wf_gad.__enter__.return_value.getnchannels.return_value = 2
    mock_wave_open_gad.return_value = mock_wf_gad

    samplerate, total_frames, channels = _get_audio_details_for_slicing(
        "fake_path.wav")
    assert samplerate == 44100
    assert total_frames == 88200
    assert channels == 2
    mock_aubio_source_gad_fails.assert_called_once()


@patch(
    "src.core.stages.slicing_stage.aubio_source",
    side_effect=RuntimeError("Aubio error"),
)
@patch("src.core.stages.slicing_stage.wave.open",
       side_effect=wave.Error("Wave error"))
def test_internal_get_audio_details_all_fail(
    mock_wave_open_gad_fails, mock_aubio_source_gad_fails
):
    with pytest.raises(ValueError, match="Could not determine audio details"):
        _get_audio_details_for_slicing("fake_path.wav")
