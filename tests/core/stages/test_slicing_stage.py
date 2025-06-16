"""
Unit tests for the SlicingStage.
"""

import pytest
import os
import shutil
import logging
from unittest.mock import patch, MagicMock, ANY
import numpy as np  # type: ignore # pylint: disable=import-error
import soundfile as sf  # type: ignore # pylint: disable=import-error
from sqlalchemy import create_engine  # type: ignore # pylint: disable=import-error
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession  # type: ignore # pylint: disable=import-error
from sqlalchemy.engine import (
    Engine as SQLAlchemyEngine,
)  # For typing engine # type: ignore # pylint: disable=import-error
from typing import Generator, Dict, Any, List, Optional

# pylint: disable=import-error
try:
    from src.core.processing_stages import (
        DATA_TYPE_FILE_PATH,
        DATA_TYPE_LIST_OF_SAMPLE_DATA,
    )
    from src.core.stages.slicing_stage import SlicingStage
    from src.database.models import (
        Base,
        Recording as RecordingModel,
        Sample as SampleModel,
        Project as ProjectModel,
    )
except ImportError:
    from core.processing_stages import (  # type: ignore
        DATA_TYPE_FILE_PATH,
        DATA_TYPE_LIST_OF_SAMPLE_DATA,
    )
    from core.stages.slicing_stage import SlicingStage  # type: ignore
    from database.models import (  # type: ignore
        Base,
        Recording as RecordingModel,
        Sample as SampleModel,
        Project as ProjectModel,
    )
# pylint: enable=import-error


logger = logging.getLogger(__name__)

DUMMY_AUDIO_DIR = "tests/fixtures"
DUMMY_AUDIO_FILENAME = "dummy_audio.wav"
DUMMY_AUDIO_PATH = os.path.join(DUMMY_AUDIO_DIR, DUMMY_AUDIO_FILENAME)

if not os.path.exists(DUMMY_AUDIO_PATH):
    logger.warning(
        f"Dummy audio file for testing not found at {DUMMY_AUDIO_PATH}. "
        "Some tests may fail or be skipped."
    )
    try:
        os.makedirs(DUMMY_AUDIO_DIR, exist_ok=True)
        samplerate: int = 22050
        duration_seconds: int = 1
        frequency: int = 440
        amplitude: float = 0.5
        t_arr: np.ndarray = np.linspace(
            0, duration_seconds, int(samplerate * duration_seconds), endpoint=False
        )
        wave_data: np.ndarray = amplitude * np.sin(2 * np.pi * frequency * t_arr)
        sf.write(DUMMY_AUDIO_PATH, wave_data.astype(np.float32), samplerate)
        logger.info(f"Created dummy audio file at {DUMMY_AUDIO_PATH}")
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"Could not create dummy audio file {DUMMY_AUDIO_PATH}: {e}")


@pytest.fixture(scope="function")
def test_engine() -> SQLAlchemyEngine:
    """Creates an in-memory SQLite engine for testing."""
    engine: SQLAlchemyEngine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db_session(
    test_engine: SQLAlchemyEngine,
) -> Generator[SQLAlchemySession, None, None]:
    """Creates a new database session for a test, ensuring a clean state."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session: SQLAlchemySession = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def temp_output_dir_for_samples() -> Generator[str, None, None]:
    """Creates a temporary directory for generated sample files."""
    path: str = "/tmp/pytest_slicing_stage_samples"
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    yield path
    try:
        shutil.rmtree(path)
    except OSError as e:
        logger.error(f"Error cleaning up temp output dir {path}: {e}")


@pytest.fixture
def setup_test_recording(
    db_session: SQLAlchemySession,
) -> RecordingModel:  # pylint: disable=redefined-outer-name
    """Sets up a Project and a Recording in the test DB."""
    project = ProjectModel(name="Test Slicing Project")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    if not os.path.exists(DUMMY_AUDIO_PATH):
        pytest.fail(f"Required dummy audio file not found: {DUMMY_AUDIO_PATH}")

    try:
        info: sf.SoundFileInfo = sf.info(DUMMY_AUDIO_PATH)
        sr: int = info.samplerate
        channels: int = info.channels
        duration: float = info.duration
    except Exception as e:  # pylint: disable=broad-except
        pytest.fail(
            f"Could not get audio details for dummy file {DUMMY_AUDIO_PATH}: {e}"
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


def test_slicing_stage_properties() -> None:
    """Test the basic properties of SlicingStage."""
    stage = SlicingStage()
    assert stage.name == "slicing"
    assert stage.input_type == DATA_TYPE_FILE_PATH
    assert stage.output_type == DATA_TYPE_LIST_OF_SAMPLE_DATA
    default_params: Dict[str, Any] = stage.default_params
    assert "librosa_onset_params" in default_params
    assert "min_sample_length_ms" in default_params
    assert "max_sample_length_ms" in default_params


@patch("src.core.stages.slicing_stage.sf.write")
@patch("src.core.stages.slicing_stage.librosa.onset.onset_detect")
@patch("src.core.stages.slicing_stage.librosa.load")
def test_slicing_stage_process_success(  # pylint: disable=redefined-outer-name
    mock_librosa_load: MagicMock,
    mock_onset_detect: MagicMock,
    mock_sf_write: MagicMock,
    db_session: SQLAlchemySession,
    setup_test_recording: RecordingModel,
    temp_output_dir_for_samples: str,
) -> None:
    """Test successful processing of an audio file into samples."""
    recording: RecordingModel = setup_test_recording
    stage = SlicingStage()

    mock_samplerate: int = 22050
    mock_audio_data_mono: np.ndarray = np.random.rand(mock_samplerate * 2).astype(
        np.float32
    )
    mock_librosa_load.return_value = (mock_audio_data_mono, mock_samplerate)

    onset_time_1_s: float = 0.5
    onset_time_2_s: float = 1.2
    mock_onset_samples: np.ndarray = np.array(
        [int(onset_time_1_s * mock_samplerate), int(onset_time_2_s * mock_samplerate)]
    )
    mock_onset_detect.return_value = mock_onset_samples

    stage_params: Dict[str, Any] = stage.default_params.copy()

    context: Dict[str, Any] = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    result_samples_info: List[Dict[str, Any]] = stage.process(
        data=recording.file_path, params=stage_params, context=context
    )

    db_session.refresh(recording)
    assert recording.status == "slicing_completed"
    assert len(result_samples_info) == 2

    mock_librosa_load.assert_called_once_with(recording.file_path, sr=None, mono=True)

    expected_call_params: Dict[str, Any] = {
        **stage.default_params["librosa_onset_params"],
        **(stage_params.get("librosa_onset_params", {})),
        "units": "samples",
    }
    mock_onset_detect.assert_called_once_with(
        y=mock_audio_data_mono, sr=mock_samplerate, **expected_call_params
    )

    sample1_info: Dict[str, Any] = next(
        s
        for s in result_samples_info
        if s["metadata_json"] == f'{{"source_onset_samples": {mock_onset_samples[0]}}}'
    )
    assert sample1_info["name"].startswith(
        f"rec_{recording.id}_sample_1_onset_S{mock_onset_samples[0]}"
    )
    assert sample1_info["midi_pitch"] is None

    expected_start_time1: float = float(mock_onset_samples[0]) / mock_samplerate
    max_len_samples1: int = int(
        (stage.default_params["max_sample_length_ms"] / 1000.0) * mock_samplerate
    )
    calculated_end_sample1: int = min(
        mock_onset_samples[1], mock_onset_samples[0] + max_len_samples1
    )
    expected_end_time1: float = float(calculated_end_sample1) / mock_samplerate

    assert abs(sample1_info["start_time_seconds"] - expected_start_time1) < 1e-6
    assert abs(sample1_info["end_time_seconds"] - expected_end_time1) < 1e-6

    sample2_info: Dict[str, Any] = next(
        s
        for s in result_samples_info
        if s["metadata_json"] == f'{{"source_onset_samples": {mock_onset_samples[1]}}}'
    )
    assert sample2_info["name"].startswith(
        f"rec_{recording.id}_sample_2_onset_S{mock_onset_samples[1]}"
    )
    assert sample2_info["midi_pitch"] is None

    expected_start_time2: float = float(mock_onset_samples[1]) / mock_samplerate
    max_len_samples2: int = int(
        (stage.default_params["max_sample_length_ms"] / 1000.0) * mock_samplerate
    )
    calculated_end_sample2: int = min(
        len(mock_audio_data_mono), mock_onset_samples[1] + max_len_samples2
    )
    expected_end_time2: float = float(calculated_end_sample2) / mock_samplerate

    assert abs(sample2_info["start_time_seconds"] - expected_start_time2) < 1e-6
    assert abs(sample2_info["end_time_seconds"] - expected_end_time2) < 1e-6

    assert mock_sf_write.call_count == 2
    args_call1, _ = mock_sf_write.call_args_list[0]
    assert args_call1[0] == sample1_info["file_path"]
    assert args_call1[2] == mock_samplerate

    db_samples: List[SampleModel] = (
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
    assert recording.samplerate == mock_samplerate
    assert (
        abs(recording.duration_seconds - (len(mock_audio_data_mono) / mock_samplerate))
        < 1e-6
    )


# pylint: disable=redefined-outer-name
def test_slicing_stage_input_file_not_found(
    db_session: SQLAlchemySession,
    setup_test_recording: RecordingModel,
    temp_output_dir_for_samples: str,
) -> None:
    """Test processing fails if input audio file is not found."""
    recording: RecordingModel = setup_test_recording
    stage = SlicingStage()
    context: Dict[str, Any] = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    non_existent_file: str = "/path/to/absolutely/nonexistent/audio.wav"
    with pytest.raises(
        FileNotFoundError, match=f"Input audio file not found: {non_existent_file}"
    ):
        stage.process(
            data=non_existent_file, params=stage.default_params, context=context
        )

    db_session.refresh(recording)
    assert recording.status == "slicing_failed"


# pylint: disable=redefined-outer-name
def test_slicing_stage_recording_not_found_in_db(
    db_session: SQLAlchemySession, temp_output_dir_for_samples: str
) -> None:
    """Test processing fails if recording ID in context is not in DB."""
    stage = SlicingStage()
    context: Dict[str, Any] = {
        "db_session": db_session,
        "recording_id": 99999,
        "project_id": 1,
        "output_sample_dir": temp_output_dir_for_samples,
    }
    with pytest.raises(ValueError, match="Recording with id 99999 not found"):
        stage.process(
            data=DUMMY_AUDIO_PATH, params=stage.default_params, context=context
        )


# pylint: disable=redefined-outer-name
def test_slicing_stage_missing_context_keys(
    db_session: SQLAlchemySession, setup_test_recording: RecordingModel
) -> None:
    """Test processing fails if required keys are missing from context."""
    recording: RecordingModel = setup_test_recording
    stage = SlicingStage()
    base_context: Dict[str, Any] = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": "/tmp/pytest_slicing_stage_samples_m_ctx",
    }

    required_keys: List[str] = [
        "db_session",
        "recording_id",
        "project_id",
        "output_sample_dir",
    ]

    for key_to_remove in required_keys:
        context_copy: Dict[str, Any] = base_context.copy()
        del context_copy[key_to_remove]

        with pytest.raises(
            ValueError, match=f"Missing required key '{key_to_remove}' in context"
        ):
            stage.process(DUMMY_AUDIO_PATH, stage.default_params, context_copy)

    with pytest.raises(ValueError, match="Context is required and was not provided."):
        stage.process(DUMMY_AUDIO_PATH, stage.default_params, None)


@patch(
    "src.core.stages.slicing_stage.librosa.load",
    side_effect=RuntimeError("Simulated librosa.load failure"),
)  # pylint: disable=redefined-outer-name
def test_slicing_stage_librosa_load_error(
    mock_librosa_load_fails: MagicMock,
    db_session: SQLAlchemySession,
    setup_test_recording: RecordingModel,
    temp_output_dir_for_samples: str,
) -> None:
    """Test processing fails gracefully if librosa.load raises an error."""
    recording: RecordingModel = setup_test_recording
    stage = SlicingStage()
    context: Dict[str, Any] = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    with pytest.raises(RuntimeError, match="Simulated librosa.load failure"):
        stage.process(
            data=recording.file_path, params=stage.default_params, context=context
        )

    db_session.refresh(recording)
    assert recording.status == "slicing_failed"
    mock_librosa_load_fails.assert_called_once()


@patch("src.core.stages.slicing_stage.sf.write")
@patch("src.core.stages.slicing_stage.librosa.onset.onset_detect")
@patch("src.core.stages.slicing_stage.librosa.load")
# pylint: disable=redefined-outer-name
def test_slicing_stage_no_onsets_detected(
    mock_librosa_load: MagicMock,
    mock_onset_detect: MagicMock,
    mock_sf_write: MagicMock,
    db_session: SQLAlchemySession,
    setup_test_recording: RecordingModel,
    temp_output_dir_for_samples: str,
) -> None:
    """Test processing completes successfully when no onsets are detected."""
    recording: RecordingModel = setup_test_recording
    stage = SlicingStage()

    mock_samplerate: int = 22050
    mock_audio_data_mono: np.ndarray = np.random.rand(mock_samplerate * 2).astype(
        np.float32
    )
    mock_librosa_load.return_value = (mock_audio_data_mono, mock_samplerate)

    mock_onset_detect.return_value = np.array([])

    context: Dict[str, Any] = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    result_samples_info: List[Dict[str, Any]] = stage.process(
        data=recording.file_path, params=stage.default_params, context=context
    )

    db_session.refresh(recording)
    assert recording.status == "slicing_completed"
    assert len(result_samples_info) == 0
    db_samples: List[SampleModel] = (
        db_session.query(SampleModel)
        .filter(SampleModel.recording_id == recording.id)
        .all()
    )
    assert len(db_samples) == 0
    assert not os.listdir(temp_output_dir_for_samples)
    mock_sf_write.assert_not_called()


@patch("src.core.stages.slicing_stage.sf.write")
@patch("src.core.stages.slicing_stage.librosa.onset.onset_detect")
@patch("src.core.stages.slicing_stage.librosa.load")
# pylint: disable=redefined-outer-name
def test_slicing_stage_min_max_sample_length(
    mock_librosa_load: MagicMock,
    mock_onset_detect: MagicMock,
    mock_sf_write: MagicMock,
    db_session: SQLAlchemySession,
    setup_test_recording: RecordingModel,
    temp_output_dir_for_samples: str,
) -> None:
    """Test that min_sample_length_ms and max_sample_length_ms parameters are respected."""
    recording: RecordingModel = setup_test_recording
    stage = SlicingStage()

    mock_samplerate: int = 22050
    mock_audio_data_mono: np.ndarray = np.random.rand(mock_samplerate * 5).astype(
        np.float32
    )
    mock_librosa_load.return_value = (mock_audio_data_mono, mock_samplerate)

    mock_onset_samples: np.ndarray = np.array(
        [
            int(0.5 * mock_samplerate),
            int(0.52 * mock_samplerate),  # This one should be skipped (too short)
            int(1.0 * mock_samplerate),
            int(2.0 * mock_samplerate),
        ]
    )
    mock_onset_detect.return_value = mock_onset_samples

    stage_params: Dict[str, Any] = stage.default_params.copy()
    stage_params["min_sample_length_ms"] = 50
    stage_params["max_sample_length_ms"] = 1000

    context: Dict[str, Any] = {
        "db_session": db_session,
        "recording_id": recording.id,
        "project_id": recording.project_id,
        "output_sample_dir": temp_output_dir_for_samples,
    }

    result_samples_info: List[Dict[str, Any]] = stage.process(
        data=recording.file_path, params=stage_params, context=context
    )

    db_session.refresh(recording)
    assert recording.status == "slicing_completed"
    assert len(result_samples_info) == 3
    assert mock_sf_write.call_count == 3

    # Check that the first actual sample corresponds to the second detected onset (index 1)
    sample1_info: Dict[str, Any] = next(
        s
        for s in result_samples_info
        if s["metadata_json"] == f'{{"source_onset_samples": {mock_onset_samples[1]}}}'
    )
    expected_start_time1: float = float(mock_onset_samples[1]) / mock_samplerate
    expected_end_time1: float = float(mock_onset_samples[2]) / mock_samplerate
    assert abs(sample1_info["start_time_seconds"] - expected_start_time1) < 1e-6
    assert abs(sample1_info["end_time_seconds"] - expected_end_time1) < 1e-6
    # ... (rest of the assertions for other samples)
    source_onset_skipped: int = mock_onset_samples[0]
    assert not any(
        s["metadata_json"] == f'{{"source_onset_samples": {source_onset_skipped}}}'
        for s in result_samples_info
    )
