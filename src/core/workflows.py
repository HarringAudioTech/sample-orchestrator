"""
Defines the preset workflow abstraction for chaining audio processing stages.

This module includes:
- A global registry (`WORKFLOW_REGISTRY`) for discovering available `BaseWorkflow` implementations.
- A function `register_workflow` to add new workflow classes to the registry.
- An abstract base class `BaseWorkflow` that defines the interface for all preset workflows.
- An example workflow implementation `ExampleSlicingWorkflow`.
"""

import logging
import os # For undefined-variable os.path.exists in __main__
import re # For potential name conversion (CamelCase to snake_case)
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type

# AudioProcessingStage is needed for dummy stage definitions in __main__ if kept,
# and potentially for type hinting in concrete workflows.
from src.core.processing_stages import AudioProcessingStage
from src.core.stage_runner import execute_stage_chain, STAGE_REGISTRY

# --- Logger Setup ---
logger = logging.getLogger(__name__)

# --- Workflow Registry ---
WORKFLOW_REGISTRY: Dict[str, Type["BaseWorkflow"]] = {}
"""
Global dictionary to store registered workflow classes.
Keys are the unique names of the workflows, and values are the workflow classes themselves.
"""


def _camel_to_snake(name: str) -> str:
    """
    Converts a CamelCase string to snake_case.

    Example: "MyWorkflowClass" becomes "my_workflow_class".

    Args:
        name (str): The CamelCase string.

    Returns:
        str: The snake_case version of the string.
    """
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def register_workflow(workflow_class: Type["BaseWorkflow"]):
    """
    Registers a workflow class in the global WORKFLOW_REGISTRY.

    The workflow class must inherit from `BaseWorkflow`.
    The registry key is derived by converting the workflow class name to snake_case.
    If a workflow with the same key is already registered, a warning will be logged,
    and the existing workflow will be overwritten.

    Args:
        workflow_class (Type[BaseWorkflow]): The workflow class to register.

    Raises:
        TypeError: If the provided class is not a subclass of `BaseWorkflow`.
        ValueError: If a valid registry key cannot be derived from the class name.
    """
    if not issubclass(workflow_class, BaseWorkflow):
        # f-string for specific exception message is generally okay
        raise TypeError(f"Workflow class '{workflow_class.__name__}' must inherit from BaseWorkflow.")

    registry_key_name = _camel_to_snake(workflow_class.__name__)
    if not registry_key_name:
        # f-string for specific exception message
        raise ValueError(f"Could not derive valid registry key from class name: {workflow_class.__name__}")

    if registry_key_name in WORKFLOW_REGISTRY:
        logger.warning(
            "Workflow registry key '%s' (from class '%s') is already registered. Overwriting. Prior: '%s'.",
            registry_key_name,
            workflow_class.__name__,
            WORKFLOW_REGISTRY[registry_key_name].__name__,
        )
    WORKFLOW_REGISTRY[registry_key_name] = workflow_class
    logger.info(
        "Successfully registered workflow: '%s' from class '%s'.",
        registry_key_name,
        workflow_class.__name__,
    )


# --- Base Workflow Class ---
class BaseWorkflow(ABC): # Docstring already present
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
        """
        The unique and human-readable name of this workflow.

        Example: "standard_podcast_cleanup", "vocal_enhancement_light"

        Returns:
            str: The name of the workflow.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """
        A brief description of what this workflow does and its intended use case.

        Example: "Applies noise reduction, normalization, and compression for
        podcasts."

        Returns:
            str: A human-readable description of the workflow.
        """

    @property
    @abstractmethod
    def stages_definition(self) -> List[Dict[str, Any]]:
        """
        Defines the chain of processing stages that constitute this workflow.

        This property must be implemented by subclasses to return a list of
        dictionaries. Each dictionary specifies a stage to be executed and
        its parameters.

        The structure for each stage dictionary is:
        - "stage_name" (str): The unique name of the stage (as registered in `STAGE_REGISTRY`).
        - "params" (dict, optional): Parameters to pass to this stage instance,
                                     overriding its defaults. If omitted or empty,
                                     the stage's default parameters will be used.

        Example:
            `[
                {"stage_name": "noise_reduction", "params": {"amount": 0.6, "aggressiveness": 3}},
                {"stage_name": "slicing", "params": {}}, # Uses slicing stage's default params
                {"stage_name": "another_custom_stage"}  # Also uses defaults
            ]`

        Returns:
            List[Dict[str, Any]]: The list defining the stages in the workflow.
        """
        # No 'pass' needed for abstract property with only a docstring.

    def run(self, initial_data: Any, initial_data_type: str,
            context: Dict[str, Any] = None) -> Any:
        """
        Executes the workflow's defined chain of processing stages.

        This method retrieves the stages definition from the `stages_definition`
        property and uses `execute_stage_chain` from `src.core.stage_runner`
        to run the stages sequentially.

        Args:
            initial_data (Any): The starting data for the first stage in the workflow.
            initial_data_type (str): The data type of `initial_data` (must be one of
                                     the `DATA_TYPE_*` constants from `processing_stages`).
            context (Dict[str, Any], optional): An optional dictionary for shared resources
                                                or information (e.g., `db_session`, `project_id`)
                                                to be passed to each stage's `process` method.
                                                Defaults to None.

        Returns:
            Any: The output data from the final stage in the workflow.

        Raises:
            ValueError: If a `stage_name` in the `stages_definition` is not found in the
                        `STAGE_REGISTRY` (raised by `execute_stage_chain`).
            TypeError: If data type mismatches occur between stages or with
                       `initial_data_type` (raised by `execute_stage_chain`).
            Exception: Any exception from a stage's `process` method will propagate
                       up (as per `execute_stage_chain`).
        """
        logger.info("Running workflow: '%s' (%s).", self.name, self.description)
        logger.debug(
            "Workflow '%s' stages definition: %s",
            self.name,
            self.stages_definition
        )

        if context is None:
            context = {} # Ensure context is a dict

        # Add workflow name to context for potential use by stages
        context["current_workflow_name"] = self.name

        return execute_stage_chain(
            initial_data=initial_data,
            initial_data_type=initial_data_type,
            chain_definition=self.stages_definition,
            context=context,
        )


# --- Example Workflow Implementation ---
class ExampleSlicingWorkflow(BaseWorkflow):
    """
    An example workflow that first applies noise reduction (placeholder)
    and then slices the audio into samples.
    """

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
                "stage_name": "noise_reduction",  # Assumes 'noise_reduction' stage is registered
                "params": {"amount": 0.3, "aggressiveness": 2},
            },
            {
                "stage_name": "slicing",  # Assumes 'slicing' stage is registered
                "params": {},  # Uses default parameters for the slicing stage
            },
        ]


# Register the example workflow
try:
    register_workflow(ExampleSlicingWorkflow)
except Exception as e:
    # Log error if registration fails, e.g. if BaseWorkflow is not fully
    # defined
    logger.critical("Failed to register ExampleSlicingWorkflow: %s", e, exc_info=True)


if __name__ == "__main__":
    # This section is for demonstration and basic testing.
    # It's significantly simplified to avoid complex dummy stage setups
    # and potential linting issues from such test code.

    # Configure basic logging for the example run
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("--- Workflow Module Main ---")

    # Attempt to import actual stages to ensure they are registered for the example.
    # These imports are fine here as this block is guarded by `if __name__ == "__main__"`.
    # They are marked with noqa for linters if they appear unused directly in this block,
    # as their primary purpose here is side-effect (registration).
    try:
        # pylint: disable=import-outside-toplevel,unused-import
        import src.core.stages.slicing_stage # noqa: F401
        import src.core.stages.noise_reduction_stage # noqa: F401
        # pylint: enable=import-outside-toplevel,unused-import
        logger.info("Main: Attempted to load SlicingStage and NoiseReductionStage.")
    except ImportError as e_import:
        logger.warning(
            "Main: Could not import actual stages (slicing_stage, noise_reduction_stage): %s. "
            "ExampleSlicingWorkflow might not run correctly if stages are not registered.", e_import
        )

    logger.info("--- Available Workflows in Registry ---")
    if not WORKFLOW_REGISTRY:
        logger.info("Main: No workflows are currently registered.")
    for key, wf_class_val in WORKFLOW_REGISTRY.items(): # Renamed wf_class to wf_class_val
        try:
            instance = wf_class_val()
            logger.info(
                "Main: Registry Key: '%s', Workflow Name: '%s', Description: '%s'",
                key, instance.name, instance.description
            )
        except Exception as e_inspect: # Catch broad exception during this debug inspection
            logger.error(
                "Main: Could not inspect workflow class %s: %s",
                wf_class_val.__name__, e_inspect, exc_info=True
            )

    # --- Example Workflow Execution (ExampleSlicingWorkflow) ---
    logger.info("--- Testing ExampleSlicingWorkflow Execution ---")
    EXAMPLE_WORKFLOW_REGISTRY_KEY = "example_slicing_workflow"

    WorkflowToTestClass = WORKFLOW_REGISTRY.get(EXAMPLE_WORKFLOW_REGISTRY_KEY)
    if WorkflowToTestClass:
        workflow_to_test_instance = WorkflowToTestClass()
        logger.info("Main: Attempting to run workflow: '%s'", workflow_to_test_instance.name)
        logger.warning(
            "Main: Note - ExampleSlicingWorkflow might have type mismatches or "
            "stage dependencies (like needing a database session) not fully mocked here. "
            "This primarily tests the workflow's run mechanism if stages are compatible."
        )

        mock_data_input = "/path/to/dummy/audio.wav"
        mock_data_input_type = "file_path"

        mock_run_context = {
            "db_session": "mocked_db_session_for_test", # Not a real session
            "recording_id": 100,
            "project_id": 10,
            "output_sample_dir": os.path.join("temp_test_outputs", EXAMPLE_WORKFLOW_REGISTRY_KEY),
        }

        try:
            if not os.path.exists(mock_run_context["output_sample_dir"]):
                os.makedirs(mock_run_context["output_sample_dir"], exist_ok=True)

            logger.info(
                "Main: Executing workflow '%s' with mock data. (Actual run is commented out).",
                workflow_to_test_instance.name
            )
            # The actual run is commented out to prevent errors in automated environments
            # due to unmet dependencies (e.g., real audio file, database session).
            # To test locally, uncomment the following lines and ensure dependencies are met.
            # final_result_output = workflow_to_test_instance.run(
            #     initial_data=mock_data_input,
            #     initial_data_type=mock_data_input_type,
            #     context=mock_run_context,
            # )
            # logger.info(
            #     "Main: Workflow '%s' execution finished. Result: %s",
            #     workflow_to_test_instance.name, final_result_output
            # )
            logger.info(
                "Main: Actual run of ExampleSlicingWorkflow is commented out in this example."
            )

        except Exception as e_wf_run:
            logger.error(
                "Main: Error during (mock) example workflow execution of '%s': %s",
                workflow_to_test_instance.name, e_wf_run, exc_info=True
            )
    else:
        logger.error(
            "Main: Workflow '%s' not found in WORKFLOW_REGISTRY.", EXAMPLE_WORKFLOW_REGISTRY_KEY
        )

    logger.info("--- Workflow Module Main Finished ---")
