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
    """Converts a string from CamelCase to snake_case.

    This utility function is primarily used to generate a default snake_case
    registry key from a workflow's class name (which is typically CamelCase).
    The conversion involves:
    1. Inserting an underscore before any uppercase letter that is preceded by
       a letter or digit and followed by a lowercase letter (e.g., "CamelCase" -> "Camel_Case").
    2. Inserting an underscore before any uppercase letter that is preceded by
       a lowercase letter or digit (e.g., "Camel_Case" -> "Camel_Case", "SimpleHTTP" -> "Simple_HTTP").
    3. Replacing multiple consecutive underscores with a single underscore.
    4. Converting the entire string to lowercase.

    Args:
        name (str): The input string, typically in CamelCase format.

    Returns:
        str: The converted string in snake_case format.
    """
    s1: str = re.sub(r"([A-Za-z0-9])([A-Z][a-z]+)", r"\1_\2", name)
    s2: str = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    s3: str = re.sub(r"_+", "_", s2)
    return s3.lower()


def register_workflow(workflow_class: Type["BaseWorkflow"]) -> None:
    """Registers a workflow class in the global `WORKFLOW_REGISTRY`.

    This function adds a given `workflow_class` to a central registry, making
    it discoverable and executable by name. The key used for registration in
    the `WORKFLOW_REGISTRY` is automatically derived by converting the
    `workflow_class.__name__` (which is typically in CamelCase) to snake_case
    using the `_camel_to_snake` utility function.

    The provided `workflow_class` must be a subclass of `BaseWorkflow`.
    If a workflow with the same derived snake_case key is already registered,
    a warning message is logged, and the existing entry in the registry is
    overwritten with the new `workflow_class`.

    Args:
        workflow_class (Type[BaseWorkflow]): The workflow class to be registered.
            This should be the class itself, not an instance of the class.

    Raises:
        TypeError: If the `workflow_class` is not a direct or indirect subclass
                   of `BaseWorkflow`.
        ValueError: If a valid snake_case registry key cannot be derived from
                    the `workflow_class.__name__` (e.g., if the name is empty
                    after sanitization, though this is unlikely for valid class names).
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

        This method takes the initial data and its type, and then invokes
        `execute_stage_chain` from `src.core.stage_runner` using the workflow's
        specific `stages_definition`.

        It also enriches the `context` dictionary by adding a
        `current_workflow_name` key, allowing stages within the chain to be
        aware of the workflow they are part of. If the provided `context` is
        `None`, a new dictionary is created for this purpose.

        Args:
            initial_data (Any): The input data to be fed into the first stage
                                of the workflow's processing chain.
            initial_data_type (str): A string identifier for the type of
                                     `initial_data` (e.g., "file_path",
                                     "audio_buffer_mono"). This must be
                                     compatible with the expected input type of
                                     the first stage in the `stages_definition`.
            context (Optional[Dict[str, Any]]): An optional dictionary of shared
                resources or state to be passed through to each stage in the
                chain. If `None`, an empty context is initialized. The workflow
                name is added to this context. Defaults to None.

        Returns:
            Any: The data returned by the final stage in the workflow's
                 `stages_definition`. The type of this data depends on the
                 `output_type` of the last stage.

        Raises:
            Propagates any exceptions raised by `execute_stage_chain`, which
            can include `ValueError` (e.g., for missing or unregistered stages)
            or `TypeError` (for data type mismatches between stages).
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
