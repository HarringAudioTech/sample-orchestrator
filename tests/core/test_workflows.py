"""Unit tests for the workflows.py module."""

import pytest
import logging
from typing import Any, Dict, List, Type, Generator, Optional
from unittest.mock import patch, MagicMock
from _pytest.logging import LogCaptureFixture # For caplog fixture

from src.core.processing_stages import DATA_TYPE_FILE_PATH
from src.core.workflows import (
    WORKFLOW_REGISTRY,
    register_workflow,
    BaseWorkflow,
    ExampleSlicingWorkflow,
    _camel_to_snake,
)

logger = logging.getLogger(__name__)


# --- Fixture to manage WORKFLOW_REGISTRY ---
@pytest.fixture(autouse=True)
def clear_workflow_registry() -> Generator[None, None, None]:
    """Clears the WORKFLOW_REGISTRY before each test.

    Yields:
        None.
    """
    original_registry: Dict[str, Type[BaseWorkflow]] = WORKFLOW_REGISTRY.copy()
    WORKFLOW_REGISTRY.clear()
    yield
    WORKFLOW_REGISTRY.clear()
    WORKFLOW_REGISTRY.update(original_registry)


# --- Mock BaseWorkflow Implementation ---
class MockWorkflowAlpha(BaseWorkflow):
    """A mock workflow implementation for testing alpha scenarios."""
    _name: str = "Mock Workflow Alpha"
    _description: str = "Alpha workflow for testing."
    _stages_definition: List[Dict[str, Any]] = [{"stage_name": "alpha_stage1", "params": {}}]

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def stages_definition(self) -> List[Dict[str, Any]]:
        return self._stages_definition


class MockWorkflowBeta(BaseWorkflow):
    """A mock workflow implementation for testing beta scenarios."""
    _name: str = "Mock Workflow Beta"
    _description: str = "Beta workflow for testing."
    _stages_definition: List[Dict[str, Any]] = [{"stage_name": "beta_stage1", "params": {}}]

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
def test_camel_to_snake() -> None:
    """Test the _camel_to_snake utility function for various cases."""
    assert _camel_to_snake("SimpleWorkflow") == "simple_workflow"
    assert _camel_to_snake("WorkflowWithABBREVIATION") == "workflow_with_abbreviation"
    assert _camel_to_snake("Already_Snake_Case") == "already_snake_case"
    assert _camel_to_snake("ExampleSlicingWorkflow") == "example_slicing_workflow"


# --- Tests for register_workflow ---
def test_register_workflow_success() -> None:
    """Test successful registration of a workflow."""
    register_workflow(MockWorkflowAlpha)
    expected_key: str = _camel_to_snake(MockWorkflowAlpha.__name__)
    assert expected_key in WORKFLOW_REGISTRY
    assert WORKFLOW_REGISTRY[expected_key] == MockWorkflowAlpha


def test_register_workflow_reregistration(caplog: LogCaptureFixture) -> None:
    """Test that re-registering a workflow logs a warning and overwrites.

    Args:
        caplog: Pytest fixture to capture log output.
    """
    expected_key_alpha: str = _camel_to_snake(MockWorkflowAlpha.__name__)
    register_workflow(MockWorkflowAlpha)

    WORKFLOW_REGISTRY[expected_key_alpha] = MockWorkflowAlpha # Ensure it's there

    with patch("src.core.workflows._camel_to_snake", return_value=expected_key_alpha):
        with caplog.at_level(logging.WARNING):
            register_workflow(MockWorkflowBeta)

    assert expected_key_alpha in WORKFLOW_REGISTRY
    assert WORKFLOW_REGISTRY[expected_key_alpha] == MockWorkflowBeta

    assert any(
        f"Workflow registry key '{expected_key_alpha}' (derived from class '{MockWorkflowBeta.__name__}') "
        "is already registered. Overwriting" in record.message
        for record in caplog.records
    )


def test_register_workflow_type_error_not_subclass() -> None:
    """Test that registering a class not inheriting from BaseWorkflow raises TypeError."""
    class NotAWorkflow:
        pass

    with pytest.raises(TypeError, match="must inherit from BaseWorkflow"):
        register_workflow(NotAWorkflow) # type: ignore


# --- Tests for BaseWorkflow and ExampleSlicingWorkflow ---


@patch("src.core.workflows.execute_stage_chain")
def test_base_workflow_run_method(mock_execute_stage_chain: MagicMock) -> None:
    """Test the BaseWorkflow's run method calls execute_stage_chain correctly.

    Args:
        mock_execute_stage_chain: MagicMock for the execute_stage_chain function.
    """
    register_workflow(MockWorkflowAlpha)
    mock_workflow_alpha_instance = MockWorkflowAlpha()

    initial_data_val: str = "/path/to/some/file.wav"
    initial_data_type_val: str = DATA_TYPE_FILE_PATH
    mock_context_val: Dict[str, Any] = {"project_id": 1, "db_session": MagicMock()}
    mock_execute_stage_chain.return_value = "final_processed_data"

    result: Any = mock_workflow_alpha_instance.run(
        initial_data=initial_data_val,
        initial_data_type=initial_data_type_val,
        context=mock_context_val,
    )

    assert result == "final_processed_data"

    expected_context_for_chain: Dict[str, Any] = mock_context_val.copy()
    expected_context_for_chain["current_workflow_name"] = mock_workflow_alpha_instance.name

    mock_execute_stage_chain.assert_called_once_with(
        initial_data=initial_data_val,
        initial_data_type=initial_data_type_val,
        chain_definition=mock_workflow_alpha_instance.stages_definition,
        context=expected_context_for_chain,
    )


def test_example_slicing_workflow_definition() -> None:
    """Test the definition (properties) of ExampleSlicingWorkflow."""
    workflow_key: str = _camel_to_snake(ExampleSlicingWorkflow.__name__)
    if workflow_key not in WORKFLOW_REGISTRY:
        register_workflow(ExampleSlicingWorkflow)

    WorkflowClass = WORKFLOW_REGISTRY.get(workflow_key)
    assert WorkflowClass is not None, f"{workflow_key} not found in WORKFLOW_REGISTRY."
    if WorkflowClass is None: return # For mypy

    instance = WorkflowClass()
    assert instance.name == "example_slicing_workflow"
    assert "noise reduction" in instance.description.lower()
    assert "slicing" in instance.description.lower()

    stages_def: List[Dict[str, Any]] = instance.stages_definition
    assert isinstance(stages_def, list)
    assert len(stages_def) == 2

    assert stages_def[0]["stage_name"] == "noise_reduction"
    assert "amount" in stages_def[0]["params"]

    assert stages_def[1]["stage_name"] == "slicing"
    assert stages_def[1]["params"] == {}
    # Note: Type compatibility of this workflow is not tested here, only its definition.
