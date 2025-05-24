# pylint: disable=too-many-lines
"""
Unit tests for the `src.core.workflows` module.

This module tests the registration of workflows, the `_camel_to_snake` utility,
and the execution logic of `BaseWorkflow.run()` using mock workflows and by
inspecting the definition of `ExampleSlicingWorkflow`.
"""
import logging
from typing import Any, Dict, List, Type # Used in type hints
from unittest.mock import patch, MagicMock

import pytest

from src.core.processing_stages import DATA_TYPE_FILE_PATH # Used in test_base_workflow_run_method
from src.core.workflows import (
    WORKFLOW_REGISTRY,
    BaseWorkflow, # Import BaseWorkflow for subclassing mock
    ExampleSlicingWorkflow,
    _camel_to_snake, # For testing this utility
    register_workflow,
    BaseWorkflow,
    ExampleSlicingWorkflow, # Import the concrete example workflow
    _camel_to_snake
)
# Assuming stage_runner is where execute_stage_chain is defined.
# We will mock execute_stage_chain for these tests as stage execution
# is tested in test_stage_runner.py.

logger = logging.getLogger(__name__)

# --- Fixture to manage WORKFLOW_REGISTRY ---
@pytest.fixture(autouse=True)
def clear_workflow_registry():
    """
    Clears the WORKFLOW_REGISTRY before each test and restores it afterward.
    This ensures a clean state for tests involving workflow registration.
    """
    original_registry = WORKFLOW_REGISTRY.copy()
    WORKFLOW_REGISTRY.clear()
    yield
    WORKFLOW_REGISTRY.clear()
    WORKFLOW_REGISTRY.update(original_registry)

# --- Mock BaseWorkflow Implementations ---
# pylint: disable=too-few-public-methods (These are minimal mocks for testing)
class MockWorkflowA(BaseWorkflow): # Renamed for PascalCase consistency
    """A mock workflow implementation for testing registration and basic properties."""
    # Using class attributes for properties as they are fixed for the mock
    name_val = "Mock Workflow A" # Renamed _name
    description_val = "Workflow A for detailed testing." # Renamed _description
    stages_definition_val = [{"stage_name": "mock_stage_a", "params": {}}] # Renamed

    @property
    def name(self) -> str: return self.name_val
    @property
    def description(self) -> str: return self.description_val
    @property
    def stages_definition(self) -> List[Dict[str, Any]]: return self.stages_definition_val

class MockWorkflowB(BaseWorkflow): # Renamed for PascalCase consistency
    """Another mock workflow, distinct from MockWorkflowA."""
    name_val = "Mock Workflow B"
    description_val = "Workflow B for testing reregistration scenarios."
    stages_definition_val = [{"stage_name": "mock_stage_b", "params": {"val": 1}}]

    @property
    def name(self) -> str: return self.name_val
    @property
    def description(self) -> str: return self.description_val
    @property
    def stages_definition(self) -> List[Dict[str, Any]]: return self.stages_definition_val
# pylint: enable=too-few-public-methods


# --- Tests for _camel_to_snake utility ---
def test_camel_to_snake_conversion():
    """Test the _camel_to_snake utility function with various inputs."""
    assert _camel_to_snake("SimpleWorkflow") == "simple_workflow"
    assert _camel_to_snake("WorkflowWithABBREVIATION") == "workflow_with_abbreviation"
    assert _camel_to_snake("Already_Snake_Case") == "already_snake_case"
    assert _camel_to_snake("ExampleSlicingWorkflow") == "example_slicing_workflow"
    assert _camel_to_snake("MyAPITest") == "my_api_test" # Test with trailing uppercase


# --- Tests for register_workflow ---
def test_register_workflow_success():
    """Test successful registration of a valid workflow class."""
    register_workflow(MockWorkflowA)
    expected_key = _camel_to_snake(MockWorkflowA.__name__) # "mock_workflow_a"
    assert expected_key in WORKFLOW_REGISTRY
    assert WORKFLOW_REGISTRY[expected_key] == MockWorkflowA

def test_register_workflow_reregistration_warning(caplog):
    """
    Test that re-registering a workflow with a key derived from a class name
    that collides with an existing key overwrites the previous registration
    and logs a warning.
    """
    # Key for MockWorkflowA is "mock_workflow_a"
    expected_key_a = _camel_to_snake(MockWorkflowA.__name__)
    register_workflow(MockWorkflowA) # Initial registration
    
    # To simulate a key collision with a *different* class, we patch _camel_to_snake
    # to return the same key for MockWorkflowB as it did for MockWorkflowA.
    with patch('src.core.workflows._camel_to_snake', return_value=expected_key_a):
        with caplog.at_level(logging.WARNING):
            register_workflow(MockWorkflowB) # This will use expected_key_a due to patch

    assert expected_key_a in WORKFLOW_REGISTRY
    assert WORKFLOW_REGISTRY[expected_key_a] == MockWorkflowB, "Registry should be updated."
    
    # Check for the specific warning log message
    found_warning = False
    for record in caplog.records:
        if record.levelname == "WARNING" and \
           f"Workflow registry key '{expected_key_a}'" in record.message and \
           f"(derived from class '{MockWorkflowB.__name__}')" in record.message and \
           "is already registered. Overwriting" in record.message:
            found_warning = True
            break
    assert found_warning, "Warning for re-registering workflow was not logged."


def test_register_workflow_type_error_if_not_subclass_of_base_workflow(): # Already has docstring
    """
    Test that `register_workflow` raises a TypeError if the provided class
    does not inherit from `BaseWorkflow`.
    """
    class NotAWorkflow: # pylint: disable=too-few-public-methods
        """A dummy class not inheriting from BaseWorkflow."""
        pass

    with pytest.raises(TypeError, match="must inherit from BaseWorkflow"):
        register_workflow(NotAWorkflow)


# --- Tests for BaseWorkflow and ExampleSlicingWorkflow ---

@patch('src.core.workflows.execute_stage_chain')
def test_base_workflow_run_method_calls_execute_stage_chain_correctly(
    mock_execute_stage_chain
):
    """
    Test the `BaseWorkflow.run()` method to ensure it correctly calls
    `execute_stage_chain` with the appropriate arguments, including
    the workflow's stages definition and an updated context.
    Uses MockWorkflowA for a controlled test.
    """
    register_workflow(MockWorkflowA) # Ensure it's in the registry
    workflow_instance = MockWorkflowA()
    
    initial_data_val = "/path/to/input_audio.wav"
    initial_data_type_val = DATA_TYPE_FILE_PATH
    mock_context_val = {"project_id": 123, "user_id": "test_user_workflow_run"}
    
    # Set a mock return value for the execute_stage_chain call
    expected_final_data = "mocked_final_output_from_chain"
    mock_execute_stage_chain.return_value = expected_final_data

    result = workflow_instance.run(
        initial_data=initial_data_val,
        initial_data_type=initial_data_type_val,
        context=mock_context_val
    )

    assert result == expected_final_data, "Workflow run should return result from execute_stage_chain."
    
    # Verify context passed to execute_stage_chain includes current_workflow_name
    expected_context_for_chain = mock_context_val.copy()
    expected_context_for_chain['current_workflow_name'] = workflow_instance.name

    mock_execute_stage_chain.assert_called_once_with(
        initial_data=initial_data_val,
        initial_data_type=initial_data_type_val,
        chain_definition=workflow_instance.stages_definition,
        context=expected_context_for_chain
    )

def test_example_slicing_workflow_definition_is_correct():
    """
    Test the definition of `ExampleSlicingWorkflow` to ensure its name,
    description, and stages_definition are as expected.
    This test does not execute the workflow, only inspects its properties.
    """
    # ExampleSlicingWorkflow should be registered when its module (src.core.workflows) is imported.
    # The clear_workflow_registry fixture might clear it, so re-register if needed for this test.
    workflow_key = _camel_to_snake(ExampleSlicingWorkflow.__name__)
    if workflow_key not in WORKFLOW_REGISTRY:
        register_workflow(ExampleSlicingWorkflow) # Ensure it's available

    WorkflowClass = WORKFLOW_REGISTRY.get(workflow_key)
    assert WorkflowClass is not None, f"'{workflow_key}' not found in WORKFLOW_REGISTRY."
    
    instance = WorkflowClass()
    assert instance.name == "example_slicing_workflow"
    # Docstring line length for assertions
    assert "noise reduction" in instance.description.lower(), \
        "Description should mention noise reduction."
    assert "slicing" in instance.description.lower(), \
        "Description should mention slicing."
    
    stages_def = instance.stages_definition
    assert isinstance(stages_def, list), "Stages definition should be a list."
    assert len(stages_def) == 2, "ExampleSlicingWorkflow should have two stages."
    
    assert stages_def[0]["stage_name"] == "noise_reduction", \
        "First stage should be 'noise_reduction'."
    assert "amount" in stages_def[0]["params"], \
        "'amount' param missing in noise_reduction stage."
    
    assert stages_def[1]["stage_name"] == "slicing", \
        "Second stage should be 'slicing'."
    assert stages_def[1]["params"] == {}, \
        "Slicing stage should use default params (empty dict)."

    # The comment about type incompatibility in ExampleSlicingWorkflow is a
    # design note, not something this definition test can directly assert
    # without knowing specific stage details.
