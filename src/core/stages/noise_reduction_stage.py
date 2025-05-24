"""
Defines the NoiseReductionStage for audio processing pipelines.
This stage serves as a placeholder for a noise reduction algorithm.
"""

import logging
import numpy as np  # For potential audio buffer manipulation
from typing import Any, Dict

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
    def default_params(self) -> dict:
        return {
            "amount": 0.5,  # 0.0 to 1.0, how much reduction to apply
            "aggressiveness": 3,  # 1 to 5, how aggressively to target noise
        }

    def process(
        self, data: np.ndarray, params: dict, context: dict = None
    ) -> np.ndarray:
        """
        Applies a placeholder noise reduction effect to the audio data.

        Args:
            data (np.ndarray): The input mono audio buffer (NumPy array).
            params (dict): Parameters for noise reduction, merged with defaults.
                           Expected keys: "amount", "aggressiveness".
            context (dict, optional): Shared context dictionary (not used by this placeholder).

        Returns:
            np.ndarray: The processed mono audio buffer (NumPy array), slightly attenuated.

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
            raise TypeError(
                f"Input data for {self.name} must be a NumPy array.")

        amount = params.get("amount", self.default_params["amount"])
        aggressiveness = params.get(
            "aggressiveness", self.default_params["aggressiveness"]
        )

        logger.info(
            f"[{self.name}] Applying noise reduction (placeholder)... "
            f"Parameters: amount={amount}, aggressiveness={aggressiveness}. "
            f"Input data shape: {data.shape}, dtype: {data.dtype}. "
            f"Context keys: {list(context.keys()) if context else 'None'}."
        )

        # Placeholder logic: slightly attenuate the signal to simulate some processing.
        # A real implementation would use a noise reduction algorithm (e.g.,
        # spectral gating).
        processed_data = data * 0.98  # Apply a 2% attenuation as a placeholder effect

        logger.info(f"[{self.name}] Placeholder noise reduction applied.")
        return processed_data


# Register the stage when this module is imported
try:
    register_stage(NoiseReductionStage)
except Exception as e:
    logger.critical(
        f"Failed to register NoiseReductionStage: {e}", exc_info=True)
