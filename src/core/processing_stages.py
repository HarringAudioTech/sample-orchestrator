"""
Defines the building blocks for customizable audio processing pipelines.

This module includes:
- String constants for common data types used in processing stages.
- An abstract base class `AudioProcessingStage` that defines the interface
  for all audio processing stages.
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List

# --- Data Type Constants ---
# These constants define the expected types of data that can be passed
# between audio processing stages.

DATA_TYPE_AUDIO_BUFFER_MONO = "audio_buffer_mono"
"""Represents a mono audio buffer, typically a 1D NumPy array of audio samples."""

DATA_TYPE_AUDIO_BUFFER_STEREO = "audio_buffer_stereo"
"""Represents a stereo audio buffer, typically a 2D NumPy array (channels x samples)."""

DATA_TYPE_FILE_PATH = "file_path"
"""Represents a string containing the absolute or relative path to an audio file."""

DATA_TYPE_LIST_OF_FILE_PATHS = "list_of_file_paths"
"""Represents a list of strings, where each string is a file path."""

DATA_TYPE_LIST_OF_SAMPLE_DATA = "list_of_sample_data"
"""
Represents a list of dictionaries or objects. Each item in the list corresponds
to a sample and contains its metadata (e.g., start time, end time, pitch)
and potentially its audio data (e.g., as an audio buffer or file path).
"""

# --- Abstract Base Class for Processing Stages ---


class AudioProcessingStage(ABC):
    """
    Abstract Base Class for an audio processing stage.

    Each stage in an audio processing pipeline should inherit from this class
    and implement its abstract properties and methods. This ensures a consistent
    interface for all stages, allowing them to be chained together.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        The unique name of this processing stage.

        This name is used to identify the stage in configurations and logs.
        Example: "pitch_shifter", "noise_reduction".

        Returns:
            str: The name of the stage.
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        A brief description of what this processing stage does.

        This helps users understand the purpose of the stage.
        Example: "Shifts the pitch of the audio up or down."

        Returns:
            str: A human-readable description of the stage.
        """
        pass

    @property
    @abstractmethod
    def input_type(self) -> str:
        """
        The expected type of input data for this stage.

        Must be one of the `DATA_TYPE_*` constants defined in this module.
        The `process` method will receive data conforming to this type.

        Returns:
            str: The input data type string constant.
        """
        pass

    @property
    @abstractmethod
    def output_type(self) -> str:
        """
        The type of output data this stage produces.

        Must be one of the `DATA_TYPE_*` constants defined in this module.
        The `process` method should return data conforming to this type.

        Returns:
            str: The output data type string constant.
        """
        pass

    @property
    @abstractmethod
    def default_params(self) -> Dict[str, Any]:
        """A dictionary defining the default parameters for this stage.

        These parameters can be overridden when a stage instance is configured
        within a pipeline. If a stage requires no parameters, it should
        return an empty dictionary.

        Example: `{"semitones": 0, "quality": "high"}`

        Returns:
            dict: A dictionary of default parameter names and their values.
        """
        pass

    @abstractmethod
    def process(
        self,
        data: Any,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Processes the input data according to the stage's logic and parameters.

        This is the core method of the processing stage where the actual audio
        manipulation or analysis occurs.

        Args:
            data: The input data to be processed. The type of this data is
                  defined by the `input_type` property of the stage.
            params (dict): A dictionary of parameters for this specific execution
                           of the stage. These parameters are typically a merge of
                           the stage's `default_params` and any user-provided
                           overrides from a pipeline configuration.
            context (dict, optional): An optional dictionary for passing shared
                                      resources or information between stages or
                                      from the pipeline runner. This could include
                                      things like a database session, project ID,
                                      recording ID, temporary working directories, etc.
                                      Defaults to None.

        Returns:
            The processed data. The type of this data is defined by the
            `output_type` property of the stage.

        Raises:
            NotImplementedError: If the concrete stage does not implement this method.
            Exception: Concrete implementations may raise various exceptions based
                       on processing errors (e.g., FileNotFoundError, processing errors).
        """
        pass


if __name__ == "__main__":
    # Example of how a concrete stage might be defined (for illustration
    # purposes):

    class ExampleFilePathProcessor(AudioProcessingStage):
        @property
        def name(self) -> str:
            return "example_file_processor"

        @property
        def description(self) -> str:
            return "Processes a single audio file path and returns a list of paths."

        @property
        def input_type(self) -> str:
            return DATA_TYPE_FILE_PATH

        @property
        def output_type(self) -> str:
            return DATA_TYPE_LIST_OF_FILE_PATHS

        @property
        def default_params(self) -> Dict[str, Any]:
            return {"prefix": "processed_"}

        def process(
            self,
            data: str,
            params: Dict[str, Any],
            context: Optional[Dict[str, Any]] = None,
        ) -> List[str]:
            # In a real scenario, 'data' would be a file path (string).
            # This example just demonstrates parameter usage.
            print(
                f"Processing file: {data} with params: {params} and context: {context}"
            )
            output_filename: str = params.get("prefix", "") + data.split("/")[-1]

            # Simulate creating a new file path or list of paths
            processed_path: str = f"/tmp/{output_filename}"
            print(f"Simulated output path: {processed_path}")
            return [processed_path]
            # return None # Original example returned None, changing to List[str] to match output_type

    # Instantiate and use the example processor
    # This part would typically be handled by a pipeline runner.
    if False:  # Disabled for direct execution, just for illustration
        stage = ExampleFilePathProcessor()
        print(f"Stage: {stage.name}, Description: {stage.description}")
        print(f"Input type: {stage.input_type}, Output type: {stage.output_type}")
        print(f"Default params: {stage.default_params}")

        # Simulate processing
        input_data = "/path/to/my/audiofile.wav"
        # Parameters for this specific run (could merge with defaults)
        run_params: Dict[str, Any] = stage.default_params.copy()
        run_params["prefix"] = "enhanced_"

        run_context: Dict[str, Any] = {"project_id": 123, "user_id": "test_user"}

        output_data: List[str] = stage.process(
            input_data, params=run_params, context=run_context
        )
        print(f"Processed output: {output_data}")

    print("AudioProcessingStage and data type constants defined.")
    print(
        f"Available data types: {DATA_TYPE_AUDIO_BUFFER_MONO}, {DATA_TYPE_AUDIO_BUFFER_STEREO}, {DATA_TYPE_FILE_PATH}, {DATA_TYPE_LIST_OF_FILE_PATHS}, {DATA_TYPE_LIST_OF_SAMPLE_DATA}"
    )
