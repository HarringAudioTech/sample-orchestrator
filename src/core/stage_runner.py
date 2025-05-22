"""
Manages the registration and execution of audio processing stages.

This module provides:
- A global registry (`STAGE_REGISTRY`) for discovering available `AudioProcessingStage` implementations.
- A function `register_stage` to add new stage classes to the registry.
- A function `execute_stage_chain` to run a sequence of processing stages (a chain)
  on an initial piece of data.
"""

import logging
from typing import Any, Dict, List, Type
from src.core.processing_stages import AudioProcessingStage # DATA_TYPE_* constants are not directly needed here but by stages

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
        raise TypeError(f"Stage class '{stage_class.__name__}' must inherit from AudioProcessingStage.")
    
    try:
        stage_name = stage_class.name
        if not isinstance(stage_name, str) or not stage_name:
            # This check is somewhat redundant if stage_class.name is an abstractproperty
            # that must return str, but good for safety if a class doesn't implement it correctly.
            raise AttributeError("Stage class must have a valid 'name' property (non-empty string).")
    except AttributeError: # Should ideally be caught by issubclass if name is an abstractproperty
        raise TypeError(f"Stage class '{stage_class.__name__}' must have a 'name' property.")


    if stage_name in STAGE_REGISTRY:
        logger.warning(
            f"Stage name '{stage_name}' from class '{stage_class.__name__}' "
            f"is already registered. Overwriting with new class. "
            f"Previous class: '{STAGE_REGISTRY[stage_name].__name__}'."
        )
    STAGE_REGISTRY[stage_name] = stage_class
    logger.info(f"Successfully registered stage: '{stage_name}' from class '{stage_class.__name__}'.")


# --- Stage Chain Execution ---
def execute_stage_chain(
    initial_data: Any,
    initial_data_type: str,
    chain_definition: List[Dict[str, Any]],
    context: Dict[str, Any] = None
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
        context = {}

    logger.info(f"Starting stage chain execution. Initial data type: '{current_data_type}'. Context keys: {list(context.keys())}")

    for i, stage_info in enumerate(chain_definition):
        stage_name = stage_info.get("stage_name")
        if not stage_name:
            raise ValueError(f"Missing 'stage_name' in chain definition at index {i}: {stage_info}")

        StageClass = STAGE_REGISTRY.get(stage_name)
        if not StageClass:
            raise ValueError(
                f"Stage '{stage_name}' (index {i}) not found in STAGE_REGISTRY. "
                f"Available stages: {list(STAGE_REGISTRY.keys())}"
            )

        try:
            stage_instance = StageClass()
        except Exception as e:
            logger.error(f"Error instantiating stage '{stage_name}' (index {i}): {e}", exc_info=True)
            raise RuntimeError(f"Could not instantiate stage '{stage_name}': {e}") from e
            
        logger.info(f"Executing stage {i+1}/{len(chain_definition)}: '{stage_name}' ({stage_instance.description})")

        # --- Type Validation ---
        expected_input_type = stage_instance.input_type
        if current_data_type != expected_input_type:
            error_msg = (
                f"Type mismatch for stage '{stage_name}' (index {i}). "
                f"Stage expects input type '{expected_input_type}', but received '{current_data_type}' "
                f"from the previous stage or initial data."
            )
            logger.error(error_msg)
            raise TypeError(error_msg)

        # --- Parameter Merging ---
        # Start with stage's defaults, then override with user-provided params for this run.
        merged_params = stage_instance.default_params.copy()
        user_params = stage_info.get("params", {})
        if user_params: # Only update if user_params is not None or empty
            merged_params.update(user_params)
        
        logger.debug(f"Stage '{stage_name}' (index {i}) - Default params: {stage_instance.default_params}, User params: {user_params}, Merged params: {merged_params}")

        # --- Execute Stage ---
        try:
            processed_data = stage_instance.process(current_data, merged_params, context)
            logger.info(f"Stage '{stage_name}' (index {i}) completed. Output type: '{stage_instance.output_type}'.")
        except Exception as e:
            logger.error(f"Error during processing of stage '{stage_name}' (index {i}): {e}", exc_info=True)
            # Depending on desired behavior, you might want to re-raise, or handle and stop,
            # or even try to continue if some errors are recoverable. Here, we re-raise.
            raise Exception(f"Processing failed in stage '{stage_name}' (index {i}). Original error: {e}") from e

        # Update data and type for the next iteration
        current_data = processed_data
        current_data_type = stage_instance.output_type

    logger.info("Stage chain execution completed successfully.")
    return current_data


if __name__ == '__main__':
    # This section is for demonstration and basic testing of the runner.
    # It requires concrete AudioProcessingStage implementations to be registered.

    from src.core.processing_stages import (
        DATA_TYPE_FILE_PATH, DATA_TYPE_LIST_OF_FILE_PATHS, DATA_TYPE_AUDIO_BUFFER_MONO
    )
    
    # Configure basic logging for the example
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Example Concrete Stage 1: File Loader ---
    class FileLoaderStage(AudioProcessingStage):
        @property
        def name(self) -> str: return "file_loader"
        @property
        def description(self) -> str: return "Loads an audio file path and 'simulates' loading audio data."
        @property
        def input_type(self) -> str: return DATA_TYPE_FILE_PATH
        @property
        def output_type(self) -> str: return DATA_TYPE_AUDIO_BUFFER_MONO # Simulates outputting audio data
        @property
        def default_params(self) -> dict: return {"target_samplerate": 44100}

        def process(self, data: str, params: dict, context: dict = None):
            logger.info(f"[{self.name}] Processing file: {data} with params: {params}, context: {context}")
            if not os.path.exists(data) and data != "/dummy/initial_audio.wav": # Allow dummy for test
                 raise FileNotFoundError(f"Input file not found: {data}")
            # Simulate loading and returning a mono audio buffer (e.g., a NumPy array)
            simulated_audio_data = [0.1, 0.2, 0.3, 0.2, 0.1] # Placeholder
            logger.info(f"[{self.name}] Simulated loading audio data. Target SR: {params.get('target_samplerate')}")
            return simulated_audio_data

    # --- Example Concrete Stage 2: Effect Applicator ---
    class ReverbEffectStage(AudioProcessingStage):
        @property
        def name(self) -> str: return "reverb_effect"
        @property
        def description(self) -> str: return "Applies a simulated reverb effect to mono audio data."
        @property
        def input_type(self) -> str: return DATA_TYPE_AUDIO_BUFFER_MONO
        @property
        def output_type(self) -> str: return DATA_TYPE_AUDIO_BUFFER_MONO # Output is still mono audio
        @property
        def default_params(self) -> dict: return {"mix": 0.5, "decay_time": 1.5}

        def process(self, data: list, params: dict, context: dict = None): # data is list for this example
            logger.info(f"[{self.name}] Applying reverb. Mix: {params['mix']}, Decay: {params['decay_time']}. Input data length: {len(data)}")
            # Simulate applying reverb (e.g., add some values)
            reverbed_data = [val + 0.05 * params['mix'] for val in data]
            return reverbed_data

    # --- Register the example stages ---
    try:
        register_stage(FileLoaderStage)
        register_stage(ReverbEffectStage)
    except TypeError as e:
        logger.error(f"Error registering example stage: {e}")
        # This might happen if AudioProcessingStage is not fully defined or imported yet
        # when this __main__ block runs directly without full package context.

    # --- Define an example chain ---
    example_chain = [
        {
            "stage_name": "file_loader",
            "params": {"target_samplerate": 48000} # Override default
        },
        {
            "stage_name": "reverb_effect",
            "params": {"mix": 0.7} # Override default
        }
        # Add more stages here if needed
    ]

    # --- Example execution ---
    initial_file_path = "/dummy/initial_audio.wav" # A dummy path for the example
    # Create the dummy file for the FileLoaderStage to "succeed"
    # In a real scenario, this file would exist.
    # For this test, we'll skip actual file creation and rely on the check in FileLoaderStage.

    shared_context = {"project_id": 101, "user_id": "test_runner"}

    logger.info("\n--- Starting Example Stage Chain Execution ---")
    try:
        if not STAGE_REGISTRY:
             logger.warning("STAGE_REGISTRY is empty. Example stages might not have been registered if run directly without full package context or if AudioProcessingStage was not fully defined.")
        else:
            final_output = execute_stage_chain(
                initial_data=initial_file_path,
                initial_data_type=DATA_TYPE_FILE_PATH,
                chain_definition=example_chain,
                context=shared_context
            )
            logger.info(f"--- Example Stage Chain Execution Finished ---")
            logger.info(f"Final output of the chain: {final_output}")
    except (ValueError, TypeError) as e:
        logger.error(f"Chain execution error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during chain execution: {e}", exc_info=True)

    # --- Test case: Empty chain ---
    logger.info("\n--- Testing Empty Chain ---")
    empty_chain_output = execute_stage_chain(initial_file_path, DATA_TYPE_FILE_PATH, [], shared_context)
    assert empty_chain_output == initial_file_path
    logger.info(f"Empty chain output (should be initial data): {empty_chain_output}")

    # --- Test case: Type mismatch ---
    logger.info("\n--- Testing Type Mismatch ---")
    mismatch_chain = [{"stage_name": "reverb_effect"}] # Reverb expects audio buffer, not file path
    try:
        execute_stage_chain(initial_file_path, DATA_TYPE_FILE_PATH, mismatch_chain, shared_context)
    except TypeError as e:
        logger.info(f"Successfully caught expected TypeError for mismatch: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during type mismatch test: {e}", exc_info=True)


    # --- Test case: Unregistered stage ---
    logger.info("\n--- Testing Unregistered Stage ---")
    unregistered_chain = [{"stage_name": "non_existent_stage"}]
    try:
        execute_stage_chain(initial_file_path, DATA_TYPE_FILE_PATH, unregistered_chain, shared_context)
    except ValueError as e:
        logger.info(f"Successfully caught expected ValueError for unregistered stage: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during unregistered stage test: {e}", exc_info=True)
```
