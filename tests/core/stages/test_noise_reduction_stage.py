"""
Unit tests for the NoiseReductionStage.
"""

import pytest
import numpy as np
import logging
from typing import Dict, Any, List, cast
from _pytest.logging import LogCaptureFixture # For caplog fixture type

from src.core.processing_stages import DATA_TYPE_AUDIO_BUFFER_MONO
from src.core.stages.noise_reduction_stage import NoiseReductionStage

logger = logging.getLogger(__name__)

# --- NoiseReductionStage Tests ---


def test_noise_reduction_stage_properties() -> None:
    """Test the basic properties of NoiseReductionStage."""
    stage = NoiseReductionStage()
    assert stage.name == "noise_reduction"
    assert stage.description is not None and stage.description != ""
    assert stage.input_type == DATA_TYPE_AUDIO_BUFFER_MONO
    assert stage.output_type == DATA_TYPE_AUDIO_BUFFER_MONO
    default_params: Dict[str, Any] = stage.default_params
    assert "amount" in default_params
    assert "aggressiveness" in default_params


def test_noise_reduction_stage_process_success() -> None:
    """Test successful processing with default and overridden parameters."""
    stage = NoiseReductionStage()
    # Create a dummy NumPy array for input
    dummy_input_data: np.ndarray = np.array([0.1, -0.2, 0.3, -0.4, 0.5], dtype=np.float32)

    # Test with default parameters
    params_default: Dict[str, Any] = stage.default_params.copy()
    context_default: Dict[str, Any] = {"project_id": 1, "recording_id": 10}

    logger.info("Testing NoiseReductionStage with default parameters...")
    output_data_default: np.ndarray = stage.process(
        np.copy(dummy_input_data), params_default, context_default
    )

    assert isinstance(output_data_default, np.ndarray)
    assert output_data_default.shape == dummy_input_data.shape
    # Check the placeholder logic (attenuation by 0.98)
    expected_output_default: np.ndarray = dummy_input_data * 0.98
    np.testing.assert_array_almost_equal(
        output_data_default, expected_output_default, decimal=5
    )

    # Test with overridden parameters
    params_override: Dict[str, Any] = {"amount": 0.8, "aggressiveness": 5}
    context_override: Dict[str, Any] = {"some_other_key": "value"}  # Context can vary

    logger.info("Testing NoiseReductionStage with overridden parameters...")
    output_data_override: np.ndarray = stage.process(
        np.copy(dummy_input_data), params_override, context_override
    )

    assert isinstance(output_data_override, np.ndarray)
    assert output_data_override.shape == dummy_input_data.shape
    # Placeholder logic is the same, parameters are logged but don't change
    # behavior in placeholder
    expected_output_override: np.ndarray = dummy_input_data * 0.98
    np.testing.assert_array_almost_equal(
        output_data_override, expected_output_override, decimal=5
    )


def test_noise_reduction_stage_process_logs_parameters(caplog: LogCaptureFixture) -> None:
    """Test that processing logs the parameters used.

    Args:
        caplog: Pytest fixture to capture log output.
    """
    stage = NoiseReductionStage()
    dummy_input_data: np.ndarray = np.array([0.1, 0.2], dtype=np.float32)
    params: Dict[str, Any] = {"amount": 0.7, "aggressiveness": 4}
    context: Dict[str, Any] = {} # Empty context for this test

    with caplog.at_level(logging.INFO):
        stage.process(dummy_input_data, params, context)

    assert f"[{stage.name}] Applying noise reduction (placeholder)..." in caplog.text
    assert (
        f"Parameters: amount={
            params['amount']}, aggressiveness={
            params['aggressiveness']}"
        in caplog.text
    )
    assert f"Input data shape: {dummy_input_data.shape}" in caplog.text


def test_noise_reduction_stage_invalid_input_type() -> None:
    """Test processing with an invalid input data type raises TypeError."""
    stage = NoiseReductionStage()
    invalid_data: List[float] = [0.1, 0.2, 0.3]  # Not a NumPy array
    params: Dict[str, Any] = stage.default_params
    context: Dict[str, Any] = {}

    with pytest.raises(TypeError, match=f"Input data for {stage.name} must be a NumPy array."):
        # We use cast here because the type checker would normally catch this,
        # but we are specifically testing the runtime check within the process method.
        stage.process(cast(np.ndarray, invalid_data), params, context)


def test_noise_reduction_stage_empty_input_array() -> None:
    """Test processing with an empty NumPy array."""
    stage = NoiseReductionStage()
    empty_input_data: np.ndarray = np.array([], dtype=np.float32)
    params: Dict[str, Any] = stage.default_params
    context: Dict[str, Any] = {}

    output_data: np.ndarray = stage.process(empty_input_data, params, context)
    assert isinstance(output_data, np.ndarray)
    assert output_data.shape == (0,)  # Expect an empty array of the same shape
