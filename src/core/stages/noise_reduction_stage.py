"""
Defines the NoiseReductionStage for audio processing pipelines.
This stage serves as a placeholder for a noise reduction algorithm.
"""

import logging
import numpy as np  # For potential audio buffer manipulation
from typing import Any, Dict, Optional
import noisereduce

from src.core.processing_stages import AudioProcessingStage, DATA_TYPE_AUDIO_BUFFER_MONO
from src.core.stage_runner import register_stage

# Logger for this stage
logger = logging.getLogger(__name__)


class NoiseReductionStage(AudioProcessingStage):
    """
    A placeholder audio processing stage for noise reduction.

    This stage currently logs its parameters and passes the audio data through
    with a trivial modification (slight attenuation). It demonstrates the structure
    of a processing stage that operates on audio buffers.
    """

    @property
    def name(self) -> str:
        return "noise_reduction"

    @property
    def description(self) -> str:
        return "Placeholder for a noise reduction algorithm. Currently logs parameters and slightly attenuates data."

    @property
    def input_type(self) -> str:
        return DATA_TYPE_AUDIO_BUFFER_MONO

    @property
    def output_type(self) -> str:
        return DATA_TYPE_AUDIO_BUFFER_MONO

    @property
    def default_params(self) -> Dict[str, Any]:
        # These parameters are not directly used by noisereduce.reduce_noise in its basic form.
        # They are kept here for potential future use or more advanced configuration.
        return {
            "amount": 0.5,  # Example: could map to 'prop_decrease' or similar if supported
            "aggressiveness": 3,  # Example: could influence other parameters of noisereduce
        }

    def process(
        self,
        data: np.ndarray,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Applies a placeholder noise reduction effect to the audio data.

        Args:
            data: The input mono audio buffer (NumPy array).
            params: Parameters for noise reduction, merged with defaults.
            context: Shared context dictionary, expected to contain 'sample_rate'.

        Returns:
            The processed mono audio buffer (NumPy array).

        Raises:
            TypeError: If the input data is not a NumPy array.
        """
        if not isinstance(data, np.ndarray):
            # This check is good practice, though the stage runner might also do type validation
            # based on DATA_TYPE_AUDIO_BUFFER_MONO if it were more specific
            # (e.g. checking for np.ndarray).
            logger.error(
                f"[{self.name}] Input data is not a NumPy array, but type: {type(data)}"
            )
            raise TypeError(f"Input data for {self.name} must be a NumPy array.")

        if context is None or "sample_rate" not in context:
            logger.warning(
                f"[{self.name}] 'sample_rate' not found in context. "
                "Noise reduction might not be effective or may raise an error. "
                "Proceeding with a default of 0, which is likely incorrect."
            )
            sample_rate = (
                0  # This is likely to cause issues but handles missing key for now
            )
        else:
            sample_rate = context["sample_rate"]

        # Log parameters, including sample rate from context
        logger.info(
            f"[{self.name}] Applying noise reduction... "
            f"Input data shape: {data.shape}, dtype: {data.dtype}. "
            f"Sample rate: {sample_rate}. "
            f"Using parameters: {params} (Note: basic noisereduce call doesn't use them directly)."
            f"Context keys: {list(context.keys()) if context else 'None'}."
        )

        # Perform noise reduction
        # Note: The 'params' from this stage (amount, aggressiveness) are not directly
        # used in the basic noisereduce.reduce_noise call here.
        # For more advanced usage, these could be mapped to specific arguments
        # of reduce_noise if applicable (e.g., prop_decrease, n_fft, etc.).
        try:
            reduced_noise_data = noisereduce.reduce_noise(y=data, sr=sample_rate)
            logger.info(f"[{self.name}] Noise reduction applied successfully.")
            return reduced_noise_data
        except Exception as e:
            logger.error(
                f"[{self.name}] Error during noise reduction: {e}", exc_info=True
            )
            # Depending on desired behavior, either re-raise or return original data
            # For now, returning original data to allow pipeline to continue if possible
            return data


# Register the stage when this module is imported
try:
    register_stage(NoiseReductionStage)
except Exception as e:
    logger.critical(f"Failed to register NoiseReductionStage: {e}", exc_info=True)
