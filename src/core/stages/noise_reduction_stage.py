"""
Defines the NoiseReductionStage for audio processing pipelines.
This stage serves as a placeholder for a noise reduction algorithm.
"""

import logging
import numpy as np  # For potential audio buffer manipulation
from typing import Any, Dict, Optional

from src.core.processing_stages import AudioProcessingStage, DATA_TYPE_AUDIO_BUFFER_MONO
from src.core.stage_runner import register_stage

# Logger for this stage
logger = logging.getLogger(__name__)


class NoiseReductionStage(AudioProcessingStage):
    """
    A basic audio processing stage for noise reduction using a noise gate.
    """

    @property
    def name(self) -> str:
        return "noise_reduction"

    @property
    def description(self) -> str:
        return "Basic noise gate: zeroes out audio below a certain threshold."

    @property
    def input_type(self) -> str:
        return DATA_TYPE_AUDIO_BUFFER_MONO

    @property
    def output_type(self) -> str:
        return DATA_TYPE_AUDIO_BUFFER_MONO

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "amount": 1.0,  # 0.0 to 1.0, where 1.0 is full silence for gated regions
            "threshold_db": -60.0,  # Manual threshold if auto fails or if preferred
            "auto_threshold": True,
            "attack_ms": 5.0,
            "release_ms": 20.0,
        }

    def process(
        self,
        data: np.ndarray,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Applies a noise gate to the audio data.

        Args:
            data: The input mono audio buffer (NumPy array).
            params: Parameters for the noise gate.
            context: Optional context.

        Returns:
            The gated audio buffer.
        """
        if not isinstance(data, np.ndarray):
            logger.error(f"[{self.name}] Input data is not a NumPy array, but type: {type(data)}")
            raise TypeError(f"Input data for {self.name} must be a NumPy array.")

        if len(data) == 0:
            return data

        # Merge parameters
        merged_params = self.default_params.copy()
        merged_params.update(params)
        
        threshold_db = merged_params["threshold_db"]
        amount = merged_params["amount"]
        
        # Simple auto-threshold if enabled: check the first 50ms for noise floor
        if merged_params["auto_threshold"]:
            sr = 44100 # Default assumption if not in context
            if context and "sample_rate" in context:
                sr = context["sample_rate"]
            
            noise_sample_len = int(0.05 * sr)
            if len(data) > noise_sample_len:
                noise_segment = data[:noise_sample_len]
                rms_noise = np.sqrt(np.mean(noise_segment**2))
                if rms_noise > 0:
                    auto_db = 20 * np.log10(rms_noise) + 6 # Add 6dB buffer
                    threshold_db = max(threshold_db, auto_db)

        threshold_linear = 10 ** (threshold_db / 20)
        
        logger.info(f"[{self.name}] Applying noise gate with threshold {threshold_db:.1f} dB")

        # Basic hard gate: if absolute value is below threshold, multiply by (1-amount)
        # In a real gate we'd use an envelope follower and smoothing, 
        # but this is a solid upgrade from "2% attenuation".
        mask = np.abs(data) < threshold_linear
        processed_data = data.copy()
        processed_data[mask] *= (1.0 - amount)

        return processed_data


# Register the stage when this module is imported
try:
    register_stage(NoiseReductionStage)
except Exception as e:
    logger.critical(f"Failed to register NoiseReductionStage: {e}", exc_info=True)
