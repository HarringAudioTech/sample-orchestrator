"""
Unit tests for the stage_runner.py module.
"""
import pytest
import logging
from typing import Any, Dict, Type
from unittest.mock import MagicMock, patch

from src.core.processing_stages import (
    AudioProcessingStage,
    DATA_TYPE_FILE_PATH,
    DATA_TYPE_AUDIO_BUFFER_MONO,
    DATA_TYPE_LIST_OF_SAMPLE_DATA # Though not used by mocks, good to have for context
)
from src.core.stage_runner import (
    STAGE_REGISTRY,
    register_stage,
    execute_stage_chain
)

# Configure basic logging for tests (optional, but can be helpful)
# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Mock AudioProcessingStage Implementations ---

class MockStageA_FilePathToBuffer(AudioProcessingStage):
    """Mock stage: FilePath -> AudioBufferMono. Logs calls."""
    _name = "mock_stage_a"
    _description = "Converts file path to mono audio buffer (mocked)."
    _input_type = DATA_TYPE_FILE_PATH
    _output_type = DATA_TYPE_AUDIO_BUFFER_MONO
    _default_params = {"param_a": 1}
    
    # Store calls for assertion
    call_log = []

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

    def process(self, data: str, params: dict, context: dict = None) -> list: # Simulating buffer as list
        logger.info(f"[{self.name}] CALLED with data: {data}, params: {params}, context: {context}")
        self.call_log.append({"data": data, "params": params, "context": context})
        if not isinstance(data, str): # Basic type check for test
            raise TypeError(f"{self.name} expected str, got {type(data)}")
        return [0.1, 0.2, 0.3] # Mock audio buffer

class MockStageB_BufferToBuffer(AudioProcessingStage):
    """Mock stage: AudioBufferMono -> AudioBufferMono. Logs calls."""
    _name = "mock_stage_b"
    _description = "Processes a mono audio buffer (mocked)."
    _input_type = DATA_TYPE_AUDIO_BUFFER_MONO
    _output_type = DATA_TYPE_AUDIO_BUFFER_MONO
    _default_params = {"param_b": "hello"}
    call_log = []

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
        logger.info(f"[{self.name}] CALLED with data: {data}, params: {params}, context: {context}")
        self.call_log.append({"data": data, "params": params, "context": context})
        if not isinstance(data, list): # Basic type check for test
             raise TypeError(f"{self.name} expected list, got {type(data)}")
        return [d * 2 for d in data] # Mock processing

class MockStageC_BufferToFilePath(AudioProcessingStage):
    """Mock stage: AudioBufferMono -> FilePath. Logs calls."""
    _name = "mock_stage_c"
    _description = "Saves a mono audio buffer to a file path (mocked)."
    _input_type = DATA_TYPE_AUDIO_BUFFER_MONO
    _output_type = DATA_TYPE_FILE_PATH
    _default_params = {"output_filename": "output.wav"}
    call_log = []

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
        logger.info(f"[{self.name}] CALLED with data: {data}, params: {params}, context: {context}")
        self.call_log.append({"data": data, "params": params, "context": context})
        if not isinstance(data, list):
             raise TypeError(f"{self.name} expected list, got {type(data)}")
        return f"/tmp/mock_output/{params.get('output_filename', 'default_out.wav')}"


# --- Fixture to manage STAGE_REGISTRY ---
@pytest.fixture(autouse=True) # Automatically use this fixture for all tests in this module
def clear_stage_registry_and_logs():
    """Clears the STAGE_REGISTRY and mock stage call logs before each test."""
    original_registry = STAGE_REGISTRY.copy()
    STAGE_REGISTRY.clear()
    
    # Clear call logs for each mock stage
    MockStageA_FilePathToBuffer.call_log.clear()
    MockStageB_BufferToBuffer.call_log.clear()
    MockStageC_BufferToFilePath.call_log.clear()
    
    yield # Test runs here
    
    # Restore original registry content after test (optional, usually clear is enough for isolation)
    STAGE_REGISTRY.clear()
    STAGE_REGISTRY.update(original_registry)


# --- Tests for register_stage ---
def test_register_stage_success():
    register_stage(MockStageA_FilePathToBuffer)
    assert MockStageA_FilePathToBuffer.name in STAGE_REGISTRY
    assert STAGE_REGISTRY[MockStageA_FilePathToBuffer.name] == MockStageA_FilePathToBuffer

def test_register_stage_reregistration(caplog):
    register_stage(MockStageA_FilePathToBuffer) # Initial registration
    
    class MockStageA_Variant(MockStageA_FilePathToBuffer): # Same name, different class
        pass

    with caplog.at_level(logging.WARNING):
        register_stage(MockStageA_Variant)
    
    assert MockStageA_FilePathToBuffer.name in STAGE_REGISTRY
    assert STAGE_REGISTRY[MockStageA_FilePathToBuffer.name] == MockStageA_Variant # Overwritten
    
    assert any(
        f"Stage name '{MockStageA_FilePathToBuffer.name}' from class '{MockStageA_Variant.__name__}' is already registered. Overwriting" in record.message
        for record in caplog.records
    )

def test_register_stage_type_error_not_subclass():
    class NotAStage:
        name = "invalid_stage"

    with pytest.raises(TypeError, match="must inherit from AudioProcessingStage"):
        register_stage(NotAStage)

def test_register_stage_type_error_missing_name_property():
    class StageWithoutName(AudioProcessingStage): # Missing abstract 'name' property
        @property
        def description(self) -> str: return "No name"
        @property
        def input_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def output_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def default_params(self) -> dict: return {}
        def process(self, data, params, context=None): return data

    # Python might raise TypeError at class definition if abstract methods aren't implemented.
    # If it allows definition, register_stage should catch it.
    # The test here is more about what register_stage does if 'name' somehow isn't available.
    # Abstract properties make this less likely if class definition itself is valid.
    # Let's assume for testing that 'name' might not be correctly implemented.
    with patch.object(StageWithoutName, 'name', new_callable=MagicMock(side_effect=AttributeError("name not implemented"))):
        with pytest.raises(TypeError, match="must have a 'name' property"):
            register_stage(StageWithoutName)


# --- Tests for execute_stage_chain ---
@pytest.fixture
def registered_mock_stages():
    """Fixture to register all mock stages for use in chain execution tests."""
    register_stage(MockStageA_FilePathToBuffer)
    register_stage(MockStageB_BufferToBuffer)
    register_stage(MockStageC_BufferToFilePath)

def test_execute_stage_chain_success(registered_mock_stages):
    initial_file = "/path/to/input.wav"
    context_dict = {"project_id": 123, "user": "test_user"}
    
    chain_def = [
        {"stage_name": "mock_stage_a", "params": {"param_a": 100}}, # Override default
        {"stage_name": "mock_stage_b"}, # Use default param_b
        {"stage_name": "mock_stage_c", "params": {"output_filename": "final_output.wav"}}
    ]

    final_output = execute_stage_chain(
        initial_data=initial_file,
        initial_data_type=DATA_TYPE_FILE_PATH,
        chain_definition=chain_def,
        context=context_dict
    )

    assert final_output == "/tmp/mock_output/final_output.wav"

    # Check Stage A call
    assert len(MockStageA_FilePathToBuffer.call_log) == 1
    stage_a_call = MockStageA_FilePathToBuffer.call_log[0]
    assert stage_a_call["data"] == initial_file
    assert stage_a_call["params"] == {"param_a": 100} # Merged
    assert stage_a_call["context"] == context_dict

    # Check Stage B call
    assert len(MockStageB_BufferToBuffer.call_log) == 1
    stage_b_call = MockStageB_BufferToBuffer.call_log[0]
    assert stage_b_call["data"] == [0.1, 0.2, 0.3] # Output from A
    assert stage_b_call["params"] == {"param_b": "hello"} # Default from B
    assert stage_b_call["context"] == context_dict

    # Check Stage C call
    assert len(MockStageC_BufferToFilePath.call_log) == 1
    stage_c_call = MockStageC_BufferToFilePath.call_log[0]
    assert stage_c_call["data"] == [0.2, 0.4, 0.6] # Output from B
    assert stage_c_call["params"] == {"output_filename": "final_output.wav"} # Merged
    assert stage_c_call["context"] == context_dict

def test_execute_stage_chain_type_mismatch(registered_mock_stages):
    chain_def = [
        {"stage_name": "mock_stage_a"}, # Outputs AudioBufferMono
        {"stage_name": "mock_stage_c"}  # Expects AudioBufferMono, this is fine
    ]
    # Now, let's make Stage C expect FilePath to force a mismatch
    MockStageC_BufferToFilePath._input_type = DATA_TYPE_FILE_PATH 
    # Need to re-register if input_type change matters to registry (it doesn't for current STAGE_REGISTRY)
    # but the instance created by execute_stage_chain will have this modified input_type.

    with pytest.raises(TypeError, match="Stage expects input type 'file_path', but received 'audio_buffer_mono'"):
        execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})
    
    # Reset for other tests
    MockStageC_BufferToFilePath._input_type = DATA_TYPE_AUDIO_BUFFER_MONO

def test_execute_stage_chain_initial_type_mismatch(registered_mock_stages):
    chain_def = [{"stage_name": "mock_stage_a"}] # Expects FilePath
    with pytest.raises(TypeError, match="Stage expects input type 'file_path', but received 'audio_buffer_mono'"):
        execute_stage_chain([0.1, 0.2], DATA_TYPE_AUDIO_BUFFER_MONO, chain_def, {})

def test_execute_stage_chain_stage_not_found():
    chain_def = [{"stage_name": "non_existent_stage"}]
    with pytest.raises(ValueError, match="Stage 'non_existent_stage' .* not found in STAGE_REGISTRY"):
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_def, {})

def test_execute_stage_chain_empty_chain():
    initial_data = "my_initial_data"
    result = execute_stage_chain(initial_data, DATA_TYPE_FILE_PATH, [], {})
    assert result == initial_data

def test_execute_stage_chain_stage_process_error(registered_mock_stages):
    chain_def = [{"stage_name": "mock_stage_a"}]
    
    # Make Stage A's process method raise an error
    original_process = MockStageA_FilePathToBuffer.process
    MockStageA_FilePathToBuffer.process = MagicMock(side_effect=RuntimeError("Processing failed in A"))
    
    with pytest.raises(Exception, match="Processing failed in stage 'mock_stage_a'.*Original error: Processing failed in A"):
        execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})
    
    # Restore original process method
    MockStageA_FilePathToBuffer.process = original_process

def test_execute_stage_chain_missing_stage_name_in_def():
    chain_def = [{"params": {}}] # Missing 'stage_name'
    with pytest.raises(ValueError, match="Missing 'stage_name' in chain definition at index 0"):
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_def, {})

def test_execute_stage_chain_default_param_usage(registered_mock_stages):
    # Stage B has default {"param_b": "hello"}
    # Stage A has default {"param_a": 1}
    chain_def = [
        {"stage_name": "mock_stage_a"}, # Uses default param_a
        {"stage_name": "mock_stage_b"}  # Uses default param_b
    ]
    execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})

    assert MockStageA_FilePathToBuffer.call_log[0]["params"] == {"param_a": 1}
    assert MockStageB_BufferToBuffer.call_log[0]["params"] == {"param_b": "hello"}

def test_execute_stage_chain_no_context_provided(registered_mock_stages):
    chain_def = [{"stage_name": "mock_stage_a"}]
    execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def) # context=None
    assert MockStageA_FilePathToBuffer.call_log[0]["context"] == {} # Should default to empty dict
```
