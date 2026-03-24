"""
Base workflow classes and registry for audio processing workflows.

This module provides:
- BaseWorkflow abstract class
- WORKFLOW_REGISTRY for discovering available workflows
- register_workflow function for workflow registration
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type, Optional

from src.core.stage_runner import execute_stage_chain

logger = logging.getLogger(__name__)

# --- Workflow Registry ---
WORKFLOW_REGISTRY: Dict[str, Type["BaseWorkflow"]] = {}


def _camel_to_snake(name: str) -> str:
    """Converts CamelCase to snake_case."""
    s1 = re.sub(r"([A-Za-z0-9])([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    s3 = re.sub(r"_+", "_", s2)
    return s3.lower()


def register_workflow(workflow_class: Type["BaseWorkflow"]) -> None:
    """Registers a workflow class in the global WORKFLOW_REGISTRY."""
    if not issubclass(workflow_class, BaseWorkflow):
        raise TypeError(
            f"Workflow class '{workflow_class.__name__}' must inherit from BaseWorkflow."
        )

    registry_key_name = _camel_to_snake(workflow_class.__name__)
    if not registry_key_name:
        raise ValueError(
            f"Could not derive a valid registry key name from class name '{workflow_class.__name__}'."
        )

    if registry_key_name in WORKFLOW_REGISTRY:
        logger.warning(
            f"Workflow registry key '{registry_key_name}' already registered. "
            f"Overwriting with new class '{workflow_class.__name__}'."
        )
    WORKFLOW_REGISTRY[registry_key_name] = workflow_class
    logger.info(
        f"Registered workflow: '{registry_key_name}' (class: '{workflow_class.__name__}')"
    )


class BaseWorkflow(ABC):
    """
    Abstract Base Class for defining preset audio processing workflows.

    A workflow consists of a defined chain of audio processing stages
    that are executed sequentially. Subclasses must implement the
    name, description, and stages_definition properties.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique and human-readable name of this workflow."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A brief description of what this workflow does."""
        pass

    @property
    @abstractmethod
    def stages_definition(self) -> List[Dict[str, Any]]:
        """Defines the chain of processing stages for this workflow."""
        pass

    def run(
        self,
        initial_data: Any,
        initial_data_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Executes the workflow's defined chain of processing stages."""
        logger.info(f"Running workflow: '{self.name}' ({self.description}).")

        current_context = context.copy() if context else {}
        current_context["current_workflow_name"] = self.name

        return execute_stage_chain(
            initial_data=initial_data,
            initial_data_type=initial_data_type,
            chain_definition=self.stages_definition,
            context=current_context,
        )


# --- Built-in Workflows ---

class ExampleSlicingWorkflow(BaseWorkflow):
    """Example workflow: noise reduction then slicing."""

    @property
    def name(self) -> str:
        return "example_slicing_workflow"

    @property
    def description(self) -> str:
        return "A simple example workflow that runs noise reduction (placeholder) then audio slicing."

    @property
    def stages_definition(self) -> List[Dict[str, Any]]:
        return [
            {
                "stage_name": "noise_reduction",
                "params": {"amount": 0.3, "aggressiveness": 2},
            },
            {
                "stage_name": "slicing",
                "params": {},
            },
        ]


class DecentSamplerCreationWorkflow(BaseWorkflow):
    """Workflow for creating a Decent Sampler instrument from an audio recording."""

    @property
    def name(self) -> str:
        return "decent_sampler_creation_workflow"

    @property
    def description(self) -> str:
        return "Slices audio and exports to a Decent Sampler (.dspreset) instrument."

    @property
    def stages_definition(self) -> List[Dict[str, Any]]:
        return [
            {
                "stage_name": "slicing",
                "params": {},
            },
            {
                "stage_name": "decent_sampler_export",
                "params": {
                    "instrument_name": "My New Instrument",
                    "instrument_author": "Orchestrator",
                },
            },
        ]


# Register built-in workflows
try:
    register_workflow(ExampleSlicingWorkflow)
    register_workflow(DecentSamplerCreationWorkflow)
except Exception as e:
    logger.critical(f"Failed to register built-in workflows: {e}", exc_info=True)
