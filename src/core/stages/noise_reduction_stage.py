"""
Defines the NoiseReductionStage for audio processing pipelines.
This stage loads an audio file, applies placeholder noise reduction,
and saves the result to a new file.
"""

import logging
import numpy as np
import librosa  # For audio loading
import soundfile as sf  # For audio writing
import os  # For path manipulation
from typing import Any, Dict, Optional

# Changed import to DATA_TYPE_FILE_PATH
from src.core.processing_stages import AudioProcessingStage, DATA_TYPE_FILE_PATH
from src.core.stage_runner import register_stage

# Logger for this stage
logger = logging.getLogger(__name__)


class NoiseReductionStage(AudioProcessingStage):
    """
    Loads an audio file, applies placeholder noise reduction, and saves it to a new file.
    """

    @property
    def name(self) -> str:
        return "noise_reduction"

    @property
    def description(self) -> str:
        # Updated description
        return "Loads an audio file, applies placeholder noise reduction, and saves it to a new file."

    @property
    def input_type(self) -> str:
        return DATA_TYPE_FILE_PATH  # Changed

    @property
    def output_type(self) -> str:
        return DATA_TYPE_FILE_PATH  # Changed

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "amount": 0.5,  # 0.0 to 1.0, how much reduction to apply (placeholder use)
            "aggressiveness": 3,  # 1 to 5, how aggressively to target noise (placeholder use)
        }

    def process(
        self,
        data: str,  # Changed: data is now input_file_path
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:  # Changed: returns output_file_path
        input_file_path = data  # Rename for clarity

        if not os.path.exists(input_file_path):
            logger.error(f"[{self.name}] Input audio file not found: {input_file_path}")
            raise FileNotFoundError(f"Input audio file not found: {input_file_path}")

        amount = params.get("amount", self.default_params["amount"])
        aggressiveness = params.get("aggressiveness", self.default_params["aggressiveness"])

        logger.info(
            f"[{self.name}] Applying noise reduction. Input file: {input_file_path}. "
            f"Parameters: amount={amount}, aggressiveness={aggressiveness}. "
            f"Context keys: {list(context.keys()) if context else 'None'}."
        )

        try:
            # Load audio using librosa
            y, sr = librosa.load(input_file_path, sr=None, mono=True)
            logger.info(f"[{self.name}] Loaded audio from {input_file_path}. Duration: {len(y)/sr:.2f}s, SR: {sr} Hz.")
        except Exception as e:
            logger.error(f"[{self.name}] Error loading audio file {input_file_path}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to load audio file {input_file_path}") from e

        # Placeholder noise reduction logic (actual algorithm would go here)
        # For demonstration, we'll just attenuate the signal slightly.
        # The 'amount' and 'aggressiveness' parameters could be used by a real algorithm.
        processed_data = y * 0.98  # Slight attenuation

        # Determine output path
        # Use a dedicated subdirectory within the workflow's output_sample_dir from context
        if context and 'output_sample_dir' in context:
            base_output_dir = context['output_sample_dir']
        else:
            # Fallback if context or output_sample_dir is missing, though it shouldn't be for this workflow
            logger.warning(
                f"[{self.name}] 'output_sample_dir' not found in context. "
                f"Saving to a subdirectory in the input file's directory: {os.path.dirname(input_file_path)}."
            )
            base_output_dir = os.path.dirname(input_file_path)

        # Define a subdirectory for intermediate files from this stage
        intermediate_files_dir = os.path.join(base_output_dir, "intermediate_noise_reduction")

        try:
            os.makedirs(intermediate_files_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"[{self.name}] Error creating intermediate directory {intermediate_files_dir}: {e}", exc_info=True)
            raise RuntimeError(f"Could not create intermediate directory: {intermediate_files_dir}") from e


        original_filename = os.path.basename(input_file_path)
        # Construct a new filename for the processed audio, e.g., append "_nr"
        processed_filename = os.path.splitext(original_filename)[0] + "_nr.wav"
        output_file_path = os.path.join(intermediate_files_dir, processed_filename)

        try:
            # Save processed audio using soundfile
            sf.write(output_file_path, processed_data, sr)
            logger.info(f"[{self.name}] Processed audio saved to: {output_file_path}")
        except Exception as e:
            logger.error(f"[{self.name}] Error saving processed audio to {output_file_path}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to save processed audio to {output_file_path}") from e

        return output_file_path


# Register the stage when this module is imported
try:
    register_stage(NoiseReductionStage)
except Exception as e:
    # Log critical error if registration fails, as it might prevent app startup or workflow execution
    logger.critical(f"Failed to register NoiseReductionStage: {e}", exc_info=True)
