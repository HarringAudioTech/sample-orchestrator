"""
Unit tests for the NoiseReductionStage.
"""

import pytest
import numpy as np
import logging

from src.core.processing_stages import DATA_TYPE_AUDIO_BUFFER_MONO
from src.core.stages.noise_reduction_stage import NoiseReductionStage

logger = logging.getLogger(__name__)

# --- NoiseReductionStage Tests ---


def test_noise_reduction_stage_properties():
    stage = NoiseReductionStage()
    assert stage.name == "noise_reduction"
    assert stage.description is not None  # Check it's not empty
    assert stage.input_type == DATA_TYPE_AUDIO_BUFFER_MONO
    assert stage.output_type == DATA_TYPE_AUDIO_BUFFER_MONO
    assert "amount" in stage.default_params
    assert "aggressiveness" in stage.default_params


def test_noise_reduction_stage_process_success():
    stage = NoiseReductionStage()
    # Create a dummy NumPy array for input
    dummy_input_data = np.array([0.1, -0.2, 0.3, -0.4, 0.5], dtype=np.float32)

    # Test with default parameters
    params_default = stage.default_params.copy()
    context_default = {"project_id": 1, "recording_id": 10}

    logger.info("Testing NoiseReductionStage with default parameters...")
    output_data_default = stage.process(
        np.copy(dummy_input_data), params_default, context_default
    )

    assert isinstance(output_data_default, np.ndarray)
    assert output_data_default.shape == dummy_input_data.shape
    # Check the placeholder logic (attenuation by 0.98)
    expected_output_default = dummy_input_data * 0.98
    np.testing.assert_array_almost_equal(
        output_data_default, expected_output_default, decimal=5
    )

    # Test with overridden parameters
    params_override = {"amount": 0.8, "aggressiveness": 5}
    context_override = {"some_other_key": "value"}  # Context can vary

    logger.info("Testing NoiseReductionStage with overridden parameters...")
    output_data_override = stage.process(
        np.copy(dummy_input_data), params_override, context_override
    )

    assert isinstance(output_data_override, np.ndarray)
    assert output_data_override.shape == dummy_input_data.shape
    # Placeholder logic is the same, parameters are logged but don't change
    # behavior in placeholder
    expected_output_override = dummy_input_data * 0.98
    np.testing.assert_array_almost_equal(
        output_data_override, expected_output_override, decimal=5
    )


def test_noise_reduction_stage_process_logs_parameters(caplog):
    stage = NoiseReductionStage()
    dummy_input_data = np.array([0.1, 0.2], dtype=np.float32)
    params = {"amount": 0.7, "aggressiveness": 4}

    with caplog.at_level(logging.INFO):
        stage.process(dummy_input_data, params, {})

    assert f"[{stage.name}] Applying noise reduction (placeholder)..." in caplog.text
    assert (
        f"Parameters: amount={
            params['amount']}, aggressiveness={
            params['aggressiveness']}"
        in caplog.text
    )
    assert f"Input data shape: {dummy_input_data.shape}" in caplog.text


def test_noise_reduction_stage_invalid_input_type():
    stage = NoiseReductionStage()
    invalid_data = [0.1, 0.2, 0.3]  # Not a NumPy array
    params = stage.default_params

    with pytest.raises(TypeError, match=f"Input data for {stage.name} must be a NumPy array."):
        stage.process(invalid_data, params, {})


def test_noise_reduction_stage_empty_input_array():
    stage = NoiseReductionStage()
    empty_input_data = np.array([], dtype=np.float32)
    params = stage.default_params

    output_data = stage.process(empty_input_data, params, {})
    assert isinstance(output_data, np.ndarray)
    assert output_data.shape == (0,)  # Expect an empty array of the same shape
