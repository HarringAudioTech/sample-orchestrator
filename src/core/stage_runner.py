"""
Manages the registration and execution of audio processing stages.

This module provides:
- A global registry (`STAGE_REGISTRY`) for discovering available `AudioProcessingStage` implementations.
- A function `register_stage` to add new stage classes to the registry.
- A function `execute_stage_chain` to run a sequence of processing stages (a chain)
  on an initial piece of data.
"""

import logging
from typing import Any, Dict, List, Type, Optional
from src.core.processing_stages import (
    AudioProcessingStage,
)

# --- Logger Setup ---
logger = logging.getLogger(__name__)

# --- Stage Registry ---
STAGE_REGISTRY: Dict[str, Type[AudioProcessingStage]] = {}
"""Global dictionary to store registered audio processing stage classes.
Keys are the unique names of the stages (from `stage_class().name`),
and values are the stage classes themselves.
"""


def register_stage(stage_class: Type[AudioProcessingStage]) -> None:
    """Registers an audio processing stage class in the global `STAGE_REGISTRY`.

    To be registered, the `stage_class` must meet several criteria:
    1. It must be a subclass of `AudioProcessingStage`.
    2. It must be instantiable (e.g., all abstract methods implemented if any).
    3. An instance of the class must have a `name` property that returns a
       non-empty string. This name is used as the key in the `STAGE_REGISTRY`.

    If a stage with the same name (obtained from `stage_class().name`) already
    exists in the registry, a warning is logged, and the existing entry is
    overwritten with the new `stage_class`.

    Args:
        stage_class (Type[AudioProcessingStage]): The audio processing stage
            class to be registered. This is the class itself, not an instance.

    Raises:
        TypeError:
            - If `stage_class` is not a subclass of `AudioProcessingStage`.
            - If `stage_class` cannot be instantiated (e.g., due to missing
              implementation of abstract methods or errors in its `__init__`).
            - If the `name` property of an instance of `stage_class` is missing,
              not a string, or returns an empty string or `None`.
    """
    if not issubclass(stage_class, AudioProcessingStage):
        raise TypeError(
            f"Stage class '{stage_class.__name__}' must inherit from AudioProcessingStage."
        )

    try:
        # Instantiate the class to get the name from the property
        stage_instance_for_name = stage_class()
        stage_name = stage_instance_for_name.name
        if not stage_name or not isinstance(stage_name, str):
            raise AttributeError(  # Changed to AttributeError for clarity on value
                "Stage class's 'name' property returned an empty, None, or non-string value."
            )
    except AttributeError as e:
        raise TypeError(
            f"Stage class '{stage_class.__name__}' must have a valid 'name' property that returns a non-empty string: {e}"
        ) from e
    except (
        Exception
    ) as e:  # Catch other errors during instantiation (e.g. missing other abstract methods)
        raise TypeError(
            f"Could not instantiate stage class '{stage_class.__name__}' to get its name. This might be due to missing abstract methods or errors in __init__. Original error: {e}"
        ) from e

    if stage_name in STAGE_REGISTRY:
        logger.warning(
            f"Stage name '{stage_name}' from class '{stage_class.__name__}' "
            f"is already registered. Overwriting with new class. "
            f"Previous class: '{STAGE_REGISTRY[stage_name].__name__}'."
        )
    STAGE_REGISTRY[stage_name] = stage_class
    logger.info(
        f"Successfully registered stage: '{stage_name}' from class '{stage_class.__name__}'."
    )


# --- Stage Chain Execution ---
def execute_stage_chain(
    initial_data: Any,
    initial_data_type: str,
    chain_definition: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> Any:
    """Executes a defined chain of audio processing stages sequentially.

    This function iterates through a `chain_definition`, where each element
    specifies a stage to be executed. The output of one stage serves as the
    input for the subsequent stage. Data type compatibility between stages is
    enforced based on each stage's `input_type` and `output_type` properties.

    Each stage in the chain is defined by a dictionary containing:
    - `stage_name` (str): The name of the stage, which must be registered in
      `STAGE_REGISTRY`.
    - `params` (Optional[Dict[str, Any]]): A dictionary of parameters to
      override the stage's `default_params`.

    An optional `context` dictionary can be provided, which is passed to each
    stage's `process` method, allowing stages to share resources or state.

    Args:
        initial_data (Any): The data to be fed into the first stage of the chain.
        initial_data_type (str): A string identifier for the type of `initial_data`
            (e.g., "file_path", "audio_buffer_mono"). This must match the
            `input_type` of the first stage.
        chain_definition (List[Dict[str, Any]]): A list of dictionaries, each
            defining a stage to be executed. Each dictionary must contain
            'stage_name' and optionally 'params'.
        context (Optional[Dict[str, Any]]): A dictionary of shared resources or
            state to be passed to each stage. Defaults to an empty dictionary if None.

    Returns:
        Any: The data returned by the `process` method of the final stage in
             the chain. If the `chain_definition` is empty, `initial_data` is
             returned directly.

    Raises:
        ValueError:
            - If a stage definition in `chain_definition` is missing 'stage_name'.
            - If a specified 'stage_name' is not found in `STAGE_REGISTRY`.
        TypeError:
            - If there's a data type mismatch between the output of one stage
              (or `initial_data_type`) and the expected `input_type` of the next.
        RuntimeError: If a registered stage class cannot be instantiated.
        Exception: Propagates exceptions raised during the `process` method of
                   any stage, prefixing them with information about the failing stage.
    """
    if not chain_definition:
        logger.info("Stage chain definition is empty. Returning initial data.")
        return initial_data

    current_data = initial_data
    current_data_type = initial_data_type

    if context is None:
        context = {}

    logger.info(
        f"Starting stage chain execution. Initial data type: '{current_data_type}'. Context keys: {list(context.keys())}"
    )

    for i, stage_info in enumerate(chain_definition):
        stage_name = stage_info.get("stage_name")
        if not stage_name:
            raise ValueError(
                f"Missing 'stage_name' in chain definition at index {i}: {stage_info}"
            )

        StageClass = STAGE_REGISTRY.get(stage_name)
        if not StageClass:
            raise ValueError(
                f"Stage '{stage_name}' (index {i}) not found in STAGE_REGISTRY. "
                f"Available stages: {list(STAGE_REGISTRY.keys())}"
            )

        try:
            stage_instance = StageClass()
        except Exception as e:
            logger.error(
                f"Error instantiating stage '{stage_name}' (index {i}): {e}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Could not instantiate stage '{stage_name}': {e}"
            ) from e

        logger.info(
            f"Executing stage {i + 1}/{len(chain_definition)}: '{stage_name}' ({stage_instance.description})"
        )

        expected_input_type = stage_instance.input_type
        if current_data_type != expected_input_type:
            error_msg = (
                f"Type mismatch for stage '{stage_name}' (index {i}). "
                f"Stage expects input type '{expected_input_type}', but received '{current_data_type}' "
                f"from the previous stage or initial data."
            )
            logger.error(error_msg)
            raise TypeError(error_msg)

        merged_params = stage_instance.default_params.copy()
        user_params = stage_info.get("params", {})
        if user_params:
            merged_params.update(user_params)

        logger.debug(
            f"Stage '{stage_name}' (index {i}) - Default params: {stage_instance.default_params}, User params: {user_params}, Merged params: {merged_params}"
        )

        try:
            processed_data = stage_instance.process(
                current_data, merged_params, context
            )
            logger.info(
                f"Stage '{stage_name}' (index {i}) completed. Output type: '{stage_instance.output_type}'."
            )
        except Exception as e:
            logger.error(
                f"Error during processing of stage '{stage_name}' (index {i}): {e}",
                exc_info=True,
            )
            raise Exception(
                f"Processing failed in stage '{stage_name}' (index {i}). Original error: {e}"
            ) from e

        current_data = processed_data
        current_data_type = stage_instance.output_type

    logger.info("Stage chain execution completed successfully.")
    return current_data


if __name__ == "__main__":
    from src.core.processing_stages import (
        DATA_TYPE_FILE_PATH,
        DATA_TYPE_AUDIO_BUFFER_MONO,
    )
    import os  # Required for os.path.exists in FileLoaderStage example

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    class FileLoaderStage(AudioProcessingStage):
        @property
        def name(self) -> str:
            return "file_loader"

        @property
        def description(self) -> str:
            return "Loads an audio file path and 'simulates' loading audio data."

        @property
        def input_type(self) -> str:
            return DATA_TYPE_FILE_PATH

        @property
        def output_type(self) -> str:
            return DATA_TYPE_AUDIO_BUFFER_MONO

        @property
        def default_params(self) -> Dict[str, Any]:
            return {"target_samplerate": 44100}

        def process(
            self,
            data: str,
            params: Dict[str, Any],
            context: Optional[Dict[str, Any]] = None,
        ) -> List[float]:
            logger.info(
                f"[{self.name}] Processing file: {data} with params: {params}, context: {context}"
            )
            if not os.path.exists(data) and data != "/dummy/initial_audio.wav":
                raise FileNotFoundError(f"Input file not found: {data}")
            simulated_audio_data: List[float] = [0.1, 0.2, 0.3, 0.2, 0.1]
            logger.info(
                f"[{self.name}] Simulated loading audio data. Target SR: {params.get('target_samplerate')}"
            )
            return simulated_audio_data

    class ReverbEffectStage(AudioProcessingStage):
        @property
        def name(self) -> str:
            return "reverb_effect"

        @property
        def description(self) -> str:
            return "Applies a simulated reverb effect to mono audio data."

        @property
        def input_type(self) -> str:
            return DATA_TYPE_AUDIO_BUFFER_MONO

        @property
        def output_type(self) -> str:
            return DATA_TYPE_AUDIO_BUFFER_MONO

        @property
        def default_params(self) -> Dict[str, Any]:
            return {"mix": 0.5, "decay_time": 1.5}

        def process(
            self,
            data: List[float],
            params: Dict[str, Any],
            context: Optional[Dict[str, Any]] = None,
        ) -> List[float]:
            logger.info(
                f"[{self.name}] Applying reverb. Mix: {params['mix']}, Decay: {params['decay_time']}. Input data length: {len(data)}"
            )
            reverbed_data: List[float] = [val + 0.05 * params["mix"] for val in data]
            return reverbed_data

    try:
        register_stage(FileLoaderStage)
        register_stage(ReverbEffectStage)
    except TypeError as e:
        logger.error(f"Error registering example stage: {e}")

    example_chain = [
        {"stage_name": "file_loader", "params": {"target_samplerate": 48000}},
        {"stage_name": "reverb_effect", "params": {"mix": 0.7}},
    ]
    initial_file_path = "/dummy/initial_audio.wav"
    shared_context = {"project_id": 101, "user_id": "test_runner"}

    logger.info("\n--- Starting Example Stage Chain Execution ---")
    try:
        if not STAGE_REGISTRY:
            logger.warning("STAGE_REGISTRY is empty.")
        else:
            final_output = execute_stage_chain(
                initial_file_path, DATA_TYPE_FILE_PATH, example_chain, shared_context
            )
            logger.info(f"--- Example Stage Chain Execution Finished ---")
            logger.info(f"Final output of the chain: {final_output}")
    except (ValueError, TypeError) as e:
        logger.error(f"Chain execution error: {e}", exc_info=True)
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during chain execution: {e}", exc_info=True
        )
