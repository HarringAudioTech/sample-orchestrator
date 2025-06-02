"""
Defines the preset workflow abstraction for chaining audio processing stages.

This module includes:
- A global registry (`WORKFLOW_REGISTRY`) for discovering available `BaseWorkflow` implementations.
- A function `register_workflow` to add new workflow classes to the registry.
- An abstract base class `BaseWorkflow` that defines the interface for all preset workflows.
- An example workflow implementation `ExampleSlicingWorkflow`.
"""

import logging
import re  # For potential name conversion (CamelCase to snake_case)
import os # For __main__ example
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type, Optional, Generator # Added Generator

from src.core.stage_runner import execute_stage_chain, STAGE_REGISTRY as ACTUAL_STAGE_REGISTRY
from src.core.processing_stages import AudioProcessingStage # For dummy stages in __main__
from src.core.processing_stages import DATA_TYPE_FILE_PATH, DATA_TYPE_AUDIO_BUFFER_MONO # For __main__

# --- Logger Setup ---
logger = logging.getLogger(__name__)

# --- Workflow Registry ---
WORKFLOW_REGISTRY: Dict[str, Type["BaseWorkflow"]] = {}
"""Global dictionary to store registered workflow classes.

Keys are the unique names of the workflows (typically snake_case derived from class name),
and values are the workflow classes themselves.
"""


def _camel_to_snake(name: str) -> str:
    """Converts a CamelCase string to snake_case.

    Args:
        name: The CamelCase string.

    Returns:
        The snake_case version of the string.
    """
    s1: str = re.sub(r"([A-Za-z0-9])([A-Z][a-z]+)", r"\1_\2", name)
    s2: str = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    s3: str = re.sub(r"_+", "_", s2)
    return s3.lower()


def register_workflow(workflow_class: Type["BaseWorkflow"]) -> None:
    """Registers a workflow class in the global WORKFLOW_REGISTRY.

    The workflow class must inherit from `BaseWorkflow`.
    The registry key is derived by converting the workflow class's __name__
    to snake_case.
    If a workflow with the same key is already registered, a warning will be logged,
    and the existing workflow will be overwritten.

    Args:
        workflow_class: The workflow class to register.

    Raises:
        TypeError: If the provided class is not a subclass of BaseWorkflow.
        ValueError: If a registry key cannot be derived from the class name.
    """
    if not issubclass(workflow_class, BaseWorkflow):
        raise TypeError(
            f"Workflow class '{workflow_class.__name__}' must inherit from BaseWorkflow."
        )

    registry_key_name: str = _camel_to_snake(workflow_class.__name__)
    if not registry_key_name:
        raise ValueError(f"Could not derive a valid registry key name from class name '{workflow_class.__name__}'.")

    if registry_key_name in WORKFLOW_REGISTRY:
        logger.warning(
            f"Workflow registry key '{registry_key_name}' (derived from class '{workflow_class.__name__}') "
            f"is already registered. Overwriting with new class. "
            f"Previous class: '{WORKFLOW_REGISTRY[registry_key_name].__name__}'."
        )
    WORKFLOW_REGISTRY[registry_key_name] = workflow_class
    logger.info(
        f"Successfully registered workflow: '{registry_key_name}' (class: '{workflow_class.__name__}')"
    )


# --- Base Workflow Class ---
class BaseWorkflow(ABC):
    """
    Abstract Base Class for defining preset audio processing workflows.

    A workflow consists of a defined chain of audio processing stages
    (from `src.core.processing_stages`) that are executed sequentially.
    Subclasses must implement the `name`, `description`, and `stages_definition`
    properties.
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
        self, initial_data: Any, initial_data_type: str, context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Executes the workflow's defined chain of processing stages.

        Args:
            initial_data: The starting data for the first stage.
            initial_data_type: The data type of `initial_data`.
            context: Optional shared resources for stages.

        Returns:
            The output data from the final stage in the workflow.
        """
        logger.info(f"Running workflow: '{self.name}' ({self.description}).")
        logger.debug(
            f"Workflow '{self.name}' stages definition: {self.stages_definition}"
        )

        current_context = context.copy() if context else {}
        current_context["current_workflow_name"] = self.name

        return execute_stage_chain(
            initial_data=initial_data,
            initial_data_type=initial_data_type,
            chain_definition=self.stages_definition,
            context=current_context,
        )


# --- Example Workflow Implementation ---
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

try:
    register_workflow(ExampleSlicingWorkflow)
except Exception as e:
    logger.critical(f"Failed to register ExampleSlicingWorkflow: {e}", exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        from src.core.stages.slicing_stage import SlicingStage # noqa F401
        from src.core.stages.noise_reduction_stage import NoiseReductionStage # noqa F401
        logger.info("Actual SlicingStage and NoiseReductionStage imported for __main__ test.")
    except ImportError:
        logger.warning(
            "Could not import actual SlicingStage or NoiseReductionStage for __main__ test. "
            "Falling back to dummy stages if not already registered."
        )
        example_workflow_instance_for_check = ExampleSlicingWorkflow()
        required_stages_for_example: List[str] = [
            sdef["stage_name"] for sdef in example_workflow_instance_for_check.stages_definition
        ]

        if "noise_reduction" in required_stages_for_example and "noise_reduction" not in ACTUAL_STAGE_REGISTRY:
            class DummyNoiseReduction(AudioProcessingStage):
                @property
                def name(self) -> str: return "noise_reduction"
                @property
                def description(self) -> str: return "Dummy Noise Reduction"
                @property
                def input_type(self) -> str: return DATA_TYPE_AUDIO_BUFFER_MONO
                @property
                def output_type(self) -> str: return DATA_TYPE_AUDIO_BUFFER_MONO
                @property
                def default_params(self) -> Dict[str, Any]: return {}
                def process(self, data: Any, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
                    logger.info(f"[{self.name}] Dummy processing data: {type(data)}")
                    return data # Corrected indentation
            from src.core.stage_runner import register_stage # Local import
            register_stage(DummyNoiseReduction)
            logger.info("Registered DummyNoiseReduction for __main__ test.")

        if "slicing" in required_stages_for_example and "slicing" not in ACTUAL_STAGE_REGISTRY:
            class DummySlicing(AudioProcessingStage):
                @property
                def name(self) -> str: return "slicing"
                @property
                def description(self) -> str: return "Dummy Slicing"
                @property
                def input_type(self) -> str: return DATA_TYPE_AUDIO_BUFFER_MONO # Example, SlicingStage expects file_path
                @property
                def output_type(self) -> str: return "list_of_sample_data" # Using string as per constants
                @property
                def default_params(self) -> Dict[str, Any]: return {}
                def process(self, data: Any, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
                    logger.info(f"[{self.name}] Dummy processing data: {type(data)}")
                    return [{"sample_id": 1, "status": "dummy"}]
            from src.core.stage_runner import register_stage # Local import
            register_stage(DummySlicing)
            logger.info("Registered DummySlicing for __main__ test.")

    logger.info("\n--- Available Workflows ---")
    for wf_key, wf_class_val in WORKFLOW_REGISTRY.items():
        try:
            instance = wf_class_val()
            logger.info(
                f"Key: '{wf_key}', Name: '{instance.name}', Desc: '{instance.description}'"
            )
        except Exception as e:
            logger.error(f"Could not inspect workflow class {wf_class_val.__name__}: {e}")

    logger.info("\n--- Testing ExampleSlicingWorkflow (structure) ---")
    workflow_to_run_key: str = "example_slicing_workflow"
    WorkflowCls = WORKFLOW_REGISTRY.get(workflow_to_run_key)

    if WorkflowCls:
        workflow_instance = WorkflowCls()
        logger.info(f"Workflow: {workflow_instance.name}, Desc: {workflow_instance.description}")
        logger.info(f"Stages: {workflow_instance.stages_definition}")
        logger.warning(
            "Actual execution of ExampleSlicingWorkflow in __main__ is skipped due to potential "
            "type mismatches and complex dependencies (real files, DB session) not fully mocked here."
        )
    else:
        logger.error(f"Workflow '{workflow_to_run_key}' not found in registry.")

    logger.info("Workflow system demonstration finished.")
