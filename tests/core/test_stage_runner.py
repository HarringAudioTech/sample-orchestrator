import pytest
import logging

from src.core.stage_runner import STAGE_REGISTRY, register_stage, execute_stage_chain
from src.core.processing_stages import AudioProcessingStage, DATA_TYPE_FILE_PATH, DATA_TYPE_AUDIO_BUFFER_MONO, DATA_TYPE_TEXT

# New dummy data type for testing
DATA_TYPE_DUMMY = "DATA_TYPE_DUMMY"

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
    def name(self):
        return "mock_success_stage"

    def __init__(self, config=None, **kwargs): # Added **kwargs
        super().__init__(config)
        self.called = False
        self.input_type = DATA_TYPE_FILE_PATH
        self.output_type = DATA_TYPE_FILE_PATH
        self.received_config = config
        self.received_kwargs = kwargs
        self.received_params_in_process = None
        self.received_context_in_process = None

    default_params = {"default_param_key": "default_param_value"}

    def process(self, data, temp_dir_path: str, params: dict = None, context: dict = None): # Modified signature
        self.called = True
        self.received_params_in_process = params
        self.received_context_in_process = context
        return f"processed_{data}"

class MockErrorStage(AudioProcessingStage):
    """A stage that raises an exception during its process method."""
    @property
    def name(self):
        return "mock_error_stage"

    def __init__(self, config=None, **kwargs): # Added **kwargs
        super().__init__(config)
        self.input_type = DATA_TYPE_FILE_PATH
        self.output_type = DATA_TYPE_FILE_PATH
        self.received_kwargs = kwargs

    def process(self, data, temp_dir_path: str, params: dict = None, context: dict = None): # Modified signature
        raise ValueError("Mock error in processing stage")

class MockTypeAtoBStage(AudioProcessingStage):
    """Stage with input_type DATA_TYPE_FILE_PATH and output_type DATA_TYPE_AUDIO_BUFFER_MONO."""
    @property
    def name(self):
        return "mock_type_a_to_b_stage"

    def __init__(self, config=None, **kwargs): # Added **kwargs
        super().__init__(config)
        self.input_type = DATA_TYPE_FILE_PATH
        self.output_type = DATA_TYPE_AUDIO_BUFFER_MONO
        self.called = False
        self.received_kwargs = kwargs

    def process(self, data, temp_dir_path: str, params: dict = None, context: dict = None): # Modified signature
        self.called = True
        # Simulate converting file path to audio buffer
        return {"sample_rate": 16000, "audio_data": [0.1, 0.2, 0.3]}

class MockTypeBtoCStage(AudioProcessingStage):
    """Stage with input_type DATA_TYPE_AUDIO_BUFFER_MONO and output_type DATA_TYPE_TEXT."""
    @property
    def name(self):
        return "mock_type_b_to_c_stage"

    def __init__(self, config=None, **kwargs): # Added **kwargs
        super().__init__(config)
        self.input_type = DATA_TYPE_AUDIO_BUFFER_MONO
        self.output_type = DATA_TYPE_TEXT
        self.called = False
        self.received_kwargs = kwargs

    def process(self, data, temp_dir_path: str, params: dict = None, context: dict = None): # Modified signature
        self.called = True
        # Simulate converting audio buffer to text
        return "transcribed text from audio"

class MockTypeCtoDStage(AudioProcessingStage):
    """Stage with input_type DATA_TYPE_TEXT and output_type DATA_TYPE_DUMMY."""
    @property
    def name(self):
        return "mock_type_c_to_d_stage"

    def __init__(self, config=None, **kwargs): # Added **kwargs
        super().__init__(config)
        self.input_type = DATA_TYPE_TEXT
        self.output_type = DATA_TYPE_DUMMY
        self.called = False # Added for consistency, though not strictly needed by current tests
        self.received_kwargs = kwargs

    def process(self, data, temp_dir_path: str, params: dict = None, context: dict = None): # Modified signature
        self.called = True
        # Simulate processing text to a dummy data type
        return {"dummy_data": f"processed_{data}"}

class MockStageWithInitError(AudioProcessingStage):
    @property
    def name(self):
        return "mock_init_error_stage"

    def __init__(self, config=None, **kwargs):
        raise RuntimeError("Init failed for MockStageWithInitError")

    @property
    def input_type(self): return DATA_TYPE_FILE_PATH # Must be implemented
    @property
    def output_type(self): return DATA_TYPE_FILE_PATH # Must be implemented
    def process(self, data, temp_dir_path: str, params: dict = None, context: dict = None): # Must be implemented
        return data


# --- Tests for register_stage ---

def test_register_stage_success_and_logging(clear_stage_registry, caplog):
    """Test successful registration of a valid stage and INFO logging."""
    stage_class = MockSuccessStage
    with caplog.at_level(logging.INFO):
        register_stage(stage_class)

    assert stage_class.name in STAGE_REGISTRY
    assert STAGE_REGISTRY[stage_class.name] == stage_class

    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    assert log_record.levelname == "INFO"
    assert f"Successfully registered stage '{stage_class.name}' from class {stage_class.__name__}" in log_record.message
    assert log_record.name == "src.core.stage_runner"

def test_register_stage_overwrite_warning(clear_stage_registry, caplog): # Already uses caplog
    """Test that overwriting an existing stage logs a WARNING."""
    initial_stage_class = MockSuccessStage
    register_stage(initial_stage_class) # Initial registration

    class AnotherStageWithName(AudioProcessingStage):
        @property
        def name(self):
            return initial_stage_class.name # Same name as MockSuccessStage

        @property
        def input_type(self): return DATA_TYPE_TEXT
        @property
        def output_type(self): return DATA_TYPE_TEXT
        def process(self, data, temp_dir_path: str, params: dict = None, context: dict = None): return data


    # Clear previous logs if any from the initial registration if caplog is not reset per test part
    caplog.clear()

    with caplog.at_level(logging.WARNING): # Ensure this context manager is capturing for the overwrite
        register_stage(AnotherStageWithName)

    assert STAGE_REGISTRY[initial_stage_class.name] == AnotherStageWithName # Check it's overwritten

    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    assert log_record.levelname == "WARNING"
    assert f"Stage name '{initial_stage_class.name}' from class {AnotherStageWithName.__name__} is already registered (currently {initial_stage_class.__name__}). Overwriting." in log_record.message
    assert log_record.name == "src.core.stage_runner"

def test_register_stage_invalid_type(clear_stage_registry): # No specific logging for this before error
    """Test that registering a class not inheriting from AudioProcessingStage raises TypeError."""
    class NotAudioStage:
        name = "not_audio_stage"

    with pytest.raises(TypeError, match="Stage class must inherit from AudioProcessingStage"):
        register_stage(NotAudioStage)

class StageMissingNameProperty(AudioProcessingStage):
    @property
    def name(self):
        return None

    @property
    def input_type(self): return DATA_TYPE_TEXT
    @property
    def output_type(self): return DATA_TYPE_TEXT
    def process(self, data, temp_dir_path: str, params: dict = None, context: dict = None): return data


class StageEmptyNameValue(AudioProcessingStage):
    @property
    def name(self):
        return ""

    @property
    def input_type(self): return DATA_TYPE_FILE_PATH
    @property
    def output_type(self): return DATA_TYPE_FILE_PATH
    def process(self, data, temp_dir_path: str, params: dict = None, context: dict = None): return data

def test_register_stage_name_is_none(clear_stage_registry):
    with pytest.raises(AttributeError, match="Stage class must have a valid 'name' property \\(non-empty string\\)\\."):
        register_stage(StageMissingNameProperty)

def test_register_stage_empty_name_value(clear_stage_registry):
    with pytest.raises(AttributeError, match="Stage class must have a valid 'name' property \\(non-empty string\\)\\."):
        register_stage(StageEmptyNameValue)


# --- Helper class for inspecting instance behavior in execute_stage_chain ---
class InspectableMockSuccessStage(MockSuccessStage):
    last_instance_called_flag = False
    last_instance_received_params = None
    last_instance_received_context = None

    @property
    def name(self):
        return "inspectable_mock_success_stage"

    def process(self, data, temp_dir_path: str, params: dict = None, context: dict = None):
        super().process(data, temp_dir_path, params, context)
        InspectableMockSuccessStage.last_instance_called_flag = self.called
        InspectableMockSuccessStage.last_instance_received_params = self.received_params_in_process
        InspectableMockSuccessStage.last_instance_received_context = self.received_context_in_process
        return f"processed_inspectable_{data}"

    @classmethod
    def reset_class_inspection_vars(cls):
        cls.last_instance_called_flag = False
        cls.last_instance_received_params = None
        cls.last_instance_received_context = None

# --- Tests for execute_stage_chain basic execution ---

def test_execute_empty_chain(clear_stage_registry):
    initial_data = "initial_data"
    initial_data_type = DATA_TYPE_FILE_PATH
    chain_definition = []
    result, final_data_type = execute_stage_chain(initial_data, initial_data_type, chain_definition, {}, "dummy_temp_dir")
    assert result == initial_data
    assert final_data_type == initial_data_type

def test_execute_single_stage_chain_success(clear_stage_registry):
    register_stage(InspectableMockSuccessStage)
    InspectableMockSuccessStage.reset_class_inspection_vars()
    initial_data = "test_file.txt"
    initial_data_type = DATA_TYPE_FILE_PATH
    chain_definition = [{"stage_name": InspectableMockSuccessStage.name}]
    result, final_data_type = execute_stage_chain(initial_data, initial_data_type, chain_definition, {}, "dummy_temp_dir")
    assert result == f"processed_inspectable_{initial_data}"
    assert final_data_type == InspectableMockSuccessStage.output_type
    assert InspectableMockSuccessStage.last_instance_called_flag is True
    InspectableMockSuccessStage.reset_class_inspection_vars()

def test_execute_multiple_stages_chain_success(clear_stage_registry):
    register_stage(MockTypeAtoBStage)
    register_stage(MockTypeBtoCStage)
    initial_data = "input.wav"
    initial_data_type = DATA_TYPE_FILE_PATH
    chain_definition = [
        {"stage_name": MockTypeAtoBStage.name},
        {"stage_name": MockTypeBtoCStage.name}
    ]
    result, final_data_type = execute_stage_chain(initial_data, initial_data_type, chain_definition, {}, "dummy_temp_dir")
    assert result == "transcribed text from audio"
    assert final_data_type == MockTypeBtoCStage.output_type

def test_execute_chain_with_context(clear_stage_registry):
    register_stage(InspectableMockSuccessStage)
    InspectableMockSuccessStage.reset_class_inspection_vars()
    initial_data = "context_test.txt"
    initial_data_type = DATA_TYPE_FILE_PATH
    context_to_pass = {"project_id": 123, "user_id": "test_user"}
    chain_definition = [{"stage_name": InspectableMockSuccessStage.name}]
    execute_stage_chain(initial_data, initial_data_type, chain_definition, context_to_pass, "dummy_temp_dir")
    assert InspectableMockSuccessStage.last_instance_received_context is not None
    assert InspectableMockSuccessStage.last_instance_received_context["project_id"] == 123
    assert InspectableMockSuccessStage.last_instance_received_context["user_id"] == "test_user"
    InspectableMockSuccessStage.reset_class_inspection_vars()

def test_execute_chain_parameter_merging(clear_stage_registry):
    register_stage(InspectableMockSuccessStage)
    InspectableMockSuccessStage.reset_class_inspection_vars()
    initial_data = "params_test.txt"
    initial_data_type = DATA_TYPE_FILE_PATH
    user_params_override = {
        "default_param_key": "overridden_value",
        "user_specific_param": "user_value"
    }
    chain_def_override = [{
        "stage_name": InspectableMockSuccessStage.name,
        "params": user_params_override
    }]
    execute_stage_chain(initial_data, initial_data_type, chain_def_override, {}, "dummy_temp_dir")
    expected_merged_params_override = InspectableMockSuccessStage.default_params.copy()
    expected_merged_params_override.update(user_params_override)
    assert InspectableMockSuccessStage.last_instance_received_params is not None
    assert InspectableMockSuccessStage.last_instance_received_params == expected_merged_params_override
    InspectableMockSuccessStage.reset_class_inspection_vars()
    chain_def_default = [{"stage_name": InspectableMockSuccessStage.name}]
    execute_stage_chain(initial_data, initial_data_type, chain_def_default, {}, "dummy_temp_dir")
    assert InspectableMockSuccessStage.last_instance_received_params is not None
    assert InspectableMockSuccessStage.last_instance_received_params == InspectableMockSuccessStage.default_params
    InspectableMockSuccessStage.reset_class_inspection_vars()

# --- Tests for execute_stage_chain error handling and edge cases ---

def test_execute_chain_unregistered_stage(clear_stage_registry):
    """Test chain execution with an unregistered stage name."""
    chain_definition = [{"stage_name": "UnregisteredStageName"}]
    with pytest.raises(ValueError, match="Stage 'UnregisteredStageName' not found in STAGE_REGISTRY."):
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_definition, {}, "dummy_temp_dir")

def test_execute_chain_missing_stage_name_key(clear_stage_registry):
    """Test chain execution with a malformed stage definition (missing 'stage_name')."""
    chain_definition = [{"params": {"some_param": "value"}}] # Missing 'stage_name'
    with pytest.raises(ValueError, match="Missing 'stage_name' in stage definition:"):
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_definition, {}, "dummy_temp_dir")

def test_execute_chain_initial_type_mismatch(clear_stage_registry):
    """Test chain execution where initial data type mismatches first stage's input type."""
    register_stage(MockTypeAtoBStage) # Expects DATA_TYPE_FILE_PATH
    chain_definition = [{"stage_name": MockTypeAtoBStage.name}]
    initial_data_type = DATA_TYPE_TEXT # Mismatch
    with pytest.raises(TypeError, match=f"Type mismatch: Stage {MockTypeAtoBStage.name} expected {MockTypeAtoBStage.input_type}, but got {initial_data_type}"):
        execute_stage_chain("data", initial_data_type, chain_definition, {}, "dummy_temp_dir")

def test_execute_chain_intermediate_type_mismatch(clear_stage_registry):
    """Test chain execution where output type of one stage mismatches input type of the next."""
    register_stage(MockTypeAtoBStage) # Outputs: DATA_TYPE_AUDIO_BUFFER_MONO
    register_stage(MockTypeCtoDStage) # Expects: DATA_TYPE_TEXT

    chain_definition = [
        {"stage_name": MockTypeAtoBStage.name},
        {"stage_name": MockTypeCtoDStage.name}
    ]
    expected_error_msg = (f"Type mismatch: Stage {MockTypeCtoDStage.name} expected {MockTypeCtoDStage.input_type}, "
                          f"but got {MockTypeAtoBStage.output_type} from previous stage {MockTypeAtoBStage.name}")

    with pytest.raises(TypeError, match=expected_error_msg):
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_definition, {}, "dummy_temp_dir")

def test_execute_chain_stage_instantiation_error(clear_stage_registry):
    """Test chain execution where a stage fails to instantiate."""
    register_stage(MockStageWithInitError)
    chain_definition = [{"stage_name": MockStageWithInitError.name}]

    with pytest.raises(RuntimeError, match=f"Could not instantiate stage {MockStageWithInitError.name}") as excinfo:
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_definition, {}, "dummy_temp_dir")
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    assert "Init failed for MockStageWithInitError" in str(excinfo.value.__cause__)


def test_execute_chain_stage_processing_error(clear_stage_registry):
    """Test chain execution where a stage's process method raises an error."""
    register_stage(MockErrorStage) # process() raises ValueError
    chain_definition = [{"stage_name": MockErrorStage.name}]

    with pytest.raises(Exception, match=f"Processing failed in stage {MockErrorStage.name}") as excinfo:
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_definition, {}, "dummy_temp_dir")

    assert isinstance(excinfo.value.__cause__, ValueError)
    assert "Mock error in processing stage" in str(excinfo.value.__cause__)


# --- Tests for execute_stage_chain Logging ---

def test_execute_stage_chain_logging_basic_flow(clear_stage_registry, caplog):
    """Test INFO logging for basic successful stage chain execution."""
    register_stage(MockSuccessStage)
    chain_definition = [{"stage_name": MockSuccessStage.name, "description": "Test Description"}]
    initial_data = "start_data"
    initial_data_type = DATA_TYPE_FILE_PATH

    with caplog.at_level(logging.INFO):
        execute_stage_chain(initial_data, initial_data_type, chain_definition, {}, "dummy_temp_dir")

    assert len(caplog.records) >= 4 # Start chain, Executing stage, Stage completed, Chain completed

    # Check specific log messages (order and exact count might vary if other INFO logs exist)
    # For src.core.stage_runner logger only
    runner_logs = [r for r in caplog.records if r.name == "src.core.stage_runner"]

    assert runner_logs[0].levelname == "INFO"
    assert "Starting stage chain execution with 1 stages." in runner_logs[0].message

    assert runner_logs[1].levelname == "INFO"
    assert f"Executing stage 1/1: '{MockSuccessStage.name}' (Test Description)" in runner_logs[1].message

    assert runner_logs[2].levelname == "INFO"
    assert f"Stage '{MockSuccessStage.name}' (index 0) completed. Output type: '{MockSuccessStage.output_type}'" in runner_logs[2].message

    assert runner_logs[3].levelname == "INFO"
    assert "Stage chain execution completed successfully." in runner_logs[3].message

    # Test empty chain logging
    caplog.clear()
    with caplog.at_level(logging.INFO):
        execute_stage_chain(initial_data, initial_data_type, [], {}, "dummy_temp_dir")

    assert len(caplog.records) == 1
    assert caplog.records[0].name == "src.core.stage_runner"
    assert caplog.records[0].levelname == "INFO"
    assert "Stage chain definition is empty. Returning initial data." in caplog.records[0].message


def test_execute_stage_chain_logging_parameter_merging_debug(clear_stage_registry, caplog):
    """Test DEBUG logging for parameter merging."""
    register_stage(MockSuccessStage) # Has default_params
    user_params = {"user_key": "user_val", "default_param_key": "user_override"}
    chain_definition = [{
        "stage_name": MockSuccessStage.name,
        "params": user_params
    }]

    # Temporarily set logger level for this test
    logger = logging.getLogger("src.core.stage_runner")
    original_level = logger.level
    logger.setLevel(logging.DEBUG)

    with caplog.at_level(logging.DEBUG): # caplog needs to be at DEBUG too
        execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_definition, {}, "dummy_temp_dir")

    logger.setLevel(original_level) # Restore original level

    # Expected merged params: default updated with user
    expected_merged = MockSuccessStage.default_params.copy()
    expected_merged.update(user_params)

    found_debug_log = False
    for record in caplog.records:
        if record.name == "src.core.stage_runner" and record.levelname == "DEBUG":
            if f"Stage '{MockSuccessStage.name}' (index 0) - Default params: {MockSuccessStage.default_params}, User params: {user_params}, Merged params: {expected_merged}" in record.message:
                found_debug_log = True
                break
    assert found_debug_log, "DEBUG log for parameter merging not found or incorrect."


def test_execute_stage_chain_logging_errors(clear_stage_registry, caplog):
    """Test ERROR logging for various failure scenarios in chain execution."""

    # 1. Type Mismatch (Initial)
    register_stage(MockTypeAtoBStage) # Expects DATA_TYPE_FILE_PATH
    chain_def_type_mismatch = [{"stage_name": MockTypeAtoBStage.name}]
    initial_data_type_mismatch = DATA_TYPE_TEXT

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(TypeError): # We expect it to fail
             execute_stage_chain("data", initial_data_type_mismatch, chain_def_type_mismatch, {}, "dummy_temp_dir")

    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    assert log_record.name == "src.core.stage_runner"
    assert log_record.levelname == "ERROR"
    assert f"Type mismatch for stage {MockTypeAtoBStage.name} (index 0): Expected {MockTypeAtoBStage.input_type}, got {initial_data_type_mismatch}" in log_record.message

    # 2. Stage Instantiation Error
    register_stage(MockStageWithInitError)
    chain_def_init_error = [{"stage_name": MockStageWithInitError.name}]

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError):
            execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_def_init_error, {}, "dummy_temp_dir")

    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    assert log_record.name == "src.core.stage_runner"
    assert log_record.levelname == "ERROR"
    assert f"Error instantiating stage {MockStageWithInitError.name} (index 0)" in log_record.message
    assert "Init failed for MockStageWithInitError" in log_record.message # Original error in message

    # 3. Stage Processing Error
    register_stage(MockErrorStage)
    chain_def_proc_error = [{"stage_name": MockErrorStage.name}]

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(Exception): # General exception as it's wrapped
            execute_stage_chain("data", DATA_TYPE_FILE_PATH, chain_def_proc_error, {}, "dummy_temp_dir")

    assert len(caplog.records) == 1
    log_record = caplog.records[0]
    assert log_record.name == "src.core.stage_runner"
    assert log_record.levelname == "ERROR"
    assert f"Error during processing of stage {MockErrorStage.name} (index 0)" in log_record.message
    assert "Mock error in processing stage" in log_record.message # Original error in message
