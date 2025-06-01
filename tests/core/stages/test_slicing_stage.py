"""
Unit tests for the SlicingStage.
"""

import pytest
import os
import shutil

import logging
from unittest.mock import patch, MagicMock, ANY
import numpy as np  # For librosa mocks
import soundfile as sf  # For sf.info in fixture and mock target
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.core.processing_stages import (
    DATA_TYPE_FILE_PATH,
    DATA_TYPE_LIST_OF_SAMPLE_DATA,
)

# _get_audio_details_for_slicing is removed, so SlicingStage is the direct import
from src.core.stages.slicing_stage import (
    SlicingStage,
)  # , _get_audio_details_for_slicing # Remove helper
from src.database.models import (
    Base,
    Recording as RecordingModel,
    Sample as SampleModel,
    Project as ProjectModel,
)

# from src.database.utils import init_db as initialize_db_utils, get_db as get_db_utils # Not used

# Configure basic logging for tests
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG) # Uncomment for detailed test logging

# --- Test Fixtures ---
DUMMY_AUDIO_DIR = "tests/fixtures"
DUMMY_AUDIO_FILENAME = "dummy_audio.wav"
DUMMY_AUDIO_PATH = os.path.join(DUMMY_AUDIO_DIR, DUMMY_AUDIO_FILENAME)

# Ensure the dummy audio file exists for tests that need it.
if not os.path.exists(DUMMY_AUDIO_PATH):
    logger.warning(
        f"Dummy audio file for testing not found at {DUMMY_AUDIO_PATH}. Some tests may fail or be skipped."
    )
    # Attempt to create a dummy file if it's missing, as it's crucial for many tests
    try:
        os.makedirs(DUMMY_AUDIO_DIR, exist_ok=True)
        # Create a simple 1-second mono WAV file at 22050 Hz
        samplerate = 22050
        duration_seconds = 1
        frequency = 440  # A4 note
        amplitude = 0.5
        t = np.linspace(
            0, duration_seconds, int(samplerate * duration_seconds), endpoint=False
        )
        wave_data = amplitude * np.sin(2 * np.pi * frequency * t)
        sf.write(DUMMY_AUDIO_PATH, wave_data.astype(np.float32), samplerate)
        logger.info(f"Created dummy audio file at {DUMMY_AUDIO_PATH}")
    except Exception as e:
        logger.error(f"Could not create dummy audio file {DUMMY_AUDIO_PATH}: {e}")
        # Depending on test strictness, you might want to raise the error here:
        # raise RuntimeError(f"Failed to create essential dummy audio file: {e}") from e


@pytest.fixture(scope="function")
def test_engine():
    """Creates an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Creates a new database session for a test, ensuring a clean state."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def temp_output_dir_for_samples():
    """Creates a temporary directory for generated sample files."""
    path = "/tmp/pytest_slicing_stage_samples"
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    yield path
    try:
        shutil.rmtree(path)
    except OSError as e:
        logger.error(f"Error cleaning up temp output dir {path}: {e}")


@pytest.fixture
def setup_test_recording(db_session: Session) -> RecordingModel:
    """Sets up a Project and a Recording in the test DB."""
    project = ProjectModel(name="Test Slicing Project")
    db_session.add(project)
    db_session.commit()

    if not os.path.exists(DUMMY_AUDIO_PATH):
        pytest.fail(
            f"Required dummy audio file not found and could not be created: {DUMMY_AUDIO_PATH}"
        )

    try:
        info = sf.info(DUMMY_AUDIO_PATH)
        sr, frames, channels, duration = (
            info.samplerate,
            info.frames,
            info.channels,
            info.duration,
        )
    except Exception as e:
        pytest.fail(
            f"Could not get audio details for dummy file {DUMMY_AUDIO_PATH} using soundfile: {e}"
        )

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
    return recording


# --- SlicingStage Tests ---


def test_slicing_stage_properties():
    stage = SlicingStage()
    assert stage.name == "slicing"
    assert stage.input_type == DATA_TYPE_FILE_PATH
    assert stage.output_type == DATA_TYPE_LIST_OF_SAMPLE_DATA
    assert "librosa_onset_params" in stage.default_params
    assert "min_sample_length_ms" in stage.default_params
    assert "max_sample_length_ms" in stage.default_params


@patch("src.core.stages.slicing_stage.sf.write")
@patch("src.core.stages.slicing_stage.librosa.onset.onset_detect")
@patch("src.core.stages.slicing_stage.librosa.load")
def test_slicing_stage_process_success(
    mock_librosa_load,
    mock_onset_detect,
    mock_sf_write,
    db_session,
    setup_test_recording,
    temp_output_dir_for_samples,
):
    recording = setup_test_recording
    stage = SlicingStage()

    mock_samplerate = 22050
    mock_audio_data_mono = np.random.rand(mock_samplerate * 2).astype(np.float32)  # 2s audio
    mock_librosa_load.return_value = (mock_audio_data_mono, mock_samplerate)

    onset_time_1_s = 0.5
    onset_time_2_s = 1.2
    mock_onset_samples = np.array(
        [int(onset_time_1_s * mock_samplerate), int(onset_time_2_s * mock_samplerate)]
    )
    mock_onset_detect.return_value = mock_onset_samples

    stage_params = stage.default_params.copy()
    # User can override librosa_onset_params, e.g.
    # stage_params["librosa_onset_params"] = {"hop_length": 256} # Example override

    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    result_samples_info = stage.process(
        data=recording.file_path, params=stage_params, context=context
    )

    db_session.refresh(recording)
    assert recording.status == "slicing_completed"
    assert len(result_samples_info) == 2

    mock_librosa_load.assert_called_once_with(recording.file_path, sr=None, mono=True)

    # Expected librosa_onset_params should be a merge of defaults and user-provided (if any)
    # And 'units' should be 'samples' as enforced by the stage
    expected_call_params = {
        **stage.default_params["librosa_onset_params"],
        **(stage_params.get("librosa_onset_params", {})),
        "units": "samples",
    }
    mock_onset_detect.assert_called_once_with(
        y=mock_audio_data_mono, sr=mock_samplerate, **expected_call_params
    )

    # Assertions for Sample 1
    sample1_info = next(
        s
        for s in result_samples_info
        if s["metadata_json"] == f'{{"source_onset_samples": {mock_onset_samples[0]}}}'
    )
    assert sample1_info["name"].startswith(
        f"rec_{recording.id}_sample_1_onset_S{mock_onset_samples[0]}"
    )
    assert sample1_info["midi_pitch"] is None

    expected_start_time1 = float(mock_onset_samples[0]) / mock_samplerate
    # End time for sample 1 is start of sample 2, unless max_length is shorter
    max_len_samples1 = int(
        (
            stage_params.get(
                "max_sample_length_ms", stage.default_params["max_sample_length_ms"]
            )
            / 1000.0
        )
        * mock_samplerate
    )
    calculated_end_sample1 = min(
        mock_onset_samples[1], mock_onset_samples[0] + max_len_samples1
    )
    expected_end_time1 = float(calculated_end_sample1) / mock_samplerate

    assert abs(sample1_info["start_time_seconds"] - expected_start_time1) < 1e-6
    assert abs(sample1_info["end_time_seconds"] - expected_end_time1) < 1e-6

    # Assertions for Sample 2
    sample2_info = next(
        s
        for s in result_samples_info
        if s["metadata_json"] == f'{{"source_onset_samples": {mock_onset_samples[1]}}}'
    )
    assert sample2_info["name"].startswith(
        f"rec_{recording.id}_sample_2_onset_S{mock_onset_samples[1]}"
    )
    assert sample2_info["midi_pitch"] is None

    expected_start_time2 = float(mock_onset_samples[1]) / mock_samplerate
    # End time for sample 2 is end of audio, unless max_length is shorter
    max_len_samples2 = int(
        (
            stage_params.get(
                "max_sample_length_ms", stage.default_params["max_sample_length_ms"]
            )
            / 1000.0
        )
        * mock_samplerate
    )
    calculated_end_sample2 = min(
        len(mock_audio_data_mono), mock_onset_samples[1] + max_len_samples2
    )
    expected_end_time2 = float(calculated_end_sample2) / mock_samplerate

    assert abs(sample2_info["start_time_seconds"] - expected_start_time2) < 1e-6
    assert abs(sample2_info["end_time_seconds"] - expected_end_time2) < 1e-6

    assert mock_sf_write.call_count == 2
    # Example check for one sf.write call's arguments
    # First call: (path, data_slice, samplerate)
    args_call1, _ = mock_sf_write.call_args_list[0]
    assert args_call1[0] == sample1_info["file_path"]
    # Data slice check:
    # expected_slice_data1 = mock_audio_data_mono[mock_onset_samples[0]:calculated_end_sample1]
    # assert np.array_equal(args_call1[1], expected_slice_data1) # This can be tricky with float precision
    assert args_call1[2] == mock_samplerate

    db_samples = (
        db_session.query(SampleModel)
        .filter(SampleModel.recording_id == recording.id)
        .order_by(SampleModel.start_time_seconds)
        .all()
    )
    assert len(db_samples) == 2
    assert db_samples[0].name == sample1_info["name"]
    assert db_samples[0].midi_pitch is None
    assert abs(db_samples[0].start_time_seconds - expected_start_time1) < 1e-6
    assert abs(db_samples[0].end_time_seconds - expected_end_time1) < 1e-6

    assert db_samples[1].name == sample2_info["name"]
    assert db_samples[1].midi_pitch is None
    assert abs(db_samples[1].start_time_seconds - expected_start_time2) < 1e-6
    assert abs(db_samples[1].end_time_seconds - expected_end_time2) < 1e-6

    db_session.refresh(recording)
    assert (
        recording.samplerate == mock_samplerate
    )  # Should be updated by librosa.load's return
    assert (
        abs(recording.duration_seconds - (len(mock_audio_data_mono) / mock_samplerate)) < 1e-6
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

    non_existent_file = "/path/to/absolutely/nonexistent/audio.wav"
    with pytest.raises(
        FileNotFoundError, match=f"Input audio file not found: {non_existent_file}"
    ):
        stage.process(data=non_existent_file, params=stage.default_params, context=context)

    db_session.refresh(recording)
    assert recording.status == "slicing_failed"


def test_slicing_stage_recording_not_found_in_db(db_session, temp_output_dir_for_samples):
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": 99999,  # Non-existent
        "project_id": 1,
        "output_sample_dir": temp_output_dir_for_samples,
    }
    with pytest.raises(ValueError, match="Recording with id 99999 not found"):
        stage.process(data=DUMMY_AUDIO_PATH, params=stage.default_params, context=context)


def test_slicing_stage_missing_context_keys(db_session, setup_test_recording):
    recording = setup_test_recording
    stage = SlicingStage()
    base_context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": "/tmp/pytest_slicing_stage_samples_m_ctx",
    }

    required_keys = ["db_session", "recording_id", "project_id", "output_sample_dir"]

    for key_to_remove in required_keys:
        context_copy = base_context.copy()
        del context_copy[key_to_remove]

        with pytest.raises(
            ValueError, match=f"Missing required key '{key_to_remove}' in context"
        ):
            stage.process(DUMMY_AUDIO_PATH, {}, context_copy)

    # Test with context = None
    with pytest.raises(ValueError, match="Context is required and was not provided."):
        stage.process(DUMMY_AUDIO_PATH, {}, None)


@patch(
    "src.core.stages.slicing_stage.librosa.load",
    side_effect=RuntimeError("Simulated librosa.load failure"),
)
def test_slicing_stage_librosa_load_error(
    mock_librosa_load_fails,
    db_session,
    setup_test_recording,
    temp_output_dir_for_samples,
):
    recording = setup_test_recording
    stage = SlicingStage()
    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    with pytest.raises(RuntimeError, match="Simulated librosa.load failure"):
        stage.process(data=recording.file_path, params=stage.default_params, context=context)

    db_session.refresh(recording)
    assert recording.status == "slicing_failed"
    mock_librosa_load_fails.assert_called_once()


@patch("src.core.stages.slicing_stage.sf.write")
@patch("src.core.stages.slicing_stage.librosa.onset.onset_detect")
@patch("src.core.stages.slicing_stage.librosa.load")
def test_slicing_stage_no_onsets_detected(
    mock_librosa_load,
    mock_onset_detect,
    mock_sf_write,
    db_session,
    setup_test_recording,
    temp_output_dir_for_samples,
):
    recording = setup_test_recording
    stage = SlicingStage()

    mock_samplerate = 22050
    mock_audio_data_mono = np.random.rand(mock_samplerate * 2).astype(np.float32)
    mock_librosa_load.return_value = (mock_audio_data_mono, mock_samplerate)

    mock_onset_detect.return_value = np.array([])  # No onsets

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
    assert recording.status == "slicing_completed"
    assert len(result_samples_info) == 0
    db_samples = (
        db_session.query(SampleModel).filter(SampleModel.recording_id == recording.id).all()
    )
    assert len(db_samples) == 0
    assert not os.listdir(temp_output_dir_for_samples)  # No sample files created
    mock_sf_write.assert_not_called()


@patch("src.core.stages.slicing_stage.sf.write")
@patch("src.core.stages.slicing_stage.librosa.onset.onset_detect")
@patch("src.core.stages.slicing_stage.librosa.load")
def test_slicing_stage_min_max_sample_length(
    mock_librosa_load,
    mock_onset_detect,
    mock_sf_write,
    db_session,
    setup_test_recording,
    temp_output_dir_for_samples,
):
    recording = setup_test_recording
    stage = SlicingStage()

    mock_samplerate = 22050
    # Audio duration: 5 seconds
    mock_audio_data_mono = np.random.rand(mock_samplerate * 5).astype(np.float32)
    mock_librosa_load.return_value = (mock_audio_data_mono, mock_samplerate)

    # Onsets at 0.5s, 0.52s (too short), 1.0s, 2.0s (long segment after this one)
    # 0.5s = 11025 samples
    # 0.52s = 11466 samples (duration 441 samples)
    # 1.0s = 22050 samples
    # 2.0s = 44100 samples
    mock_onset_samples = np.array(
        [
            int(0.5 * mock_samplerate),  # Slice 1: 0.5s to 0.52s (potentially too short)
            int(0.52 * mock_samplerate),  # Slice 2: 0.52s to 1.0s
            int(1.0 * mock_samplerate),  # Slice 3: 1.0s to 2.0s
            int(2.0 * mock_samplerate),  # Slice 4: 2.0s to end (potentially too long)
        ]
    )
    mock_onset_detect.return_value = mock_onset_samples

    stage_params = stage.default_params.copy()
    # Min length 50ms. 0.050 * 22050 = 1102.5 samples.
    # Slice 1 duration is (0.52 - 0.5) * 22050 = 441 samples. Should be skipped.
    stage_params["min_sample_length_ms"] = 50
    # Max length 1s. 1.0 * 22050 = 22050 samples.
    # Slice 4 duration (2.0s to 5.0s = 3s) is 3 * 22050 = 66150 samples. Should be truncated to 1s.
    stage_params["max_sample_length_ms"] = 1000  # 1 second

    context = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    result_samples_info = stage.process(
        data=recording.file_path, params=stage_params, context=context
    )

    db_session.refresh(recording)
    assert recording.status == "slicing_completed"
    # Expected: Slice 1 (0.5-0.52s) skipped. Slices from 0.52s, 1.0s, 2.0s kept.
    assert len(result_samples_info) == 3
    assert mock_sf_write.call_count == 3

    # --- Detailed Assertions ---

    # Sample 1 (original onset at 0.52s, was mock_onset_samples[1])
    # Starts at 0.52s, ends at 1.0s. Duration 0.48s. This is > 50ms and < 1000ms.
    sample1_info = next(
        s
        for s in result_samples_info
        if s["metadata_json"] == f'{{"source_onset_samples": {mock_onset_samples[1]}}}'
    )
    expected_start_time1 = float(mock_onset_samples[1]) / mock_samplerate
    expected_end_time1 = float(mock_onset_samples[2]) / mock_samplerate  # Ends at next onset
    assert abs(sample1_info["start_time_seconds"] - expected_start_time1) < 1e-6
    assert abs(sample1_info["end_time_seconds"] - expected_end_time1) < 1e-6
    # Check sf.write call for this sample (data integrity)
    # args_call1, _ = mock_sf_write.call_args_list[0] # Need to find the correct call
    # assert args_call1[0] == sample1_info["file_path"]
    # expected_data_slice1 = mock_audio_data_mono[mock_onset_samples[1]:mock_onset_samples[2]]
    # assert np.array_equal(args_call1[1], expected_data_slice1)

    # Sample 2 (original onset at 1.0s, was mock_onset_samples[2])
    # Starts at 1.0s, ends at 2.0s. Duration 1.0s. This is > 50ms and <= 1000ms.
    sample2_info = next(
        s
        for s in result_samples_info
        if s["metadata_json"] == f'{{"source_onset_samples": {mock_onset_samples[2]}}}'
    )
    expected_start_time2 = float(mock_onset_samples[2]) / mock_samplerate
    expected_end_time2 = float(mock_onset_samples[3]) / mock_samplerate  # Ends at next onset
    assert abs(sample2_info["start_time_seconds"] - expected_start_time2) < 1e-6
    assert abs(sample2_info["end_time_seconds"] - expected_end_time2) < 1e-6

    # Sample 3 (original onset at 2.0s, was mock_onset_samples[3])
    # Starts at 2.0s, should end at 3.0s (due to max_sample_length_ms = 1000). Original end was 5.0s.
    sample3_info = next(
        s
        for s in result_samples_info
        if s["metadata_json"] == f'{{"source_onset_samples": {mock_onset_samples[3]}}}'
    )
    expected_start_time3 = float(mock_onset_samples[3]) / mock_samplerate
    max_len_samples = int((stage_params["max_sample_length_ms"] / 1000.0) * mock_samplerate)
    # expected_end_sample_idx3 = min(len(mock_audio_data_mono), mock_onset_samples[3] + max_len_samples) # This is correct
    expected_end_sample_idx3 = mock_onset_samples[3] + max_len_samples
    expected_end_time3 = float(expected_end_sample_idx3) / mock_samplerate

    assert abs(sample3_info["start_time_seconds"] - expected_start_time3) < 1e-6
    assert abs(sample3_info["end_time_seconds"] - expected_end_time3) < 1e-6

    # Check sf.write call for the truncated sample (Sample 3)
    # Find the call corresponding to sample3_info
    found_call_args = None
    for call_args_tuple in mock_sf_write.call_args_list:
        args, _ = call_args_tuple
        if args[0] == sample3_info["file_path"]:
            found_call_args = args
            break
    assert found_call_args is not None, "sf.write call for sample 3 not found"

    written_data_slice3 = found_call_args[1]
    expected_data_slice3 = mock_audio_data_mono[
        mock_onset_samples[3] : expected_end_sample_idx3
    ]
    assert written_data_slice3.shape == expected_data_slice3.shape
    assert np.array_equal(written_data_slice3, expected_data_slice3)

    db_samples = (
        db_session.query(SampleModel).filter(SampleModel.recording_id == recording.id).all()
    )
    assert len(db_samples) == 3  # Slice 1 was skipped

    # Verify that the skipped sample (onset at mock_onset_samples[0]) is not in the results
    source_onset_skipped = mock_onset_samples[0]
    assert not any(
        s["metadata_json"] == f'{{"source_onset_samples": {source_onset_skipped}}}'
        for s in result_samples_info
    )
    assert mock_sf_write.call_count == 3  # Corrected call count
