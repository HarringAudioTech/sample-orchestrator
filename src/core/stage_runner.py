"""
Manages the registration and execution of audio processing stages.

This module provides:
- A global registry (`STAGE_REGISTRY`) for discovering available `AudioProcessingStage` implementations.
- A function `register_stage` to add new stage classes to the registry.
- A function `execute_stage_chain` to run a sequence of processing stages (a chain)
  on an initial piece of data.
"""

import logging
import os  # Added to fix undefined-variable for os.path.exists in example
from typing import Any, Dict, List, Type

# AudioProcessingStage is the core dependency. Specific DATA_TYPE_* constants
# are not directly used by the runner logic itself, but by the stages it runs.
# DATA_TYPE_LIST_OF_FILE_PATHS was specifically mentioned as unused.
from src.core.processing_stages import AudioProcessingStage

# --- Logger Setup ---
logger = logging.getLogger(__name__)

# --- Stage Registry ---
STAGE_REGISTRY: Dict[str, Type[AudioProcessingStage]] = {}
"""
Global dictionary to store registered audio processing stage classes.
Keys are the unique names of the stages (from `stage_class.name`),
and values are the stage classes themselves.
"""


def register_stage(stage_class: Type[AudioProcessingStage]):
    """
    Registers an audio processing stage class in the global STAGE_REGISTRY.

    The stage class must inherit from `AudioProcessingStage` and have a unique `name` property.
    If a stage with the same name is already registered, a warning will be logged,
    and the existing stage will be overwritten.

    Args:
        stage_class (Type[AudioProcessingStage]): The audio processing stage class to register.

    Raises:
        TypeError: If the provided class is not a subclass of AudioProcessingStage
                   or does not have a 'name' attribute.
    """
    if not issubclass(stage_class, AudioProcessingStage):
        raise TypeError(
            f"Stage class '{
                stage_class.__name__}' must inherit from AudioProcessingStage."
        )

    try:
        stage_name = stage_class.name
        if not isinstance(stage_name, str) or not stage_name:
            raise ValueError(
                "Stage class must have a valid 'name' property (non-empty string)."
            ) # No f-string needed
    except AttributeError as e:
        # f-string for specific exception message is fine
        raise TypeError(f"Stage class '{stage_class.__name__}' must have a 'name' property.") from e

    if stage_name in STAGE_REGISTRY:
        logger.warning(
            "Stage name '%s' from class '%s' is already registered. Overwriting. Previous: '%s'.",
            stage_name, stage_class.__name__, STAGE_REGISTRY[stage_name].__name__
        )
    STAGE_REGISTRY[stage_name] = stage_class
    logger.info(
        "Successfully registered stage: '%s' from class '%s'.",
        stage_name, stage_class.__name__
    )


# --- Stage Chain Execution ---
def execute_stage_chain(
    initial_data: Any,
    initial_data_type: str,
    chain_definition: List[Dict[str, Any]],
    context: Dict[str, Any] = None,
) -> Any:
    """
    Executes a chain of audio processing stages sequentially.

    The output of each stage becomes the input for the next stage in the chain.
    Data types are validated between stages to ensure compatibility.

    Args:
        initial_data (Any): The starting data for the first stage in the chain.
        initial_data_type (str): The data type of `initial_data` (must be one of
                                 the `DATA_TYPE_*` constants from `processing_stages`).
        chain_definition (List[Dict[str, Any]]): A list of dictionaries, where each
                                                 dictionary defines a stage to be executed.
                                                 Each dictionary should have:
                                                 - "stage_name" (str): The unique name of the stage
                                                   (must be registered in `STAGE_REGISTRY`).
                                                 - "params" (dict, optional): Parameters to pass to this
                                                   stage instance, overriding its defaults.
        context (Dict[str, Any], optional): An optional dictionary for shared resources
                                            or information (e.g., `db_session`, `project_id`)
                                            to be passed to each stage's `process` method.
                                            Defaults to None.

    Returns:
        Any: The output data from the final stage in the chain. If `chain_definition`
             is empty, returns `initial_data`.

    Raises:
        ValueError: If a `stage_name` in the `chain_definition` is not found in the
                    `STAGE_REGISTRY`.
        TypeError: If the output data type of one stage is incompatible with the
                   input data type of the next stage in the chain.
                   Also raised if `initial_data_type` does not match the input type
                   of the first stage.
        Exception: Any exception raised by a stage's `process` method will propagate
                   up, unless caught and handled within the stage itself.
    """
    if not chain_definition:
        logger.info("Stage chain definition is empty. Returning initial data.")
        return initial_data

    current_data = initial_data
    current_data_type = initial_data_type

    if context is None:
        context = {} # Ensure context is always a dict

    logger.info(
        "Starting stage chain execution. Initial data type: '%s'. Context keys: %s",
        current_data_type, list(context.keys())
    )

    for i, stage_info in enumerate(chain_definition):
        stage_name = stage_info.get("stage_name")
        if not stage_name:
            # Using %s for stage_info to avoid issues if it contains problematic characters for f-string
            raise ValueError("Missing 'stage_name' in chain definition at index %d: %s" % (i, stage_info))

        stage_class_from_registry = STAGE_REGISTRY.get(stage_name)
        if not stage_class_from_registry:
            available_stages_str = ", ".join(STAGE_REGISTRY.keys())
            # Constructing error message separately to keep f-string use minimal if not strictly needed
            error_msg_val = (
                f"Stage '{stage_name}' (index {i}) not found in STAGE_REGISTRY. "
                f"Available stages: {available_stages_str}"
            )
            logger.error(error_msg_val)
            raise ValueError(error_msg_val)

        try:
            stage_instance = stage_class_from_registry()
        except Exception as e: # Broad exception during instantiation
            logger.error(
                "Error instantiating stage '%s' (index %d): %s",
                stage_name, i, e, exc_info=True
            )
            raise RuntimeError(f"Could not instantiate stage '{stage_name}': {e}") from e

        logger.info(
            "Executing stage %d/%d: '%s' (%s)",
            i + 1,
            len(chain_definition),
            stage_name,
            stage_instance.description
        )

        # --- Type Validation ---
        stage_input_type = stage_instance.input_type
        if current_data_type != stage_input_type:
            # Inlining type_error_message
            # f-string for specific exception message is fine
            error_msg_type_mismatch = (
                f"Type mismatch for stage '{stage_name}' (index {i}). "
                f"Expects '{stage_input_type}', got '{current_data_type}'."
            )
            logger.error(error_msg_type_mismatch)
            raise TypeError(error_msg_type_mismatch)

        # --- Parameter Merging ---
        merged_params = stage_instance.default_params.copy()
        # Inlining user_provided_params into the update call and logger if possible,
        # or just keeping it if it makes the debug log clearer.
        # For too-many-locals, it's better to reduce.
        # user_provided_params = stage_info.get("params", {}) # Original
        # if user_provided_params: # Check if dict is not empty
        # merged_params.update(user_provided_params)
        # logger.debug(...)
        # Simplified:
        current_stage_user_params = stage_info.get("params")
        if current_stage_user_params: # if params were provided and not None
            merged_params.update(current_stage_user_params)

        logger.debug(
            "Stage '%s' (index %d) - Defaults: %s, User: %s, Merged: %s",
            stage_name, i, stage_instance.default_params, current_stage_user_params or {}, merged_params
        )

        # --- Execute Stage ---
        try:
            current_data = stage_instance.process(current_data, merged_params, context) # Reassign current_data
            logger.info(
                "Stage '%s' (index %d) completed. Output type: '%s'.",
                stage_name, i, stage_instance.output_type
            )
        except Exception as e: # Broad exception from stage.process
            logger.error(
                "Error processing stage '%s' (index %d): %s",
                stage_name, i, e, exc_info=True
            )
            # Re-raise a new RuntimeError wrapping the original error for context.
            # Using f-string for error detail is fine here as it's an exception message.
            raise RuntimeError(f"Processing failed in stage '{stage_name}': {str(e)}") from e

        # Update data type for the next iteration
        # current_data is already updated by reassignment.
        current_data_type = stage_instance.output_type

    logger.info("Stage chain execution completed successfully.")
    return current_data


if __name__ == "__main__":
    # This section is for demonstration and basic testing of the runner.
    # It requires concrete AudioProcessingStage implementations to be
    # registered.

    # Example stages need these, but stage_runner.py itself does not directly use them.
    from src.core.processing_stages import DATA_TYPE_FILE_PATH, DATA_TYPE_AUDIO_BUFFER_MONO
    # DATA_TYPE_LIST_OF_FILE_PATHS was removed from main imports as unused by runner.

    # Configure basic logging for the example
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # --- Example Concrete Stage 1: File Loader ---
    class FileLoaderStage(AudioProcessingStage): # Docstring already present
        @property
        def name(self) -> str:
            return "file_loader" # No f-string needed

        @property
        def description(self) -> str:
            return "Loads an audio file path and 'simulates' loading audio data." # No f-string

        @property
        def input_type(self) -> str:
            return DATA_TYPE_FILE_PATH # No f-string

        @property
        def output_type(self) -> str:
            return DATA_TYPE_AUDIO_BUFFER_MONO

        @property
        def default_params(self) -> dict:
            return {"target_samplerate": 44100}

        def process(self, data: str, params: dict, context: dict = None):
            logger.info(
                "[%s] Processing file: %s with params: %s, context: %s",
                self.name, data, params, context
            )
            # Allow dummy for test, but check existence otherwise
            if data != "/dummy/initial_audio.wav" and not os.path.exists(data):
                raise FileNotFoundError(f"Input file not found: {data}") # f-string for error detail
            # Simulate loading
            simulated_audio_data = [0.1, 0.2, 0.3, 0.2, 0.1]
            logger.info(
                "[%s] Simulated loading. Target SR: %s",
                self.name, params.get('target_samplerate')
            )
            return simulated_audio_data

    # --- Example Concrete Stage 2: Effect Applicator ---
    class ReverbEffectStage(AudioProcessingStage): # Docstring already present
        @property
        def name(self) -> str:
            return "reverb_effect" # No f-string

        @property
        def description(self) -> str:
            return "Applies a simulated reverb effect to mono audio data." # No f-string

        @property
        def input_type(self) -> str:
            return DATA_TYPE_AUDIO_BUFFER_MONO # No f-string

        @property
        def output_type(self) -> str:
            return DATA_TYPE_AUDIO_BUFFER_MONO

        @property
        def default_params(self) -> dict:
            return {"mix": 0.5, "decay_time": 1.5}

        def process(self, data: list, params: dict, context: dict = None):
            logger.info(
                "[%s] Applying reverb. Mix: %s, Decay: %s. Input data length: %d",
                self.name, params['mix'], params['decay_time'], len(data)
            )
            # Simulate applying reverb
            reverbed_data = [val + 0.05 * params["mix"] for val in data]
            return reverbed_data

    # --- Register the example stages ---
    try:
        register_stage(FileLoaderStage)
        register_stage(ReverbEffectStage)
    except TypeError as e:
        logger.error("Error registering example stage: %s", e)
        # This might happen if AudioProcessingStage is not fully defined or imported.

    # --- Define an example chain ---
    example_chain_definition = [ # Renamed for clarity
        {"stage_name": "file_loader", "params": {"target_samplerate": 48000}},
        {"stage_name": "reverb_effect", "params": {"mix": 0.7}},
    ]

    # --- Example execution ---
    example_initial_file_path = "/dummy/initial_audio.wav" # Renamed for clarity
    # No actual file creation needed for this dummy path due to logic in FileLoaderStage example

    example_shared_context = {"project_id": 101, "user_id": "test_runner"} # Renamed

    logger.info("\n--- Starting Example Stage Chain Execution ---") # Corrected: No f-string needed
    try:
        if not STAGE_REGISTRY:
            logger.warning(
                "STAGE_REGISTRY is empty. Example stages might not have been registered."
            ) # Corrected: No f-string needed
        else:
            final_output = execute_stage_chain(
                initial_data=example_initial_file_path,
                initial_data_type=DATA_TYPE_FILE_PATH,
                chain_definition=example_chain_definition,
                context=example_shared_context,
            )
            logger.info("--- Example Stage Chain Execution Finished ---") # Corrected: No f-string needed
            logger.info("Final output of the chain: %s", final_output)
    except (ValueError, TypeError) as e_chain_err:
        logger.error("Chain execution error: %s", e_chain_err, exc_info=True)
    except Exception as e_unexpected:
        logger.error(
            "An unexpected error during chain execution: %s", e_unexpected, exc_info=True
        )

    # --- Test case: Empty chain ---
    logger.info("\n--- Testing Empty Chain ---") # Corrected: No f-string needed
    empty_chain_output = execute_stage_chain(
        example_initial_file_path, DATA_TYPE_FILE_PATH, [], example_shared_context
    )
    assert empty_chain_output == example_initial_file_path # Assertion is not an f-string
    logger.info("Empty chain output (should be initial data): %s", empty_chain_output)

    # --- Test case: Type mismatch ---
    logger.info("\n--- Testing Type Mismatch ---") # Corrected: No f-string needed
    type_mismatch_chain = [{"stage_name": "reverb_effect"}]
    try:
        execute_stage_chain(
            example_initial_file_path,
            DATA_TYPE_FILE_PATH,
            type_mismatch_chain,
            example_shared_context
        )
    except TypeError as e_type_err:
        logger.info("Successfully caught expected TypeError for mismatch: %s", e_type_err)
    except Exception as e_unexpected_type_test:
        logger.error(
            "Unexpected error during type mismatch test: %s", e_unexpected_type_test, exc_info=True
        )

    # --- Test case: Unregistered stage ---
    logger.info("\n--- Testing Unregistered Stage ---") # Corrected: No f-string needed
    unregistered_stage_chain = [{"stage_name": "non_existent_stage"}]
    try:
        execute_stage_chain(
            example_initial_file_path,
            DATA_TYPE_FILE_PATH,
            unregistered_stage_chain,
            example_shared_context
        )
    except ValueError as e_val_err:
        logger.info("Successfully caught expected ValueError for unregistered stage: %s", e_val_err)
    except Exception as e_unexpected_unreg_test:
        logger.error(
            "Unexpected error during unregistered stage test: %s",
            e_unexpected_unreg_test, exc_info=True
        )
            exc_info=True)
