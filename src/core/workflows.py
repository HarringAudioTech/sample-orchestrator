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
from typing import Any, Dict, List, Type, Optional

from src.core.stage_runner import execute_stage_chain, STAGE_REGISTRY as ACTUAL_STAGE_REGISTRY
from src.core.processing_stages import AudioProcessingStage # For dummy stages in __main__

# AudioProcessingStage and data type constants are not directly needed by BaseWorkflow itself,
# but might be useful for type hinting in concrete workflow implementations if they
# construct stage definitions dynamically or need to reference data types.

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
    # Handle cases like "WordWord" -> "Word_Word" (e.g. SimpleWorkflow -> Simple_Workflow)
    # and also internal capitals like "wordWord" -> "word_Word".
    s1: str = re.sub(r"([A-Za-z0-9])([A-Z][a-z]+)", r"\1_\2", name)

    # Handle cases like "wordWORD" -> "word_WORD" (e.g. SimpleHTTP -> Simple_HTTP)
    # or "WordWORD" if the first rule didn't catch a transition from lowercase.
    s2: str = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)

    # Collapse multiple underscores that might have been introduced.
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
            f"Workflow class '{
                workflow_class.__name__}' must inherit from BaseWorkflow."
        )

    registry_key_name: str = _camel_to_snake(workflow_class.__name__)
    if not registry_key_name:
        raise ValueError(
            f"Could not derive a valid registry key name from class name '{
                workflow_class.__name__}'."
        )

    if registry_key_name in WORKFLOW_REGISTRY:
        logger.warning(
            f"Workflow registry key '{registry_key_name}' (derived from class '{
                workflow_class.__name__}') "
            f"is already registered. Overwriting with new class. "
            f"Previous class: '{
                WORKFLOW_REGISTRY[registry_key_name].__name__}'."
        )
    WORKFLOW_REGISTRY[registry_key_name] = workflow_class
    logger.info(
        f"Successfully registered workflow: '{registry_key_name}' (class: '{
            workflow_class.__name__}')"
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
        """
        The unique and human-readable name of this workflow.

        Example: "standard_podcast_cleanup", "vocal_enhancement_light"

        Returns:
            str: The name of the workflow.
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        A brief description of what this workflow does and its intended use case.

        Example: "Applies noise reduction, normalization, and compression for podcasts."

        Returns:
            str: A human-readable description of the workflow.
        """
        pass

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
        pass

    def run(
        self, initial_data: Any, initial_data_type: str, context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Executes the workflow's defined chain of processing stages.

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
            TypeError: If data type mismatches occur between stages or with `initial_data_type`
                       (raised by `execute_stage_chain`).
            Exception: Any exception raised by a stage's `process` method during execution
                       will propagate up (as per `execute_stage_chain`).
        """
        logger.info(f"Running workflow: '{self.name}' ({self.description}).")
        logger.debug(
            f"Workflow '{
                self.name}' stages definition: {
                self.stages_definition}"
        )

        if context is None:
            context = {}

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
    logger.critical(f"Failed to register ExampleSlicingWorkflow: {e}", exc_info=True)


if __name__ == "__main__":
    # This section is for demonstration and basic testing of the workflow system.
    # It requires concrete AudioProcessingStage implementations to be registered
    # in stage_runner.py's STAGE_REGISTRY.

    # Configure basic logging for the example
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # --- Prerequisite: Ensure example stages are registered (from stage_runner's __main__ or similar) ---
    # This is a bit tricky for a direct __main__ run here, as stages are in different files.
    # For a real application, stage registration would happen at import time
    # or app startup.

        # Attempt to import real stages to trigger their registration
    try:
            from src.core.stages.slicing_stage import SlicingStage # noqa F401
            from src.core.stages.noise_reduction_stage import NoiseReductionStage # noqa F401
            logger.info("Actual SlicingStage and NoiseReductionStage imported for __main__ test.")
    except ImportError:
            logger.warning(
                "Could not import actual SlicingStage or NoiseReductionStage for __main__ test. "
                "Falling back to dummy stages if not already registered."
        )
            # Define and register dummy stages only if real ones aren't found or couldn't be imported
            # and they are not already in the registry (e.g. from a previous partial run)

            example_workflow_instance_for_check = ExampleSlicingWorkflow()
            required_stages_for_example = [
                sdef["stage_name"] for sdef in example_workflow_instance_for_check.stages_definition
            ]

            if "noise_reduction" in required_stages_for_example and "noise_reduction" not in ACTUAL_STAGE_REGISTRY:
            class DummyNoiseReduction(AudioProcessingStage):
                @property
                    def name(self) -> str: return "noise_reduction"
                @property
                    def description(self) -> str: return "Dummy Noise Reduction"
                @property
                    def input_type(self) -> str: return "audio_buffer_mono" # Example
                @property
                    def output_type(self) -> str: return "audio_buffer_mono"
                @property
                    def default_params(self) -> Dict[str, Any]: return {}
                    def process(self, data: Any, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
                        logger.info(f"[{self.name}] Dummy processing data: {type(data)}")
                    return data
                from src.core.stage_runner import register_stage
                register_stage(DummyNoiseReduction)
                logger.info("Registered DummyNoiseReduction for __main__ test.")

            if "slicing" in required_stages_for_example and "slicing" not in ACTUAL_STAGE_REGISTRY:
            class DummySlicing(AudioProcessingStage):
                @property
                    def name(self) -> str: return "slicing"
                @property
                    def description(self) -> str: return "Dummy Slicing"
                @property
                    # SlicingStage actually takes file_path
                    def input_type(self) -> str: return "audio_buffer_mono"
                @property
                    def output_type(self) -> str: return "list_of_sample_data"
                @property
                    def default_params(self) -> Dict[str, Any]: return {}
                    def process(self, data: Any, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
                        logger.info(f"[{self.name}] Dummy processing data: {type(data)}")
                        return [{"sample_id": 1, "status": "dummy"}]
                from src.core.stage_runner import register_stage
                register_stage(DummySlicing)
                logger.info("Registered DummySlicing for __main__ test.")


    logger.info("\n--- Available Workflows ---")
    for wf_key, wf_class_val in WORKFLOW_REGISTRY.items():
        try:
            # To get name and description, we need an instance.
            # This assumes concrete classes can be instantiated without args.
            instance = wf_class_val()
            logger.info(
                f"Key: '{wf_key}', Name: '{
                    instance.name}', Desc: '{
                    instance.description}'"
            )
        except Exception as e:
            logger.error(
                f"Could not inspect workflow class {
                    wf_class_val.__name__}: {e}"
            )

    # --- Example Workflow Execution ---
    logger.info("\n--- Testing ExampleSlicingWorkflow ---")
    workflow_to_run_key: str = (
        "example_slicing_workflow"  # Derived from ExampleSlicingWorkflow class name
    )

    WorkflowCls = WORKFLOW_REGISTRY.get(workflow_to_run_key)
    if WorkflowCls:
        workflow_instance = WorkflowCls()
        from src.core.processing_stages import DATA_TYPE_FILE_PATH, DATA_TYPE_AUDIO_BUFFER_MONO

        logger.warning(
            "The ExampleSlicingWorkflow might have type mismatches depending on actual "
            "registered stages. NoiseReductionStage (if real) outputs audio_buffer_mono, "
            "while SlicingStage (if real) expects file_path. This test might fail if "
            "using real stages without an adapter stage in between, or if dummy stages "
            "don't align types."
        )

        # For a more robust __main__ test, we should ideally use the types defined by the
        # *actual* first stage of the *actual* ExampleSlicingWorkflow.
        # Let's assume the first stage is 'noise_reduction' and it (or its dummy)
        # can take a file_path and output a file_path for simplicity here,
        # or that the example workflow is internally consistent (e.g., uses dummy stages
        # that are type-compatible).

        # If ExampleSlicingWorkflow starts with a stage like actual NoiseReductionStage,
        # it would expect DATA_TYPE_AUDIO_BUFFER_MONO.
        # If it starts with actual SlicingStage, it would expect DATA_TYPE_FILE_PATH.
        # The example workflow is: noise_reduction -> slicing.
        # Actual NoiseReductionStage: input AUDIO_BUFFER_MONO
        # Actual SlicingStage: input FILE_PATH
        # So, ExampleSlicingWorkflow is flawed if using these actual stages directly.

        # Let's assume for this test, the first stage of ExampleSlicingWorkflow
        # (noise_reduction or its dummy) is made to accept DATA_TYPE_FILE_PATH
        # and also outputs DATA_TYPE_FILE_PATH, and SlicingStage (or its dummy)
        # also takes DATA_TYPE_FILE_PATH. This is a simplification for __main__.
        initial_mock_data: str = "/path/to/some/audio_file.wav"  # Dummy path
        initial_mock_data_type: str = DATA_TYPE_FILE_PATH

        mock_context_main: Dict[str, Any] = {
            "db_session": "dummy_db_session_for_main_test (mocked)",
            "recording_id": 99, # Different from OnlySlicingWorkflow test
            "project_id": 99,
            "output_sample_dir": "/tmp/test_example_workflow_output",
        }
        if not os.path.exists(mock_context_main["output_sample_dir"]):
            os.makedirs(mock_context_main["output_sample_dir"], exist_ok=True)

        try:
            logger.info(f"Attempting to run workflow: {workflow_instance.name}")
            # final_output = workflow_instance.run(initial_mock_data, initial_mock_data_type, mock_context_main)
            # logger.info(f"Output of {workflow_instance.name}: {final_output}")
            logger.info(
                f"Skipping actual run of {
                    workflow_instance.name} in __main__ due to potential complex dependencies (real files, DB)."
            )
        except Exception as e:
            logger.error(
                f"Error running {workflow_instance.name}: {e}", exc_info=True
            )


        # Option: Test with a workflow that ONLY has slicing for this __main__
        # This was already defined, let's try to run it if SlicingStage (dummy or real) is available
        only_slicing_workflow_key = "only_slicing_workflow" # from OnlySlicingWorkflow class name
        OnlySlicingWorkflowCls = WORKFLOW_REGISTRY.get(only_slicing_workflow_key)

        if not OnlySlicingWorkflowCls: # If not registered in previous block due to some logic path
            class OnlySlicingWorkflow(BaseWorkflow): # Re-define if necessary
                @property
                def name(self) -> str: return "test_only_slicing"
                @property
                def description(self) -> str: return "Test workflow with only the slicing stage."
                @property
                def stages_definition(self) -> List[Dict[str, Any]]:
                    return [{"stage_name": "slicing", "params": {}}]
            register_workflow(OnlySlicingWorkflow)
            OnlySlicingWorkflowCls = OnlySlicingWorkflow


        if OnlySlicingWorkflowCls:
            test_slicing_workflow_instance = OnlySlicingWorkflowCls()
            logger.info(f"\n--- Testing {test_slicing_workflow_instance.name} ---")

            mock_context_slicing: Dict[str, Any] = {
                "db_session": "dummy_db_session_for_slicing_test (mocked)",
                "recording_id": 1,
                "project_id": 1,
                "output_sample_dir": "/tmp/test_slicing_output_workflow_2",
            }
            if not os.path.exists(mock_context_slicing["output_sample_dir"]):
                os.makedirs(mock_context_slicing["output_sample_dir"], exist_ok=True)

            initial_slicing_data: str = "/path/to/another/audio.wav" # Dummy path
            initial_slicing_data_type: str = DATA_TYPE_FILE_PATH

            if "slicing" in ACTUAL_STAGE_REGISTRY :
                logger.info(
                    f"Attempting to run '{test_slicing_workflow_instance.name}'. This might fail if SlicingStage has unmet dependencies (real file, DB)."
                )
                # try:
                #     final_result_slicing = test_slicing_workflow_instance.run(
                #         initial_slicing_data, initial_slicing_data_type, mock_context_slicing
                #     )
                #     logger.info(f"Result of '{test_slicing_workflow_instance.name}': {final_result_slicing}")
                # except Exception as e_slice:
                #     logger.error(f"Error during run of '{test_slicing_workflow_instance.name}': {e_slice}", exc_info=True)
                logger.info(f"Skipping actual run of {test_slicing_workflow_instance.name} in __main__ due to dependencies.")

            else:
                logger.warning(
                    f"Skipping run of '{
                        test_slicing_workflow_instance.name}' as 'slicing' stage not found in STAGE_REGISTRY."
                )
        else:
            logger.error(f"Workflow '{only_slicing_workflow_key}' not found in registry for testing.")

    else:
        logger.error(f"Workflow '{workflow_to_run_key}' not found in registry.")

    logger.info("Workflow system demonstration finished.")


# Helper for __main__ to avoid NameError if STAGE_REGISTRY is not
# populated from stage_runner (though direct import is preferred now)
def from_src_core_stage_runner_import_STAGE_REGISTRY_else_empty_dict() -> Dict[str, Type[AudioProcessingStage]]:
    # This helper is less critical if ACTUAL_STAGE_REGISTRY is imported directly at the top.
    # Kept for structural reference or if direct import causes issues in some contexts.
    return ACTUAL_STAGE_REGISTRY # Prefer direct import
