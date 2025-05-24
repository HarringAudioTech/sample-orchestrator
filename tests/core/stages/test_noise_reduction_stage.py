"""
Unit tests for the NoiseReductionStage audio processing stage.

This module tests the properties of the NoiseReductionStage and its
placeholder `process` method, including parameter handling, input type
validation, and basic data manipulation.
"""
import logging # Standard library first

import numpy as np # Third-party
import pytest # Third-party

from src.core.processing_stages import DATA_TYPE_AUDIO_BUFFER_MONO # Local application
from src.core.stages.noise_reduction_stage import NoiseReductionStage # Local application

logger = logging.getLogger(__name__)

# --- NoiseReductionStage Tests ---


def test_noise_reduction_stage_properties():
    """
    Test the basic properties of the NoiseReductionStage (name, description, types, params).
    """
    stage = NoiseReductionStage()
    assert stage.name == "noise_reduction"
    assert stage.description, "Description should not be empty." # More direct check
    assert stage.input_type == DATA_TYPE_AUDIO_BUFFER_MONO
    assert stage.output_type == DATA_TYPE_AUDIO_BUFFER_MONO
    assert "amount" in stage.default_params
    assert "aggressiveness" in stage.default_params


def test_noise_reduction_stage_process_success():
    """
    Test the `process` method with valid input and both default and overridden
    parameters. Verifies the placeholder logic (attenuation) and output type.
    """
    stage = NoiseReductionStage()
    dummy_input_data = np.array([0.1, -0.2, 0.3, -0.4, 0.5], dtype=np.float32)

    # Test with default parameters
    params_default = stage.default_params.copy()
    context_default = {"project_id": 1, "recording_id": 10}

    logger.info("Testing NoiseReductionStage with default parameters...")
    output_data_default = stage.process(
        np.copy(dummy_input_data),
        params_default,
        context_default)

    assert isinstance(output_data_default, np.ndarray)
    assert output_data_default.shape == dummy_input_data.shape
    # Check the placeholder logic (attenuation by 0.98)
    expected_output_default = dummy_input_data * 0.98
    np.testing.assert_array_almost_equal(
        output_data_default, expected_output_default, decimal=5)

    # Test with overridden parameters
    params_override = {"amount": 0.8, "aggressiveness": 5}
    context_override = {"some_other_key": "value"}  # Context can vary

    logger.info("Testing NoiseReductionStage with overridden parameters...")
    output_data_override = stage.process(
        np.copy(dummy_input_data),
        params_override,
        context_override)

    assert isinstance(output_data_override, np.ndarray)
    assert output_data_override.shape == dummy_input_data.shape
    # Placeholder logic is the same, parameters are logged but don't change
    # behavior in placeholder
    expected_output_override = dummy_input_data * 0.98
    np.testing.assert_array_almost_equal(
        output_data_override,
        expected_output_override,
        decimal=5
    )


def test_noise_reduction_stage_process_logs_parameters(caplog):
    """
    Test that the `process` method logs the parameters it's using at INFO level.
    """
    stage = NoiseReductionStage()
    dummy_input_data = np.array([0.1, 0.2], dtype=np.float32)
    params = {"amount": 0.7, "aggressiveness": 4}

    with caplog.at_level(logging.INFO):
        stage.process(dummy_input_data, params, {})

    # Check for specific parts in the log text to confirm parameters are logged
    assert f"[{stage.name}] Applying noise reduction (placeholder)..." in caplog.text
    log_text = caplog.text
    # Example check for parameter logging (adapt if log format changes)
    assert f"Parameters: amount={params['amount']}" in log_text
    assert f"aggressiveness={params['aggressiveness']}" in log_text
    assert f"Input data shape: {dummy_input_data.shape}" in log_text


def test_noise_reduction_stage_invalid_input_type():
    """
    Test that the `process` method raises a TypeError if the input data
    is not a NumPy array as expected.
    """
    stage = NoiseReductionStage()
    invalid_data = [0.1, 0.2, 0.3]  # This is a list, not a NumPy array
    params = stage.default_params
    
    expected_error_message = f"Input data for {stage.name} must be a NumPy array."
    with pytest.raises(TypeError, match=expected_error_message):
        stage.process(invalid_data, params, {})


def test_noise_reduction_stage_empty_input_array():
    """
    Test the `process` method with an empty NumPy array.
    It should return an empty NumPy array of the same shape.
    """
    stage = NoiseReductionStage()
    empty_input_data = np.array([], dtype=np.float32)
    params = stage.default_params

    output_data = stage.process(empty_input_data, params, {})
    assert isinstance(output_data, np.ndarray), "Output should be a NumPy array."
    assert output_data.shape == (0,), "Output array should be empty and have correct shape."