import pytest
import logging
from typing import Optional

from src.core.stage_runner import STAGE_REGISTRY, register_stage, execute_stage_chain
from src.core.processing_stages import (
    AudioProcessingStage,
    DATA_TYPE_FILE_PATH,
    DATA_TYPE_AUDIO_BUFFER_MONO,
)

# New dummy data types for testing
DATA_TYPE_DUMMY = "DATA_TYPE_DUMMY"
DATA_TYPE_DUMMY_TEXT = "dummy_text"
DATA_TYPE_DUMMY_OUTPUT = "dummy_output"


@pytest.fixture
def clear_stage_registry():
    """Clears the STAGE_REGISTRY before each test."""
    STAGE_REGISTRY.clear()
    yield
    STAGE_REGISTRY.clear()


# --- Mock Stage Implementations ---
class MockSuccessStage(AudioProcessingStage):
    @property
    def name(self) -> str:
        return "mock_success_stage"

    @property
    def description(self) -> str:
        return "A mock stage that simulates successful processing."

    @property
    def input_type(self) -> str:
        return DATA_TYPE_FILE_PATH

    @property
    def output_type(self) -> str:
        return DATA_TYPE_FILE_PATH

    def process(self, data, params: dict, context: Optional[dict] = None):
        return f"processed_{data}"


class MockTypeAtoBStage(AudioProcessingStage):
    @property
    def name(self) -> str:
        return "mock_type_a_to_b_stage"

    @property
    def description(self) -> str:
        return "Converts type A to type B."

    @property
    def input_type(self) -> str:
        return DATA_TYPE_FILE_PATH

    @property
    def output_type(self) -> str:
        return DATA_TYPE_AUDIO_BUFFER_MONO

    def process(self, data, params: dict, context: Optional[dict] = None):
        return {"audio_data": [0.1, 0.2]}


# --- Tests ---

def test_register_stage(clear_stage_registry):
    """Test that a stage can be registered."""
    register_stage(MockSuccessStage)
    assert "mock_success_stage" in STAGE_REGISTRY
    assert STAGE_REGISTRY["mock_success_stage"] == MockSuccessStage


def test_execute_stage_chain_success(clear_stage_registry):
    """Test successful execution of a stage chain."""
    register_stage(MockSuccessStage)
    
    chain = [
        {"stage_name": "mock_success_stage", "params": {}}
    ]
    
    result = execute_stage_chain(
        initial_data="test_file.wav",
        initial_data_type=DATA_TYPE_FILE_PATH,
        chain_definition=chain
    )
    
    assert result["final_data"] == "processed_test_file.wav"
    assert result["final_type"] == DATA_TYPE_FILE_PATH
    assert len(result["stages"]) == 1
    assert result["stages"][0]["status"] == "success"


def test_execute_stage_chain_type_mismatch(clear_stage_registry):
    """Test that type mismatch raises an error."""
    register_stage(MockTypeAtoBStage)
    register_stage(MockSuccessStage) # Expects FILE_PATH
    
    chain = [
        {"stage_name": "mock_type_a_to_b_stage", "params": {}},
        {"stage_name": "mock_success_stage", "params": {}}
    ]
    
    with pytest.raises(TypeError):
        execute_stage_chain(
            initial_data="test.wav",
            initial_data_type=DATA_TYPE_FILE_PATH,
            chain_definition=chain
        )


def test_execute_stage_chain_unknown_stage(clear_stage_registry):
    """Test that unknown stage raises an error."""
    chain = [
        {"stage_name": "non_existent_stage", "params": {}}
    ]
    
    with pytest.raises(ValueError):
        execute_stage_chain(
            initial_data="test.wav",
            initial_data_type=DATA_TYPE_FILE_PATH,
            chain_definition=chain
        )
