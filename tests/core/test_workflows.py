"""
Unit tests for the workflows.py module.
"""

import pytest
import logging
from typing import Any, Dict, List, Type
from unittest.mock import patch, MagicMock

from src.core.processing_stages import DATA_TYPE_FILE_PATH  # For example workflow
from src.core.workflows import (
    WORKFLOW_REGISTRY,
    register_workflow,
    BaseWorkflow,
    ExampleSlicingWorkflow,  # Import the concrete example workflow
    _camel_to_snake,
)

# Assuming stage_runner is where execute_stage_chain is defined.
# We will mock execute_stage_chain for these tests.

logger = logging.getLogger(__name__)


# --- Fixture to manage WORKFLOW_REGISTRY ---
@pytest.fixture(autouse=True)
def clear_workflow_registry():
    """Clears the WORKFLOW_REGISTRY before each test."""
    original_registry = WORKFLOW_REGISTRY.copy()
    WORKFLOW_REGISTRY.clear()
    yield
    WORKFLOW_REGISTRY.clear()
    WORKFLOW_REGISTRY.update(original_registry)


# --- Mock BaseWorkflow Implementation (Optional, if needed for specific tests) ---
class MockWorkflowAlpha(BaseWorkflow):
    _name = "Mock Workflow Alpha"
    _description = "Alpha workflow for testing."
    _stages_definition = [{"stage_name": "alpha_stage1", "params": {}}]

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def stages_definition(self) -> List[Dict[str, Any]]:
        return self._stages_definition


class MockWorkflowBeta(
    BaseWorkflow
):  # Different class, same derived registry key if not careful
    _name = "Mock Workflow Beta"  # Different name property
    _description = "Beta workflow for testing."
    _stages_definition = [{"stage_name": "beta_stage1", "params": {}}]

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def stages_definition(self) -> List[Dict[str, Any]]:
        return self._stages_definition


# --- Tests for _camel_to_snake utility ---
def test_camel_to_snake():
    assert _camel_to_snake("SimpleWorkflow") == "simple_workflow"
    assert _camel_to_snake(
        "WorkflowWithABBREVIATION") == "workflow_with_abbreviation"
    assert _camel_to_snake("Already_Snake_Case") == "already_snake_case"
    assert _camel_to_snake(
        "ExampleSlicingWorkflow") == "example_slicing_workflow"


# --- Tests for register_workflow ---
def test_register_workflow_success():
    # ExampleSlicingWorkflow is registered at import time of its module.
    # For this test, let's use a fresh mock one.
    register_workflow(MockWorkflowAlpha)
    expected_key = _camel_to_snake(
        MockWorkflowAlpha.__name__)  # "mock_workflow_alpha"
    assert expected_key in WORKFLOW_REGISTRY
    assert WORKFLOW_REGISTRY[expected_key] == MockWorkflowAlpha


def test_register_workflow_reregistration(caplog):
    expected_key_alpha = _camel_to_snake(MockWorkflowAlpha.__name__)
    register_workflow(MockWorkflowAlpha)  # Initial registration

    # Create a new class with the same derived registry key
    class MockWorkflowAlphaVariant(
        BaseWorkflow
    ):  # Same class name structure as MockWorkflowAlpha
        @property
        def name(self) -> str:
            return "Variant Alpha"

        @property
        def description(self) -> str:
            return "A variant."

        @property
        def stages_definition(self) -> List[Dict[str, Any]]:
            return []

        # To ensure a different class name if MockWorkflowAlpha is also a class name
        # for the key, this is a bit contrived. The key is from __name__.
        # If MockWorkflowAlpha.__name__ == MockWorkflowAlphaVariant.__name__, this test makes sense.
        # Let's assume we are testing overwriting the *same key*.
        # The key is derived from class name. So, we'd need a class with the same name,
        # which is not possible in the same scope.
        # The warning is based on the *key*, not the class itself.
        # So, if two different classes map to the same key.
        # The current _camel_to_snake will produce unique keys for unique class names.
        # The warning is more relevant if we manually provide names or have complex name clashes.
        # For this test, let's simulate a class that would generate the same key if that were possible,
        # or simply re-registering a different class with a key that happens to collide.
        # The current implementation uses _camel_to_snake(class.__name__), so direct collision
        # of keys from *different* class names is unlikely unless _camel_to_snake produces non-unique output.
        # The warning is more about "if a key is already there, it's
        # overwritten".

    # To test the overwrite warning properly, let's use a different class
    # that we force to have the same registry key by manipulating its __name__ or how the key is derived.
    # Since we can't easily change __name__, let's assume _camel_to_snake could hypothetically collide,
    # or more simply, just register another class that would naturally get the same key as a previous one
    # (which is hard with the current key derivation).
    # So, let's test the warning by registering a different class that *would* overwrite if the key was the same.
    # The most straightforward way is to register the same class again, or a new class that would overwrite.
    # The current register_workflow uses _camel_to_snake(class_name).
    # So, to test overwrite, we'd need a different class that produces the same snake_case name.
    # This is unlikely with typical class names.
    # The warning is more for:
    # 1. If `register_workflow` took a `name` argument.
    # 2. If `_camel_to_snake` was lossy (e.g. `MyFlow` and `MYFlow` -> `my_flow`).
    # For now, we'll test re-registering a *different class* under the *same key*
    # by directly manipulating the registry for setup, then calling
    # register_workflow.

    # Ensure it's there
    WORKFLOW_REGISTRY[expected_key_alpha] = MockWorkflowAlpha

    # Now register a new class that would also map to expected_key_alpha if it was named MockWorkflowAlpha
    # For the test, we'll use MockWorkflowBeta but imagine its key collides.
    # To force collision for test:
    with patch("src.core.workflows._camel_to_snake", return_value=expected_key_alpha):
        with caplog.at_level(logging.WARNING):
            register_workflow(
                MockWorkflowBeta
            )  # This will use expected_key_alpha due to patch

    assert expected_key_alpha in WORKFLOW_REGISTRY
    # Overwritten
    assert WORKFLOW_REGISTRY[expected_key_alpha] == MockWorkflowBeta

    assert any(
        f"Workflow registry key '{expected_key_alpha}' (derived from class '{
            MockWorkflowBeta.__name__}') is already registered. Overwriting" in record.message for record in caplog.records)


def test_register_workflow_type_error_not_subclass():
    class NotAWorkflow:
        pass  # Missing name, etc.

    with pytest.raises(TypeError, match="must inherit from BaseWorkflow"):
        register_workflow(NotAWorkflow)


# --- Tests for BaseWorkflow and ExampleSlicingWorkflow ---


@patch(
    "src.core.workflows.execute_stage_chain"
)  # Mock the function called by workflow.run()
def test_base_workflow_run_method(mock_execute_stage_chain):
    # Use the concrete ExampleSlicingWorkflow for testing the BaseWorkflow.run() logic
    # as BaseWorkflow itself is abstract.

    # ExampleSlicingWorkflow is registered at module import. Let's get it.
    workflow_key = _camel_to_snake(ExampleSlicingWorkflow.__name__)
    # Ensure ExampleSlicingWorkflow is in the registry for this test
    if workflow_key not in WORKFLOW_REGISTRY:
        register_workflow(
            ExampleSlicingWorkflow
        )  # Register if cleared by fixture setup

    WorkflowClass = WORKFLOW_REGISTRY.get(workflow_key)
    assert (
        WorkflowClass is not None
    ), f"{workflow_key} not found after attempting registration."

    workflow_instance = WorkflowClass()

    initial_data_val = "/path/to/some/file.wav"
    # ExampleSlicingWorkflow's first stage (noise_reduction) expects
    # audio_buffer_mono
    initial_data_type_val = DATA_TYPE_FILE_PATH
    # but the SlicingStage (if it's the real one) expects file_path.
    # This highlights the importance of workflow stage compatibility.
    # For testing `run` itself, we care that it *calls* execute_stage_chain
    # correctly.

    # The ExampleSlicingWorkflow as defined:
    # 1. noise_reduction (input: audio_buffer_mono)
    # 2. slicing (input: file_path)
    # This chain has a type mismatch.
    # For this test, let's assume initial_data_type matches the *first* stage of *a* valid workflow.
    # Or, we can test that `run` correctly passes what it's given.
    # The `initial_data_type` for `run` should match the input type of the *first* stage in the workflow's chain.
    # Let's assume a hypothetical first stage that takes DATA_TYPE_FILE_PATH.
    # The ExampleSlicingWorkflow's first stage is 'noise_reduction', which expects 'audio_buffer_mono'.
    # The second stage 'slicing' expects 'file_path'. This workflow is flawed
    # as defined.

    # Let's use MockWorkflowAlpha for a controlled test of `run`
    register_workflow(MockWorkflowAlpha)
    mock_workflow_alpha_instance = MockWorkflowAlpha()

    # MockWorkflowAlpha's first stage (alpha_stage1) - let's assume it expects DATA_TYPE_FILE_PATH
    # We need to define what its (mocked) stages expect/return for execute_stage_chain to be "successful".
    # For this test, we only care that execute_stage_chain is called with the
    # right things from workflow.run().

    mock_context_val = {"project_id": 1, "db_session": MagicMock()}
    mock_execute_stage_chain.return_value = "final_processed_data"  # Mocked return

    result = mock_workflow_alpha_instance.run(
        initial_data=initial_data_val,
        initial_data_type=DATA_TYPE_FILE_PATH,
        # Assume this matches first stage of MockWorkflowAlpha
        context=mock_context_val,
    )

    assert result == "final_processed_data"

    expected_context_for_chain = mock_context_val.copy()
    expected_context_for_chain["current_workflow_name"] = (
        mock_workflow_alpha_instance.name
    )

    mock_execute_stage_chain.assert_called_once_with(
        initial_data=initial_data_val,
        initial_data_type=DATA_TYPE_FILE_PATH,  # Passed through
        chain_definition=mock_workflow_alpha_instance.stages_definition,
        context=expected_context_for_chain,
    )


def test_example_slicing_workflow_definition():
    # ExampleSlicingWorkflow is registered at module import.
    workflow_key = _camel_to_snake(ExampleSlicingWorkflow.__name__)
    if workflow_key not in WORKFLOW_REGISTRY:
        register_workflow(ExampleSlicingWorkflow)

    WorkflowClass = WORKFLOW_REGISTRY.get(workflow_key)
    assert WorkflowClass is not None

    instance = WorkflowClass()
    assert instance.name == "example_slicing_workflow"
    assert "noise reduction" in instance.description.lower()
    assert "slicing" in instance.description.lower()

    stages_def = instance.stages_definition
    assert isinstance(stages_def, list)
    assert len(stages_def) == 2

    assert stages_def[0]["stage_name"] == "noise_reduction"
    assert "amount" in stages_def[0]["params"]

    assert stages_def[1]["stage_name"] == "slicing"
    assert stages_def[1]["params"] == {}  # Expects default params for slicing

    # Note: As identified, this specific workflow (ExampleSlicingWorkflow)
    # has a type incompatibility between its defined stages if using the
    # actual NoiseReductionStage (outputs buffer) and SlicingStage (inputs file path).
    # This test only checks the definition, not its executability without
    # mocks.
