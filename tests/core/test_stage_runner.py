"""
Unit tests for the stage_runner.py module.
"""

import pytest
import logging
from typing import Any, Dict, Type, List, Generator, Optional # Added List, Generator, Optional
from unittest.mock import MagicMock, patch
from _pytest.logging import LogCaptureFixture # For caplog fixture

from src.core.processing_stages import (
    AudioProcessingStage,
    DATA_TYPE_FILE_PATH,
    DATA_TYPE_AUDIO_BUFFER_MONO,
    DATA_TYPE_LIST_OF_SAMPLE_DATA,  # Though not used by mocks, good to have for context
)
from src.core.stage_runner import STAGE_REGISTRY, register_stage, execute_stage_chain

# Configure basic logging for tests (optional, but can be helpful)
# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Mock AudioProcessingStage Implementations ---


class MockStageA_FilePathToBuffer(AudioProcessingStage):
    """Mock stage: FilePath -> AudioBufferMono. Logs calls."""

    name = "mock_stage_a"  # Changed to class attribute
    _description: str = "Converts file path to mono audio buffer (mocked)."
    _input_type: str = DATA_TYPE_FILE_PATH
    _output_type: str = DATA_TYPE_AUDIO_BUFFER_MONO
    _default_params: Dict[str, Any] = {"param_a": 1}

    call_log: List[Dict[str, Any]] = []

    @property
    def name(self) -> str: # name property added back as it's part of the ABC
        return self.__class__.name # Access class attribute

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
    ) -> List[float]:  # Simulating buffer as list[float]
        """Mock process method."""
        logger.info(
            f"[{self.name}] CALLED with data: {data}, params: {params}, context: {context}"
        )
        self.call_log.append({"data": data, "params": params, "context": context or {}})
        if not isinstance(data, str):
            raise TypeError(f"{self.name} expected str, got {type(data)}")
        return [0.1, 0.2, 0.3]


class MockStageB_BufferToBuffer(AudioProcessingStage):
    """Mock stage: AudioBufferMono -> AudioBufferMono. Logs calls."""

    name: str = "mock_stage_b"
    _description: str = "Processes a mono audio buffer (mocked)."
    _input_type: str = DATA_TYPE_AUDIO_BUFFER_MONO
    _output_type: str = DATA_TYPE_AUDIO_BUFFER_MONO
    _default_params: Dict[str, Any] = {"param_b": "hello"}
    call_log: List[Dict[str, Any]] = []

    @property
    def name(self) -> str: # name property added back
        return self.__class__.name

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
        logger.info(
            f"[{self.name}] CALLED with data: {data}, params: {params}, context: {context}"
        )
        self.call_log.append({"data": data, "params": params, "context": context or {}})
        if not isinstance(data, list):
            raise TypeError(f"{self.name} expected list, got {type(data)}")
        return [d * 2 for d in data]


class MockStageC_BufferToFilePath(AudioProcessingStage):
    """Mock stage: AudioBufferMono -> FilePath. Logs calls."""

    name: str = "mock_stage_c"
    _description: str = "Saves a mono audio buffer to a file path (mocked)."
    _input_type: str = DATA_TYPE_AUDIO_BUFFER_MONO
    _output_type: str = DATA_TYPE_FILE_PATH
    _default_params: Dict[str, Any] = {"output_filename": "output.wav"}
    call_log: List[Dict[str, Any]] = []

    @property
    def name(self) -> str: # name property added back
        return self.__class__.name

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
        logger.info(
            f"[{self.name}] CALLED with data: {data}, params: {params}, context: {context}"
        )
        self.call_log.append({"data": data, "params": params, "context": context or {}})
        if not isinstance(data, list):
            raise TypeError(f"{self.name} expected list, got {type(data)}")
        return f"/tmp/mock_output/{params.get('output_filename', 'default_out.wav')}"


# --- Fixture to manage STAGE_REGISTRY ---
@pytest.fixture(autouse=True)
def clear_stage_registry_and_logs() -> Generator[None, None, None]:
    """Clears the STAGE_REGISTRY and mock stage call logs before each test.

    Yields:
        None.
    """
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
    assert MockStageA_FilePathToBuffer.name in STAGE_REGISTRY
    assert STAGE_REGISTRY[MockStageA_FilePathToBuffer.name] == MockStageA_FilePathToBuffer


def test_register_stage_reregistration(caplog: LogCaptureFixture) -> None:
    """Test that re-registering a stage with the same name overwrites and logs a warning.

    Args:
        caplog: Pytest fixture to capture log output.
    """
    register_stage(MockStageA_FilePathToBuffer)

    class MockStageA_Variant(MockStageA_FilePathToBuffer):
        pass

    with caplog.at_level(logging.WARNING):
        register_stage(MockStageA_Variant)

    assert MockStageA_FilePathToBuffer.name in STAGE_REGISTRY
    assert STAGE_REGISTRY[MockStageA_FilePathToBuffer.name] == MockStageA_Variant

    assert any(
        f"Stage name '{MockStageA_FilePathToBuffer.name}' from class '{MockStageA_Variant.__name__}' "
        "is already registered. Overwriting" in record.message
        for record in caplog.records
    )


def test_register_stage_type_error_not_subclass() -> None:
    """Test that registering a class not inheriting from AudioProcessingStage raises TypeError."""
    class NotAStage:
        name: str = "invalid_stage" # type: ignore

    with pytest.raises(TypeError, match="must inherit from AudioProcessingStage"):
        register_stage(NotAStage) # type: ignore


def test_register_stage_type_error_missing_name_property() -> None:
    """Test registering a stage missing the 'name' property (if it weren't abstract).
    Note: This test is more conceptual as 'name' is an abstract property,
    so a class without it wouldn't properly subclass AudioProcessingStage.
    The actual error might be TypeError due to inability to instantiate an ABC
    if a direct instantiation were attempted, or AttributeError if 'name' was
    expected as a simple class attribute by register_stage.
    The current register_stage accesses `stage_class.name` which works for class attributes.
    If `name` is an `@property`, it requires an instance, which `register_stage` doesn't create.
    Our mock stages use class attributes for `name` for simplicity with `register_stage`.
    """
    class StageWithoutName(AudioProcessingStage):
        # name: str = "test" # This would make it valid.
        # To make this test meaningful for a missing 'name', we'd need to mock how 'name' is accessed
        # or change 'register_stage' to instantiate. For now, this tests a malformed class.
        _description: str = "No name"
        _input_type: str = DATA_TYPE_FILE_PATH
        _output_type: str = DATA_TYPE_FILE_PATH
        _default_params: Dict[str, Any] = {}

        @property
        def name(self) -> str: # Adding name property to make it a valid subclass
             return "stage_without_name_property_value_but_actually_has_it"

        @property
        def description(self) -> str: return self._description
        @property
        def input_type(self) -> str: return self._input_type
        @property
        def output_type(self) -> str: return self._output_type
        @property
        def default_params(self) -> Dict[str, Any]: return self._default_params
        def process(self, data: Any, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any: return data

    # This test might need adjustment based on how `register_stage` handles `name`
    # If `register_stage` expects `name` as a class attribute, and it's missing,
    # it would be an AttributeError.
    # Our mock stages provide `name` as a class attribute, so this test path for
    # a "missing" name is less direct.
    # The test for `NotAStage` covers non-AudioProcessingStage types.
    # A class truly missing the 'name' abstract property wouldn't type-check.
    # We assume `register_stage` expects a class attribute `name`.
    del StageWithoutName.name # Make it actually missing for the test
    with pytest.raises(TypeError, match="must have a 'name' property"): # Adjusted to TypeError as per current register_stage
        register_stage(StageWithoutName)


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

    final_output: Any = execute_stage_chain(
        initial_data=initial_file,
        initial_data_type=DATA_TYPE_FILE_PATH,
        chain_definition=chain_def,
        context=context_dict,
    )

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
    chain_def: List[Dict[str, Any]] = [
        {"stage_name": "mock_stage_a"},
        {"stage_name": "mock_stage_c"},
    ]
    original_input_type = MockStageC_BufferToFilePath._input_type
    MockStageC_BufferToFilePath._input_type = DATA_TYPE_FILE_PATH # Force mismatch

    with pytest.raises(
        TypeError,
        match="Stage expects input type 'file_path', but received 'audio_buffer_mono'",
    ):
        execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})

    MockStageC_BufferToFilePath._input_type = original_input_type # Reset


def test_execute_stage_chain_initial_type_mismatch(registered_mock_stages: None) -> None:
    """Test that a type mismatch with initial data raises a TypeError."""
    chain_def: List[Dict[str, Any]] = [{"stage_name": "mock_stage_a"}]  # Expects FilePath
    with pytest.raises(
        TypeError,
        match="Stage expects input type 'file_path', but received 'audio_buffer_mono'",
    ):
        execute_stage_chain([0.1, 0.2], DATA_TYPE_AUDIO_BUFFER_MONO, chain_def, {})


def test_execute_stage_chain_stage_not_found() -> None:
    """Test execution fails if a stage in the chain is not registered."""
    chain_def: List[Dict[str, Any]] = [{"stage_name": "non_existent_stage"}]
    with pytest.raises(
        ValueError, match="Stage 'non_existent_stage' .* not found in STAGE_REGISTRY"
    ):
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
    MockStageA_FilePathToBuffer.process = MagicMock( # type: ignore[method-assign]
        side_effect=RuntimeError("Processing failed in A")
    )

    with pytest.raises(
        Exception,
        match="Processing failed in stage 'mock_stage_a'.*Original error: Processing failed in A",
    ):
        execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})

    MockStageA_FilePathToBuffer.process = original_process # type: ignore[method-assign]


def test_execute_stage_chain_missing_stage_name_in_def() -> None:
    """Test that a missing 'stage_name' in chain definition raises ValueError."""
    chain_def: List[Dict[str, Any]] = [{"params": {}}]
    with pytest.raises(
        ValueError, match="Missing 'stage_name' in chain definition at index 0"
    ):
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_def, {})


def test_execute_stage_chain_default_param_usage(registered_mock_stages: None) -> None:
    """Test that default parameters are used when not overridden in chain definition."""
    chain_def: List[Dict[str, Any]] = [
        {"stage_name": "mock_stage_a"},
        {"stage_name": "mock_stage_b"},
    ]
    execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def, {})

    assert MockStageA_FilePathToBuffer.call_log[0]["params"] == {"param_a": 1}
    assert MockStageB_BufferToBuffer.call_log[0]["params"] == {"param_b": "hello"}


def test_execute_stage_chain_no_context_provided(registered_mock_stages: None) -> None:
    """Test that an empty context dictionary is used if None is provided."""
    chain_def: List[Dict[str, Any]] = [{"stage_name": "mock_stage_a"}]
    execute_stage_chain("/input.wav", DATA_TYPE_FILE_PATH, chain_def) # context=None
    assert MockStageA_FilePathToBuffer.call_log[0]["context"] == {}
