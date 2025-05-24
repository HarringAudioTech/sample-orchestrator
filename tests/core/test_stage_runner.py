# pylint: disable=too-many-lines
"""
Unit tests for the `src.core.stage_runner` module.

This module tests the registration of audio processing stages and the
execution of stage chains, including type checking, parameter merging,
and error handling.
"""
import logging
from typing import Any, Dict, List, Type # List was missing for type hints
from unittest.mock import MagicMock, patch

import pytest

from src.core.processing_stages import (
    AudioProcessingStage,
    DATA_TYPE_FILE_PATH,
    DATA_TYPE_AUDIO_BUFFER_MONO
    # DATA_TYPE_LIST_OF_SAMPLE_DATA is not used by these mock stages.
)
from src.core.stage_runner import (
    STAGE_REGISTRY,
    register_stage,
    execute_stage_chain
)

# Configure basic logging for tests (optional, but can be helpful)
# logging.basicConfig(level=logging.DEBUG) # Optional: for test debugging
logger = logging.getLogger(__name__)

# --- Mock AudioProcessingStage Implementations ---

class MockStageAFilePathToBuffer(AudioProcessingStage): # Renamed
    """
    Mock stage: Converts a file path to a mono audio buffer (simulated).
    Logs calls and interactions for test assertions.
    """
    # Class attributes defining stage properties
    _name = "mock_stage_a" # pylint: disable=invalid-name (convention for "private" class attr)
    _description = "Converts file path to mono audio buffer (mocked)."
    _input_type = DATA_TYPE_FILE_PATH
    _output_type = DATA_TYPE_AUDIO_BUFFER_MONO
    _default_params = {"param_a": 1}
    
    call_log: List[Dict[str, Any]] = [] # Store calls for assertion

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def input_type(self) -> str: return self._input_type
    @property
    def output_type(self) -> str: return self._output_type
    @property
    def default_params(self) -> dict: return self._default_params.copy()

    def process(self, data: str, params: dict, context: dict = None) -> list:
        """Simulates processing a file path to an audio buffer list."""
        logger.info("[%s] CALLED with data: %s, params: %s, context: %s",
                    self.name, data, params, context)
        self.call_log.append({"data": data, "params": params, "context": context})
        if not isinstance(data, str):
            raise TypeError(f"{self.name} expected str, got {type(data)}")
        return [0.1, 0.2, 0.3] # Mock audio buffer (list of floats)

class MockStageBBufferToBuffer(AudioProcessingStage): # Renamed
    """
    Mock stage: Processes a mono audio buffer to another mono audio buffer (simulated).
    Logs calls and interactions for test assertions.
    """
    _name = "mock_stage_b"
    _description = "Processes a mono audio buffer (mocked)."
    _input_type = DATA_TYPE_AUDIO_BUFFER_MONO
    _output_type = DATA_TYPE_AUDIO_BUFFER_MONO
    _default_params = {"param_b": "hello"}
    call_log: List[Dict[str, Any]] = []

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def input_type(self) -> str: return self._input_type
    @property
    def output_type(self) -> str: return self._output_type
    @property
    def default_params(self) -> dict: return self._default_params.copy()

    def process(self, data: list, params: dict, context: dict = None) -> list:
        """Simulates processing an audio buffer list."""
        logger.info("[%s] CALLED with data: %s, params: %s, context: %s",
                    self.name, data, params, context)
        self.call_log.append({"data": data, "params": params, "context": context})
        if not isinstance(data, list):
             raise TypeError(f"{self.name} expected list, got {type(data)}")
        return [d * 2 for d in data]

class MockStageCBufferToFilePath(AudioProcessingStage): # Renamed
    """
    Mock stage: Saves a mono audio buffer to a file path (simulated).
    Logs calls and interactions for test assertions.
    """
    _name = "mock_stage_c"
    _description = "Saves a mono audio buffer to a file path (mocked)."
    _input_type = DATA_TYPE_AUDIO_BUFFER_MONO
    _output_type = DATA_TYPE_FILE_PATH
    _default_params = {"output_filename": "output.wav"}
    call_log: List[Dict[str, Any]] = []

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def input_type(self) -> str: return self._input_type
    @property
    def output_type(self) -> str: return self._output_type
    @property
    def default_params(self) -> dict: return self._default_params.copy()

    def process(self, data: list, params: dict, context: dict = None) -> str:
        """Simulates saving an audio buffer and returning a file path."""
        logger.info("[%s] CALLED with data: %s, params: %s, context: %s",
                    self.name, data, params, context)
        self.call_log.append({"data": data, "params": params, "context": context})
        if not isinstance(data, list):
             raise TypeError(f"{self.name} expected list, got {type(data)}")
        # f-string for constructing filename is fine
        return f"/tmp/mock_output/{params.get('output_filename', 'default_out.wav')}"


# --- Fixture to manage STAGE_REGISTRY ---
@pytest.fixture(autouse=True)
def clear_stage_registry_and_logs():
    """
    Clears the STAGE_REGISTRY and mock stage call logs before each test,
    and restores the original registry content after the test.
    This ensures test isolation for stage registration and call logging.
    """
    original_registry = STAGE_REGISTRY.copy()
    STAGE_REGISTRY.clear()
    
    MockStageAFilePathToBuffer.call_log.clear()
    MockStageBBufferToBuffer.call_log.clear()
    MockStageCBufferToFilePath.call_log.clear()
    
    yield # Test runs here
    
    STAGE_REGISTRY.clear()
    STAGE_REGISTRY.update(original_registry)


# --- Tests for register_stage ---
def test_register_stage_success():
    """Test successful registration of a valid stage."""
    register_stage(MockStageAFilePathToBuffer)
    assert MockStageAFilePathToBuffer.name in STAGE_REGISTRY
    assert STAGE_REGISTRY[MockStageAFilePathToBuffer.name] == MockStageAFilePathToBuffer

def test_register_stage_reregistration(caplog):
    """Test that re-registering a stage with the same name overwrites the previous one and logs a warning."""
    register_stage(MockStageAFilePathToBuffer) # Initial registration
    
    class MockStageAVariant(MockStageAFilePathToBuffer): # Same name, different class
        """A variant of MockStageA for testing re-registration."""
        # No need to override properties if only class identity matters for test

    with caplog.at_level(logging.WARNING):
        register_stage(MockStageAVariant)
    
    assert MockStageAFilePathToBuffer.name in STAGE_REGISTRY
    assert STAGE_REGISTRY[MockStageAFilePathToBuffer.name] == MockStageAVariant # Overwritten
    
    expected_log_message_part = (
        f"Stage name '{MockStageAFilePathToBuffer.name}' from class '{MockStageAVariant.__name__}' "
        "is already registered. Overwriting"
    )
    assert any(expected_log_message_part in record.message for record in caplog.records)

def test_register_stage_type_error_not_subclass():
    """Test that register_stage raises TypeError if the class is not a subclass of AudioProcessingStage."""
    class NotAStage: #pylint: disable=too-few-public-methods
        """A dummy class that does not inherit from AudioProcessingStage."""
        name = "invalid_stage"

    with pytest.raises(TypeError, match="must inherit from AudioProcessingStage"):
        register_stage(NotAStage)

def test_register_stage_type_error_missing_name_property():
    """
    Test that register_stage raises TypeError if the stage class
    is missing the required 'name' property (e.g., due to incorrect implementation).
    """
    class StageWithoutName(AudioProcessingStage): #pylint: disable=abstract-method,too-few-public-methods
        """A stage class intentionally missing the 'name' property for testing."""
        # Abstract 'name' property is not implemented
        @property
        def description(self) -> str: return "No name"
        @property
        def input_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def output_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def default_params(self) -> dict: return {}
        def process(self, data, params, context=None): return data

    # Patch 'name' to simulate it being completely absent or raising AttributeError
    with patch.object(StageWithoutName, 'name', new_callable=MagicMock(side_effect=AttributeError("name not implemented"))):
        with pytest.raises(TypeError, match="must have a 'name' property"):
            register_stage(StageWithoutName)


# --- Tests for execute_stage_chain ---
@pytest.fixture
def registered_mock_stages():
    """
    Fixture to pre-register all mock stages (A, B, C) for use in
    tests that execute stage chains.
    """
    register_stage(MockStageAFilePathToBuffer)
    register_stage(MockStageBBufferToBuffer)
    register_stage(MockStageCBufferToFilePath)

def test_execute_stage_chain_success(registered_mock_stages):
    """
    Test successful execution of a valid chain of stages, verifying data flow,
    parameter merging, and context passing.
    """
    initial_file = "/path/to/input.wav"
    context_dict = {"project_id": 123, "user": "test_user"}
    
    chain_def = [
        {"stage_name": "mock_stage_a", "params": {"param_a": 100}},
        {"stage_name": "mock_stage_b"}, # Uses default params
        {"stage_name": "mock_stage_c", "params": {"output_filename": "final_output.wav"}}
    ]

    final_output = execute_stage_chain(
        initial_data=initial_file,
        initial_data_type=DATA_TYPE_FILE_PATH,
        chain_definition=chain_def,
        context=context_dict
    )

    assert final_output == "/tmp/mock_output/final_output.wav"

    # Check Stage A call details
    assert len(MockStageAFilePathToBuffer.call_log) == 1
    stage_a_call = MockStageAFilePathToBuffer.call_log[0]
    assert stage_a_call["data"] == initial_file
    assert stage_a_call["params"] == {"param_a": 100} # Overridden
    assert stage_a_call["context"] == context_dict

    # Check Stage B call details
    assert len(MockStageBBufferToBuffer.call_log) == 1
    stage_b_call = MockStageBBufferToBuffer.call_log[0]
    assert stage_b_call["data"] == [0.1, 0.2, 0.3] # Output from Stage A
    assert stage_b_call["params"] == {"param_b": "hello"} # Default from Stage B
    assert stage_b_call["context"] == context_dict

    # Check Stage C call details
    assert len(MockStageCBufferToFilePath.call_log) == 1
    stage_c_call = MockStageCBufferToFilePath.call_log[0]
    assert stage_c_call["data"] == [0.2, 0.4, 0.6] # Output from Stage B (doubled)
    assert stage_c_call["params"] == {"output_filename": "final_output.wav"} # Overridden
    assert stage_c_call["context"] == context_dict

def test_execute_stage_chain_type_mismatch(registered_mock_stages):
    """
    Test that execute_stage_chain raises TypeError if there's a data type
    mismatch between the output of one stage and the input of the next.
    """
    chain_def = [
        {"stage_name": "mock_stage_a"}, # Outputs AudioBufferMono
        {"stage_name": "mock_stage_c"}  # Normally expects AudioBufferMono
    ]
    # Intentionally modify MockStageC's expected input type for this test
    original_input_type_c = MockStageCBufferToFilePath._input_type
    MockStageCBufferToFilePath._input_type = DATA_TYPE_FILE_PATH 

    expected_error_msg = (
        "Type mismatch for stage 'mock_stage_c' (index 1). "
        "Stage expects input type 'file_path', but received 'audio_buffer_mono'"
    )
    with pytest.raises(TypeError, match=expected_error_msg):
        execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})
    
    MockStageCBufferToFilePath._input_type = original_input_type_c # Reset for other tests

def test_execute_stage_chain_initial_type_mismatch(registered_mock_stages):
    """
    Test `execute_stage_chain` for `TypeError` if `initial_data_type`
    mismatches the first stage's `input_type`.
    """
    chain_def = [{"stage_name": "mock_stage_a"}] # Expects FilePath
    expected_error_msg = (
        "Type mismatch for stage 'mock_stage_a' (index 0). "
        "Stage expects input type 'file_path', but received 'audio_buffer_mono'"
    )
    with pytest.raises(TypeError, match=expected_error_msg):
        execute_stage_chain([0.1, 0.2], DATA_TYPE_AUDIO_BUFFER_MONO, chain_def, {})

def test_execute_stage_chain_stage_not_found(registered_mock_stages): # Added fixture
    """
    Test `execute_stage_chain` for `ValueError` if a stage name in the
    chain definition is not found in `STAGE_REGISTRY`.
    """
    # registered_mock_stages fixture ensures STAGE_REGISTRY is somewhat populated,
    # making a "non_existent_stage" more clearly not part of it.
    chain_def = [{"stage_name": "non_existent_stage"}]
    expected_error_match = "Stage 'non_existent_stage' .* not found in STAGE_REGISTRY"
    with pytest.raises(ValueError, match=expected_error_match):
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_def, {})

def test_execute_stage_chain_empty_chain():
    """
    Test `execute_stage_chain` with an empty `chain_definition`.
    It should return the `initial_data` immediately without any processing.
    """
    initial_data = "my_initial_data"
    result = execute_stage_chain(initial_data, DATA_TYPE_FILE_PATH, [], {})
    assert result == initial_data, "Empty chain should return initial data."

def test_execute_stage_chain_stage_process_error(registered_mock_stages):
    """
    Test that `execute_stage_chain` correctly handles and propagates (by
    wrapping in `RuntimeError`) an exception raised during a stage's `process` method.
    """
    chain_def = [{"stage_name": "mock_stage_a"}]
    
    original_process_a = MockStageAFilePathToBuffer.process
    # Make Stage A's process method raise a specific error for testing
    MockStageAFilePathToBuffer.process = MagicMock(side_effect=RuntimeError("Processing error in A!"))
    
    expected_error_match = (
        "Processing failed in stage 'mock_stage_a'.*Original error: Processing error in A!"
    )
    with pytest.raises(Exception, match=expected_error_match): # Check for custom wrapped message
        execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})
    
    MockStageAFilePathToBuffer.process = original_process_a # Restore original method

def test_execute_stage_chain_missing_stage_name_in_def(registered_mock_stages): # Added fixture
    """
    Test `execute_stage_chain` for `ValueError` if an item in `chain_definition`
    is missing the required 'stage_name' key.
    """
    # registered_mock_stages not strictly needed but harmless for consistency
    chain_def = [{"params": {}}] # 'stage_name' is missing here
    expected_error_msg = "Missing 'stage_name' in chain definition at index 0"
    with pytest.raises(ValueError, match=expected_error_msg):
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_def, {})

def test_execute_stage_chain_default_param_usage(registered_mock_stages):
    """
    Test that `execute_stage_chain` correctly uses a stage's default parameters
    when none are provided in the chain definition, and correctly merges
    provided parameters with defaults.
    """
    chain_def = [
        {"stage_name": "mock_stage_a"}, # Should use default param_a: 1
        {"stage_name": "mock_stage_b", "params": {"param_b": "overridden"}} # Override
    ]
    execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})

    assert MockStageAFilePathToBuffer.call_log[0]["params"] == {"param_a": 1}
    assert MockStageBBufferToBuffer.call_log[0]["params"] == {"param_b": "overridden"}

def test_execute_stage_chain_no_context_provided(registered_mock_stages):
    """
    Test that `execute_stage_chain` provides an empty dictionary as context
    to stages if the `context` argument is `None`.
    """
    chain_def = [{"stage_name": "mock_stage_a"}]
    execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, context=None)
    assert MockStageAFilePathToBuffer.call_log[0]["context"] == {}, (
        "Context should default to an empty dict if None is passed."
    )
