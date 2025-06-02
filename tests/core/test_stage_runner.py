"""Unit tests for the stage_runner.py module."""

import pytest
import logging
from typing import Any, Dict, Type, List, Generator, Optional
from unittest.mock import MagicMock # Removed patch as it's not used directly in this version
from _pytest.logging import LogCaptureFixture

from src.core.processing_stages import (
    AudioProcessingStage,
    DATA_TYPE_FILE_PATH,
    DATA_TYPE_AUDIO_BUFFER_MONO,
    DATA_TYPE_LIST_OF_SAMPLE_DATA,
)
from src.core.stage_runner import STAGE_REGISTRY, register_stage, execute_stage_chain

logger = logging.getLogger(__name__)

# --- Mock AudioProcessingStage Implementations ---

class MockStageA_FilePathToBuffer(AudioProcessingStage):
    """Mock stage: FilePath -> AudioBufferMono. Logs calls."""
    _description: str = "Converts file path to mono audio buffer (mocked)."
    _input_type: str = DATA_TYPE_FILE_PATH
    _output_type: str = DATA_TYPE_AUDIO_BUFFER_MONO
    _default_params: Dict[str, Any] = {"param_a": 1}
    call_log: List[Dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "mock_stage_a"
    @property
    def description(self) -> str:
        return self._description
    @property
    def input_type(self) -> str:
        return self._input_type
    @property
    def output_type(self) -> str:
        return self._output_type
    @property
    def default_params(self) -> Dict[str, Any]:
        return self._default_params.copy()
    def process(
        self, data: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> List[float]:
        """Mock process method."""
        logger.info(f"[{self.name}] CALLED with data: {data}, params: {params}, context: {context}")
        self.call_log.append({"data": data, "params": params, "context": context or {}})
        if not isinstance(data, str):
            raise TypeError(f"{self.name} expected str, got {type(data)}")
        return [0.1, 0.2, 0.3]

class MockStageB_BufferToBuffer(AudioProcessingStage):
    """Mock stage: AudioBufferMono -> AudioBufferMono. Logs calls."""
    _description: str = "Processes a mono audio buffer (mocked)."
    _input_type: str = DATA_TYPE_AUDIO_BUFFER_MONO
    _output_type: str = DATA_TYPE_AUDIO_BUFFER_MONO
    _default_params: Dict[str, Any] = {"param_b": "hello"}
    call_log: List[Dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "mock_stage_b"
    @property
    def description(self) -> str:
        return self._description
    @property
    def input_type(self) -> str:
        return self._input_type
    @property
    def output_type(self) -> str:
        return self._output_type
    @property
    def default_params(self) -> Dict[str, Any]:
        return self._default_params.copy()
    def process(self, data: List[float], params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> List[float]:
        """Mock process method."""
        logger.info(f"[{self.name}] CALLED with data: {data}, params: {params}, context: {context}")
        self.call_log.append({"data": data, "params": params, "context": context or {}})
        if not isinstance(data, list):
            raise TypeError(f"{self.name} expected list, got {type(data)}")
        return [d * 2 for d in data]

class MockStageC_BufferToFilePath(AudioProcessingStage):
    """Mock stage: AudioBufferMono -> FilePath. Logs calls."""
    _description: str = "Saves a mono audio buffer to a file path (mocked)."
    _input_type: str = DATA_TYPE_AUDIO_BUFFER_MONO
    _output_type: str = DATA_TYPE_FILE_PATH
    _default_params: Dict[str, Any] = {"output_filename": "output.wav"}
    call_log: List[Dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "mock_stage_c"
    @property
    def description(self) -> str:
        return self._description
    @property
    def input_type(self) -> str:
        return self._input_type
    @property
    def output_type(self) -> str:
        return self._output_type
    @property
    def default_params(self) -> Dict[str, Any]:
        return self._default_params.copy()
    def process(self, data: List[float], params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        """Mock process method."""
        logger.info(f"[{self.name}] CALLED with data: {data}, params: {params}, context: {context}")
        self.call_log.append({"data": data, "params": params, "context": context or {}})
        if not isinstance(data, list):
            raise TypeError(f"{self.name} expected list, got {type(data)}")
        return f"/tmp/mock_output/{params.get('output_filename', 'default_out.wav')}"

# --- Fixture to manage STAGE_REGISTRY ---
@pytest.fixture(autouse=True)
def clear_stage_registry_and_logs() -> Generator[None, None, None]:
    """Clears STAGE_REGISTRY and mock stage call logs before each test."""
    original_registry: Dict[str, Type[AudioProcessingStage]] = STAGE_REGISTRY.copy()
    STAGE_REGISTRY.clear()
    MockStageA_FilePathToBuffer.call_log.clear()
    MockStageB_BufferToBuffer.call_log.clear()
    MockStageC_BufferToFilePath.call_log.clear()
    yield
    STAGE_REGISTRY.clear()
    STAGE_REGISTRY.update(original_registry)

# --- Tests for register_stage ---
def test_register_stage_success() -> None:
    """Test successful registration of a stage."""
    register_stage(MockStageA_FilePathToBuffer)
    assert STAGE_REGISTRY.get("mock_stage_a") == MockStageA_FilePathToBuffer

def test_register_stage_reregistration(caplog: LogCaptureFixture) -> None:
    """Test re-registering a stage with the same name overwrites and logs a warning."""
    register_stage(MockStageA_FilePathToBuffer)
    class MockStageA_Variant(AudioProcessingStage): # New class with same name prop
        @property
        def name(self) -> str: return "mock_stage_a"
        @property
        def description(self) -> str: return "Variant A"
        @property
        def input_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def output_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def default_params(self) -> Dict[str, Any]: return {}
        def process(self, data: Any, params: Dict[str, Any], context: Optional[Dict[str, Any]]=None)->Any: return data

    with caplog.at_level(logging.WARNING):
        register_stage(MockStageA_Variant)
    assert STAGE_REGISTRY.get("mock_stage_a") == MockStageA_Variant
    assert any("already registered. Overwriting" in record.message for record in caplog.records)

def test_register_stage_type_error_not_subclass() -> None:
    """Test registering a class not inheriting from AudioProcessingStage raises TypeError."""
    class NotAStage:
        pass
    with pytest.raises(TypeError, match="must inherit from AudioProcessingStage"):
        register_stage(NotAStage) # type: ignore

def test_register_stage_errors_on_name_issues() -> None:
    """Test errors during registration if 'name' property is problematic."""
    class StageMissingName(AudioProcessingStage): # Does not implement 'name'
        @property
        def description(self) -> str: return "Desc"
        @property
        def input_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def output_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def default_params(self) -> Dict[str, Any]: return {}
        def process(self, data: Any, params: Dict[str, Any], context: Optional[Dict[str, Any]]=None)->Any: return data
    with pytest.raises(TypeError, match="Can't instantiate abstract class StageMissingName"):
        register_stage(StageMissingName)

    class StageEmptyName(AudioProcessingStage):
        @property
        def name(self) -> str: return "" # Empty name
        @property
        def description(self) -> str: return "Desc"
        @property
        def input_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def output_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def default_params(self) -> Dict[str, Any]: return {}
        def process(self, data: Any, params: Dict[str, Any], context: Optional[Dict[str, Any]]=None)->Any: return data
    with pytest.raises(TypeError, match="must have a valid 'name' property"):
        register_stage(StageEmptyName)

# --- Tests for execute_stage_chain ---
@pytest.fixture
def registered_mock_stages() -> None:
    """Fixture to register all mock stages for use in chain execution tests."""
    register_stage(MockStageA_FilePathToBuffer)
    register_stage(MockStageB_BufferToBuffer)
    register_stage(MockStageC_BufferToFilePath)

def test_execute_stage_chain_success(registered_mock_stages: None) -> None:
    """Test successful execution of a valid stage chain."""
    initial_file: str = "/path/to/input.wav"
    context_dict: Dict[str, Any] = {"project_id": 123, "user": "test_user"}
    chain_def: List[Dict[str, Any]] = [
        {"stage_name": "mock_stage_a", "params": {"param_a": 100}},
        {"stage_name": "mock_stage_b"},
        {"stage_name": "mock_stage_c", "params": {"output_filename": "final_output.wav"}},
    ]
    final_output: Any = execute_stage_chain(initial_file, DATA_TYPE_FILE_PATH, chain_def, context_dict)
    assert final_output == "/tmp/mock_output/final_output.wav"
    assert len(MockStageA_FilePathToBuffer.call_log) == 1
    stage_a_call: Dict[str, Any] = MockStageA_FilePathToBuffer.call_log[0]
    assert stage_a_call["data"] == initial_file
    assert stage_a_call["params"] == {"param_a": 100}
    assert stage_a_call["context"] == context_dict
    assert len(MockStageB_BufferToBuffer.call_log) == 1
    stage_b_call: Dict[str, Any] = MockStageB_BufferToBuffer.call_log[0]
    assert stage_b_call["data"] == [0.1, 0.2, 0.3]
    assert stage_b_call["params"] == {"param_b": "hello"}
    assert stage_b_call["context"] == context_dict
    assert len(MockStageC_BufferToFilePath.call_log) == 1
    stage_c_call: Dict[str, Any] = MockStageC_BufferToFilePath.call_log[0]
    assert stage_c_call["data"] == [0.2, 0.4, 0.6]
    assert stage_c_call["params"] == {"output_filename": "final_output.wav"}
    assert stage_c_call["context"] == context_dict

def test_execute_stage_chain_type_mismatch(registered_mock_stages: None) -> None:
    """Test that a type mismatch between stages raises a TypeError."""
    chain_def: List[Dict[str, Any]] = [{"stage_name": "mock_stage_a"}, {"stage_name": "mock_stage_c"}]
    original_input_type = MockStageC_BufferToFilePath._input_type
    MockStageC_BufferToFilePath._input_type = DATA_TYPE_FILE_PATH # Force mismatch
    with pytest.raises(TypeError, match="Stage expects input type 'file_path', but received 'audio_buffer_mono'"):
        execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})
    MockStageC_BufferToFilePath._input_type = original_input_type # Reset

def test_execute_stage_chain_initial_type_mismatch(registered_mock_stages: None) -> None:
    """Test that a type mismatch with initial data raises a TypeError."""
    chain_def: List[Dict[str, Any]] = [{"stage_name": "mock_stage_a"}]
    with pytest.raises(TypeError, match="Stage expects input type 'file_path', but received 'audio_buffer_mono'"):
        execute_stage_chain([0.1, 0.2], DATA_TYPE_AUDIO_BUFFER_MONO, chain_def, {})

def test_execute_stage_chain_stage_not_found() -> None:
    """Test execution fails if a stage in the chain is not registered."""
    chain_def: List[Dict[str, Any]] = [{"stage_name": "non_existent_stage"}]
    with pytest.raises(ValueError, match="Stage 'non_existent_stage' .* not found in STAGE_REGISTRY"):
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_def, {})

def test_execute_stage_chain_empty_chain() -> None:
    """Test that an empty chain definition returns the initial data."""
    initial_data: str = "my_initial_data"
    result: Any = execute_stage_chain(initial_data, DATA_TYPE_FILE_PATH, [], {})
    assert result == initial_data

def test_execute_stage_chain_stage_process_error(registered_mock_stages: None) -> None:
    """Test that an error during a stage's process method propagates correctly."""
    chain_def: List[Dict[str, Any]] = [{"stage_name": "mock_stage_a"}]
    original_process = MockStageA_FilePathToBuffer.process
    MockStageA_FilePathToBuffer.process = MagicMock(side_effect=RuntimeError("Processing failed in A")) # type: ignore
    with pytest.raises(Exception, match="Processing failed in stage 'mock_stage_a'.*Original error: Processing failed in A"):
        execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})
    MockStageA_FilePathToBuffer.process = original_process # type: ignore

def test_execute_stage_chain_missing_stage_name_in_def() -> None:
    """Test that a missing 'stage_name' in chain definition raises ValueError."""
    chain_def: List[Dict[str, Any]] = [{"params": {}}]
    with pytest.raises(ValueError, match="Missing 'stage_name' in chain definition at index 0"):
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_def, {})

def test_execute_stage_chain_default_param_usage(registered_mock_stages: None) -> None:
    """Test that default parameters are used when not overridden."""
    chain_def: List[Dict[str, Any]] = [{"stage_name": "mock_stage_a"}, {"stage_name": "mock_stage_b"}]
    execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})
    assert MockStageA_FilePathToBuffer.call_log[0]["params"] == {"param_a": 1}
    assert MockStageB_BufferToBuffer.call_log[0]["params"] == {"param_b": "hello"}

def test_execute_stage_chain_no_context_provided(registered_mock_stages: None) -> None:
    """Test that an empty context dictionary is used if None is provided."""
    chain_def: List[Dict[str, Any]] = [{"stage_name": "mock_stage_a"}]
    execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def) # context=None
    assert MockStageA_FilePathToBuffer.call_log[0]["context"] == {}
