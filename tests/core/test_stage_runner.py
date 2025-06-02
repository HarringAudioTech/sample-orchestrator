import pytest
import logging
from typing import Optional # Added

from src.core.stage_runner import STAGE_REGISTRY, register_stage, execute_stage_chain
from src.core.processing_stages import AudioProcessingStage, DATA_TYPE_FILE_PATH, DATA_TYPE_AUDIO_BUFFER_MONO

# New dummy data types for testing
DATA_TYPE_DUMMY = "DATA_TYPE_DUMMY" # Existing one
DATA_TYPE_DUMMY_TEXT = "dummy_text"
DATA_TYPE_DUMMY_OUTPUT = "dummy_output"

@pytest.fixture
def clear_stage_registry():
    """Clears the STAGE_REGISTRY before each test."""
    STAGE_REGISTRY.clear()
    yield
    STAGE_REGISTRY.clear()

# --- Mock Stage Implementations (from previous step) ---
class MockSuccessStage(AudioProcessingStage):
    """A simple stage that records it was called and returns modified data."""
    @property
    def name(self) -> str:
        return "mock_success_stage"
    @property
    def description(self) -> str:
        return "A mock stage that simulates successful processing and captures inputs."
    @property
    def input_type(self) -> str:
        return DATA_TYPE_FILE_PATH
    @property
    def output_type(self) -> str:
        return DATA_TYPE_FILE_PATH
    @property
    def default_params(self) -> dict:
        return {"default_param_key": "default_param_value"}

    def __init__(self, config=None, **kwargs):
        super().__init__(config)
        self.called = False
        self.received_config = config
        self.received_kwargs = kwargs
        self.received_params_in_process = None
        self.received_context_in_process = None

    def process(self, data, params: dict, context: Optional[dict] = None): # Removed temp_dir_path, updated signature
        self.called = True
        self.received_params_in_process = params
        self.received_context_in_process = context
        return f"processed_{data}"

class MockErrorStage(AudioProcessingStage):
    """A stage that raises an exception during its process method."""
    @property
    def name(self) -> str:
        return "mock_error_stage"
    @property
    def description(self) -> str:
        return "A mock stage that always raises an error during process."
    @property
    def input_type(self) -> str:
        return DATA_TYPE_FILE_PATH
    @property
    def output_type(self) -> str:
        return DATA_TYPE_FILE_PATH
    @property
    def default_params(self) -> dict:
        return {}

    def __init__(self, config=None, **kwargs):
        super().__init__(config)
        self.received_kwargs = kwargs # To store any extra kwargs passed during instantiation

    def process(self, data, params: dict, context: Optional[dict] = None): # Removed temp_dir_path
        raise ValueError("Mock error in processing stage")

class MockTypeAtoBStage(AudioProcessingStage):
    """Stage with input_type DATA_TYPE_FILE_PATH and output_type DATA_TYPE_AUDIO_BUFFER_MONO."""
    @property
    def name(self) -> str:
        return "mock_type_a_to_b_stage"
    @property
    def description(self) -> str:
        return "Converts type A (file path) to type B (audio buffer)."
    @property
    def input_type(self) -> str:
        return DATA_TYPE_FILE_PATH
    @property
    def output_type(self) -> str:
        return DATA_TYPE_AUDIO_BUFFER_MONO
    @property
    def default_params(self) -> dict:
        return {}

    def __init__(self, config=None, **kwargs):
        super().__init__(config)
        self.called = False
        self.received_kwargs = kwargs

    def process(self, data, params: dict, context: Optional[dict] = None): # Removed temp_dir_path
        self.called = True
        # Simulate converting file path to audio buffer
        return {"sample_rate": 16000, "audio_data": [0.1, 0.2, 0.3]}

class MockTypeBtoCStage(AudioProcessingStage):
    """Stage with input_type DATA_TYPE_AUDIO_BUFFER_MONO and output_type DATA_TYPE_DUMMY_TEXT."""
    @property
    def name(self) -> str:
        return "mock_type_b_to_c_stage"
    @property
    def description(self) -> str:
        return "Converts type B (audio buffer) to type C (dummy text)."
    @property
    def input_type(self) -> str:
        return DATA_TYPE_AUDIO_BUFFER_MONO
    @property
    def output_type(self) -> str:
        return DATA_TYPE_DUMMY_TEXT
    @property
    def default_params(self) -> dict:
        return {}

    def __init__(self, config=None, **kwargs):
        super().__init__(config)
        self.called = False
        self.received_kwargs = kwargs

    def process(self, data, params: dict, context: Optional[dict] = None):  # Removed temp_dir_path
        self.called = True
        # Simulate converting audio buffer to text
        return "transcribed text from audio"

class MockTypeCtoDStage(AudioProcessingStage):
    """Stage with input_type DATA_TYPE_DUMMY_TEXT and output_type DATA_TYPE_DUMMY."""
    @property
    def name(self) -> str:
        return "mock_type_c_to_d_stage"
    @property
    def description(self) -> str:
        return "Converts type C (dummy text) to type D (dummy)."
    @property
    def input_type(self) -> str:
        return DATA_TYPE_DUMMY_TEXT
    @property
    def output_type(self) -> str:
        return DATA_TYPE_DUMMY
    @property
    def default_params(self) -> dict:
        return {}

    def __init__(self, config=None, **kwargs):
        super().__init__(config)
        self.called = False
        self.received_kwargs = kwargs

    def process(self, data, params: dict, context: Optional[dict] = None):  # Removed temp_dir_path
        self.called = True
        # Simulate processing text to a dummy data type
        return {"dummy_data": f"processed_{data}"}

class MockStageWithInitError(AudioProcessingStage):
    @property
    def name(self) -> str:
        return "mock_init_error_stage"
    @property
    def description(self) -> str:
        return "A mock stage that is designed to fail during initialization."
    @property
    def input_type(self) -> str:
        return DATA_TYPE_FILE_PATH
    @property
    def output_type(self) -> str:
        return DATA_TYPE_FILE_PATH
    @property
    def default_params(self) -> dict:
        return {}

    def __init__(self, config=None, **kwargs):
        super().__init__(config) # Call super for basic setup before failing
        raise RuntimeError("Init failed for MockStageWithInitError")

    def process(self, data, params: dict, context: Optional[dict] = None):  # Removed temp_dir_path
        # This method is required by the ABC but won't be reached if __init__ fails.
        return data
