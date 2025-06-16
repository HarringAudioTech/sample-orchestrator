import pytest
import numpy as np
import logging
from unittest.mock import (
    patch,
)  # For mocker.patch if pytest-mock isn't auto-imported as 'mocker'

from src.core.stages.noise_reduction_stage import NoiseReductionStage

# Assuming AudioProcessingContext might be a defined class/dataclass,
# otherwise a Dict is fine. For now, Dict is used as per stage.
# from src.core.audio_processing_context import AudioProcessingContext

# Logger for this test module (optional, but good practice)
logger = logging.getLogger(__name__)


@pytest.fixture
def noise_reduction_stage() -> NoiseReductionStage:
    """Fixture to create a NoiseReductionStage instance."""
    return NoiseReductionStage()


@pytest.fixture
def dummy_audio_data() -> np.ndarray:
    """Fixture for dummy audio data."""
    # Create a simple sine wave as dummy data to make it more predictable than random
    sample_rate = 44100
    duration = 0.1  # seconds
    frequency = 440  # Hz (A4 note)
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * frequency * t)
    return audio.astype(np.float32)


@pytest.fixture
def sample_rate() -> int:
    """Fixture for a sample sample rate."""
    return 44100


def test_successful_noise_reduction(
    noise_reduction_stage: NoiseReductionStage,
    dummy_audio_data: np.ndarray,
    sample_rate: int,
    mocker,  # pytest-mock fixture
) -> None:
    """Test that noisereduce.reduce_noise is called correctly and its output is returned."""
    # We need to mock 'noisereduce.reduce_noise' within the module where it's imported and used.
    # Assuming NoiseReductionStage imports it as 'import noisereduce',
    # the path is 'src.core.stages.noise_reduction_stage.noisereduce.reduce_noise'
    mock_reduce_noise = mocker.patch(
        "src.core.stages.noise_reduction_stage.noisereduce.reduce_noise"
    )

    # Configure the mock to return a slightly different array to distinguish it
    reduced_audio_data = dummy_audio_data * 0.5
    mock_reduce_noise.return_value = reduced_audio_data

    params = noise_reduction_stage.default_params
    context = {"sample_rate": sample_rate}

    processed_data = noise_reduction_stage.process(
        data=np.copy(dummy_audio_data), params=params, context=context
    )

    mock_reduce_noise.assert_called_once()
    call_args = mock_reduce_noise.call_args
    assert call_args is not None
    np.testing.assert_array_equal(call_args.kwargs["y"], dummy_audio_data)
    assert call_args.kwargs["sr"] == sample_rate
    np.testing.assert_array_equal(processed_data, reduced_audio_data)
    logger.info("Successfully tested noise reduction call and output handling.")


def test_missing_sample_rate_in_context(
    noise_reduction_stage: NoiseReductionStage,
    dummy_audio_data: np.ndarray,
    caplog,  # pytest's built-in log capture
    mocker,
) -> None:
    """Test behavior when sample_rate is missing from context and reduce_noise fails."""
    mock_reduce_noise = mocker.patch(
        "src.core.stages.noise_reduction_stage.noisereduce.reduce_noise"
    )

    # This side effect will simulate reduce_noise failing when sr=0
    def side_effect_for_sr_zero(y, sr):
        if sr == 0:
            raise ValueError("Sample rate cannot be 0 for noisereduce")
        return y

    mock_reduce_noise.side_effect = side_effect_for_sr_zero

    params = noise_reduction_stage.default_params
    context_no_sr = {}  # Missing sample_rate

    with caplog.at_level(logging.WARNING):  # Check for warning
        processed_data = noise_reduction_stage.process(
            data=np.copy(dummy_audio_data), params=params, context=context_no_sr
        )

    assert "'sample_rate' not found in context" in caplog.text
    # Check that the error from reduce_noise (due to sr=0) was logged by the stage
    assert (
        "Error during noise reduction: Sample rate cannot be 0 for noisereduce"
        in caplog.text
    )

    mock_reduce_noise.assert_called_once()
    call_args = mock_reduce_noise.call_args
    assert call_args is not None
    np.testing.assert_array_equal(call_args.kwargs["y"], dummy_audio_data)
    assert call_args.kwargs["sr"] == 0
    # Expect original data because the try-except in process should catch the error
    np.testing.assert_array_equal(processed_data, dummy_audio_data)
    logger.info(
        "Successfully tested missing sample_rate leading to reduce_noise failure."
    )


def test_reduce_noise_general_exception(
    noise_reduction_stage: NoiseReductionStage,
    dummy_audio_data: np.ndarray,
    sample_rate: int,
    caplog,
    mocker,
) -> None:
    """Test that the stage handles general exceptions from noisereduce.reduce_noise."""
    mock_reduce_noise = mocker.patch(
        "src.core.stages.noise_reduction_stage.noisereduce.reduce_noise"
    )
    mock_reduce_noise.side_effect = Exception("Generic noisereduce error")

    params = noise_reduction_stage.default_params
    context = {"sample_rate": sample_rate}

    with caplog.at_level(logging.ERROR):
        processed_data = noise_reduction_stage.process(
            data=np.copy(dummy_audio_data), params=params, context=context
        )

    assert "Error during noise reduction: Generic noisereduce error" in caplog.text
    np.testing.assert_array_equal(processed_data, dummy_audio_data)
    logger.info("Successfully tested general exception handling for reduce_noise.")


def test_noise_reduction_invalid_input_type(
    noise_reduction_stage: NoiseReductionStage,
) -> None:
    """Test processing with an invalid input data type raises TypeError."""
    invalid_data = [0.1, 0.2, 0.3]  # Not a NumPy array
    params = noise_reduction_stage.default_params
    context = {"sample_rate": 44100}

    with pytest.raises(
        TypeError,
        match=f"Input data for {noise_reduction_stage.name} must be a NumPy array.",
    ):
        noise_reduction_stage.process(data=invalid_data, params=params, context=context)  # type: ignore
    logger.info("Successfully tested invalid input type handling.")


def test_noise_reduction_stage_properties(
    noise_reduction_stage: NoiseReductionStage,
) -> None:
    """Test the basic properties of NoiseReductionStage."""
    assert noise_reduction_stage.name == "noise_reduction"
    assert (
        noise_reduction_stage.description is not None
        and noise_reduction_stage.description != ""
    )
    # Assuming DATA_TYPE_AUDIO_BUFFER_MONO is "audio_buffer_mono"
    assert noise_reduction_stage.input_type == "audio_buffer_mono"
    assert noise_reduction_stage.output_type == "audio_buffer_mono"
    default_params = noise_reduction_stage.default_params
    assert "amount" in default_params
    assert "aggressiveness" in default_params
    logger.info("Successfully tested stage properties.")


def test_empty_audio_data_processing(
    noise_reduction_stage: NoiseReductionStage, sample_rate: int, mocker
) -> None:
    """Test processing with an empty audio array."""
    mock_reduce_noise = mocker.patch(
        "src.core.stages.noise_reduction_stage.noisereduce.reduce_noise"
    )
    empty_audio_data = np.array([], dtype=np.float32)
    # Assume noisereduce might return an empty array or raise an error if input is empty.
    # If it returns an empty array:
    mock_reduce_noise.return_value = np.array([], dtype=np.float32)

    params = noise_reduction_stage.default_params
    context = {"sample_rate": sample_rate}

    processed_data = noise_reduction_stage.process(
        data=np.copy(empty_audio_data), params=params, context=context
    )

    mock_reduce_noise.assert_called_once()
    call_args = mock_reduce_noise.call_args
    assert call_args is not None
    np.testing.assert_array_equal(call_args.kwargs["y"], empty_audio_data)
    assert call_args.kwargs["sr"] == sample_rate
    np.testing.assert_array_equal(processed_data, empty_audio_data)
    logger.info("Successfully tested processing of empty audio data.")
