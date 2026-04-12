"""
Defines processing stages for the vocal chop perfection workflow.

Each stage takes an audio file and an evaluation result, performs a specific
modification or analysis, and outputs a (potentially modified) audio file path.
The workflow orchestrates these stages.
"""
import os
import shutil
import abc  # Abstract Base Class
import logging # Added logging
from typing import Tuple, Optional, List, Type, Dict, Any
import dataclasses

import soundfile  # type: ignore # pylint: disable=import-error
import numpy as np  # type: ignore # pylint: disable=import-error
import librosa  # type: ignore # pylint: disable=import-error

from src.core.stage_runner import execute_stage_chain
import src.core.stages.vst3_plugin_stage # Ensure registered

# Assuming these are in the parent directory or src/core
# Adjust imports based on actual project structure if these files are elsewhere.
# pylint: disable=import-error
try:
    from src.core.vocal_chop_evaluator import (
        VocalChopEvaluationResult,
        AnalyzedVocalStab,
        VocalChopIdealCharacteristics
    )
    from src.utils import soundfile_utils
except ImportError:
    # Fallback for cases where the script might be run directly or structure is different
    # This is primarily for development; a real project would have a fixed structure.
    from core.vocal_chop_evaluator import ( # type: ignore
        VocalChopEvaluationResult,
        AnalyzedVocalStab,
        VocalChopIdealCharacteristics
    )
    from utils import soundfile_utils # type: ignore
# pylint: enable=import-error


# pylint: disable=too-few-public-methods # Acceptable for this base class
class ProcessingStage(abc.ABC):
    """Abstract base class for a processing stage in the vocal chop perfection workflow."""

    def __init__(self, working_dir: str, stage_name: Optional[str] = None, config: Optional[dict] = None):
        self.working_dir = working_dir
        self.stage_name = stage_name if stage_name else self.__class__.__name__
        self.config = config or {}
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir, exist_ok=True)

    def _save_intermediate(
        self, audio_data: np.ndarray, sr: int, original_file_path: str, suffix: str
    ) -> str:
        """
        Saves an intermediate audio file to the working directory.
        Filename will be original_basename.suffix.wav
        """
        original_filename = os.path.basename(original_file_path)
        base, _ = os.path.splitext(original_filename)
        # Remove common previous suffixes to avoid original.stage1.stage2.wav
        common_suffixes = [
            "_denoised",
            "_click_removed",
            "_adjusted",
            "_meta_updated",
            "_perfected",
        ]
        for s in common_suffixes:
            if base.endswith(s):
                base = base[: -len(s)]

        new_filename = f"{base}_{suffix}.wav"
        output_path = os.path.join(self.working_dir, new_filename)

        try:
            soundfile.write(output_path, audio_data, sr)
            logging.info("[%s] Saved intermediate file: %s", self.stage_name, output_path)
        except Exception as e:  # pylint: disable=broad-except
            logging.error(
                "[%s] Error saving intermediate file %s: %s", self.stage_name, output_path, e
            )
            if output_path != original_file_path:
                shutil.copy(original_file_path, output_path)
            logging.info("[%s] Copied original to %s as fallback.", self.stage_name, output_path)
            return output_path
        return output_path

    def _copy_with_suffix(self, input_file_path: str, suffix: str) -> str:
        """Copies the input file to the working directory with a new suffix."""
        original_filename = os.path.basename(input_file_path)
        base, ext = os.path.splitext(original_filename)

        common_suffixes = [
            "_denoised",
            "_click_removed",
            "_adjusted",
            "_meta_updated",
            "_perfected",
        ]
        for s in common_suffixes:
            if base.endswith(s):
                base = base[: -len(s)]

        new_filename = f"{base}_{suffix}{ext}"
        output_path = os.path.join(self.working_dir, new_filename)

        if input_file_path == output_path:
            logging.debug(
                "[%s] Input and output paths are identical, no copy needed: %s",
                self.stage_name,
                input_file_path
            )
            return input_file_path

        try:
            shutil.copy(input_file_path, output_path)
            logging.info("[%s] Copied file to: %s", self.stage_name, output_path)
        except Exception as e:  # pylint: disable=broad-except
            logging.error(
                "[%s] Error copying file %s to %s: %s",
                self.stage_name,
                input_file_path,
                output_path,
                e
            )
            return input_file_path
        return output_path

    @abc.abstractmethod
    def process(
        self, input_file_path: str, evaluation_result: VocalChopEvaluationResult
    ) -> str:
        """
        Processes the audio file based on the stage's logic.
        Returns the path to the processed audio file (which might be in the working_dir).
        """

# pylint: disable=too-few-public-methods
class DenoisingStage(ProcessingStage):
    """Stage for denoising the audio."""

    def __init__(self, working_dir: str, config: Optional[dict] = None):
        super().__init__(working_dir, stage_name="DenoisingStage", config=config)

    def process(
        self, input_file_path: str, evaluation_result: VocalChopEvaluationResult
    ) -> str:
        logging.info("[%s] Processing %s...", self.stage_name, input_file_path)
        output_file_path = input_file_path

        if evaluation_result.denoising_recommended:
            logging.info("[%s] Denoising recommended for %s.", self.stage_name, input_file_path)
            
            vst3_path = self.config.get("vst3_path")
            if vst3_path:
                logging.info("[%s] Using VST3 plugin for denoising: %s", self.stage_name, vst3_path)
                try:
                    # Read audio
                    audio_data, sr = soundfile.read(input_file_path)
                    if audio_data.ndim > 1:
                        audio_data = np.mean(audio_data, axis=1) # Mono conversion
                    
                    # Process via VST3 stage
                    chain = [{"stage_name": "vst3_plugin", "params": {
                        "plugin_path": vst3_path,
                        "plugin_settings": self.config.get("vst3_settings", {})
                    }}]
                    processed_audio = execute_stage_chain(
                        initial_data=audio_data,
                        initial_data_type="audio_buffer_mono",
                        chain_definition=chain,
                        context={"sample_rate": sr}
                    )
                    output_file_path = self._save_intermediate(processed_audio, sr, input_file_path, "denoised_vst")
                except Exception as e:
                    logging.error("[%s] VST3 denoising failed: %s", self.stage_name, e)
                    output_file_path = self._copy_with_suffix(input_file_path, "denoised_failed")
            else:
                # TODO: Implement native denoising (e.g. spectral subtraction)
                logging.debug(
                    "[%s] Native denoising not yet implemented. Passing through.", self.stage_name
                )
                output_file_path = self._copy_with_suffix(input_file_path, "denoised_stub")
        else:
            logging.info(
                "[%s] Denoising not recommended for %s. Skipping.",
                self.stage_name,
                input_file_path
            )
        return output_file_path

# pylint: disable=too-few-public-methods
class ClickPopRemovalStage(ProcessingStage):
    """Stage for removing clicks and pops."""

    def __init__(self, working_dir: str, config: Optional[dict] = None):
        super().__init__(working_dir, stage_name="ClickPopRemovalStage", config=config)

    def process(
        self, input_file_path: str, evaluation_result: VocalChopEvaluationResult
    ) -> str:
        logging.info("[%s] Processing %s...", self.stage_name, input_file_path)
        output_file_path = input_file_path

        if evaluation_result.click_pop_detected:
            logging.info(
                "[%s] Click/pop removal recommended for %s.",
                self.stage_name,
                input_file_path
            )
            
            vst3_path = self.config.get("vst3_path")
            if vst3_path:
                logging.info("[%s] Using VST3 plugin for click removal: %s", self.stage_name, vst3_path)
                try:
                    audio_data, sr = soundfile.read(input_file_path)
                    if audio_data.ndim > 1:
                        audio_data = np.mean(audio_data, axis=1)
                    
                    chain = [{"stage_name": "vst3_plugin", "params": {
                        "plugin_path": vst3_path,
                        "plugin_settings": self.config.get("vst3_settings", {})
                    }}]
                    processed_audio = execute_stage_chain(
                        initial_data=audio_data,
                        initial_data_type="audio_buffer_mono",
                        chain_definition=chain,
                        context={"sample_rate": sr}
                    )
                    output_file_path = self._save_intermediate(processed_audio, sr, input_file_path, "clickremoved_vst")
                except Exception as e:
                    logging.error("[%s] VST3 click removal failed: %s", self.stage_name, e)
                    output_file_path = self._copy_with_suffix(input_file_path, "clickremoved_failed")
            else:
                # TODO: Implement native click removal (e.g. interpolation)
                logging.debug(
                    "[%s] Native click/pop removal not yet implemented. Passing through.", self.stage_name
                )
                output_file_path = self._copy_with_suffix(
                    input_file_path, "clickremoved_stub"
                )
        else:
            logging.info(
                "[%s] No clicks/pops detected or recommendation for %s. Skipping.",
                self.stage_name,
                input_file_path
            )
        return output_file_path

# pylint: disable=too-few-public-methods
class SilenceAndStabAdjustmentStage(ProcessingStage):
    """Stage for adjusting silence and stab boundaries."""

    def __init__(self, working_dir: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(working_dir, stage_name="SilenceAndStabAdjustmentStage")
        self.config = config or {}

    def _find_closest_zero_crossing(
        self,
        audio_segment: np.ndarray,
        center_sample_in_segment: int,
        search_window_samples: int,
    ) -> int:
        """
        Finds the closest zero-crossing to a center sample within a search window.
        Returns the index of the zero crossing within the audio_segment.
        """
        if len(audio_segment) == 0:
            return center_sample_in_segment

        start = max(0, center_sample_in_segment - search_window_samples // 2)
        end = min(
            len(audio_segment), center_sample_in_segment + search_window_samples // 2
        )

        windowed_segment = audio_segment[start:end]
        if len(windowed_segment) == 0:
            return center_sample_in_segment

        zc_points = librosa.zero_crossings(windowed_segment, pad=False)
        zc_indices_in_window = np.where(zc_points)[0]

        if not zc_indices_in_window.size:
            return center_sample_in_segment

        center_in_windowed_segment = center_sample_in_segment - start
        closest_zc_idx_in_window = zc_indices_in_window[
            np.argmin(np.abs(zc_indices_in_window - center_in_windowed_segment))
        ]
        return start + closest_zc_idx_in_window

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def process( # noqa: C901
        self, input_file_path: str, evaluation_result: VocalChopEvaluationResult
    ) -> str:
        logging.info("[%s] Processing %s...", self.stage_name, input_file_path)

        try:
            audio_data, sr = soundfile.read(input_file_path, dtype="float64")
            if audio_data.ndim > 1:
                audio_data = np.mean(audio_data, axis=1)
        except Exception as e: # pylint: disable=broad-except
            logging.error(
                "[%s] Error reading audio file %s: %s", self.stage_name, input_file_path, e
            )
            return self._copy_with_suffix(input_file_path, "adjustment_failed_load")

        if not evaluation_result.stabs:
            logging.info(
                "[%s] No stabs in evaluation_result. Skipping adjustment.", self.stage_name
            )
            return self._copy_with_suffix(input_file_path, "adjusted_no_stabs")

        min_silence_duration_ms = VocalChopIdealCharacteristics().min_silence_duration_ms

        processed_segments = []
        updated_stabs_info = []
        current_sample_offset = 0
        zc_search_window_ms = 10
        zc_search_samples = int((zc_search_window_ms / 1000.0) * sr)

        for i, stab_original in enumerate(evaluation_result.stabs):
            stab_copy = dataclasses.replace(stab_original)

            original_start = stab_copy.start_sample
            original_end = stab_copy.end_sample
            stab_copy.start_sample = max(0, min(original_start, len(audio_data) - 1))
            stab_copy.end_sample = max(
                stab_copy.start_sample, min(original_end, len(audio_data))
            )

            if stab_copy.end_sample <= stab_copy.start_sample:
                logging.warning(
                    "[%s] Stab %s has zero or negative length after boundary correction. "
                    "Original start: %s, end: %s. Skipping.",
                    self.stage_name, i + 1, original_start, original_end
                )
                continue

            search_start_begin = max(0, stab_copy.start_sample - zc_search_samples // 2)
            search_start_end = min(
                len(audio_data), stab_copy.start_sample + zc_search_samples // 2
            )
            start_window = audio_data[search_start_begin:search_start_end]
            if len(start_window) > 0:
                relative_start_zc = self._find_closest_zero_crossing(
                    start_window,
                    stab_copy.start_sample - search_start_begin,
                    zc_search_samples,
                )
                stab_copy.start_sample = search_start_begin + relative_start_zc

            search_end_begin = max(0, stab_copy.end_sample - zc_search_samples // 2)
            search_end_end = min(
                len(audio_data), stab_copy.end_sample + zc_search_samples // 2
            )
            end_window = audio_data[search_end_begin:search_end_end]
            if len(end_window) > 0:
                relative_end_zc = self._find_closest_zero_crossing(
                    end_window, stab_copy.end_sample - search_end_begin, zc_search_samples
                )
                stab_copy.end_sample = search_end_begin + relative_end_zc

            if stab_copy.end_sample <= stab_copy.start_sample:
                stab_copy.end_sample = stab_copy.start_sample + int(0.01 * sr)
                stab_copy.end_sample = min(stab_copy.end_sample, len(audio_data))
                if stab_copy.end_sample <= stab_copy.start_sample:
                    logging.warning(
                        "[%s] Stab %s collapsed or invalid after ZC adjustment. Skipping.",
                        self.stage_name, i + 1
                    )
                    continue

            stab_audio_segment = audio_data[stab_copy.start_sample : stab_copy.end_sample]
            processed_segments.append(stab_audio_segment)

            new_stab_start_sample = current_sample_offset
            current_sample_offset += len(stab_audio_segment)
            new_stab_end_sample = current_sample_offset

            updated_stabs_info.append(
                AnalyzedVocalStab(
                    start_sample=new_stab_start_sample,
                    end_sample=new_stab_end_sample,
                    label=stab_copy.label,
                    duration_ms=(
                        (new_stab_end_sample - new_stab_start_sample) / sr
                    ) * 1000,
                    has_clean_start_zero_crossing=True,
                    has_clean_end_zero_crossing=True,
                    issues=stab_copy.issues[:],
                )
            )

            if i < len(evaluation_result.stabs) - 1:
                silence_samples = int((min_silence_duration_ms / 1000.0) * sr)
                if silence_samples > 0:
                    silent_segment = np.zeros(silence_samples, dtype=audio_data.dtype)
                    processed_segments.append(silent_segment)
                    current_sample_offset += len(silent_segment)

        if not processed_segments:
            logging.info(
                "[%s] No segments processed. Output is copy of input.", self.stage_name
            )
            final_audio_data = np.copy(audio_data)
        else:
            final_audio_data = np.concatenate(processed_segments)

        evaluation_result.stabs = updated_stabs_info
        evaluation_result.issues.append(
            f"[{self.stage_name}] Stabs adjusted and silences enforced."
        )
        if len(updated_stabs_info) > 1:
            evaluation_result.average_silence_between_stabs_ms = min_silence_duration_ms
        elif not updated_stabs_info: # No stabs processed
            evaluation_result.average_silence_between_stabs_ms = None
        # else: 1 stab, average_silence_between_stabs_ms remains as it was (likely None)

        output_file_path = self._save_intermediate(
            final_audio_data, sr, input_file_path, "adjusted"
        )
        return output_file_path

# pylint: disable=too-few-public-methods
class MetadataUpdateStage(ProcessingStage):
    """Stage for updating WAV metadata (tags, comments)."""

    def __init__(self, working_dir: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(working_dir, stage_name="MetadataUpdateStage")
        self.config = config or {}


    # pylint: disable=too-many-branches,too-many-statements # Refactor if it gets too complex
    def process( # noqa: C901
        self, input_file_path: str, evaluation_result: VocalChopEvaluationResult
    ) -> str:
        logging.info("[%s] Processing %s...", self.stage_name, input_file_path)
        output_file_path = self._copy_with_suffix(input_file_path, "meta_updated")

        # Prepare a detailed comment string
        comment_parts = ["Processed by VocalChopPerfectionWorkflow."]

        if evaluation_result.tempo is not None:
            comment_parts.append(f"Estimated Tempo: {evaluation_result.tempo:.2f} BPM")
        else:
            comment_parts.append("Tempo: Not estimated or found in source metadata.")

        if evaluation_result.key is not None:
            # Removed key_confidence check as it's not a standard field in VocalChopEvaluationResult
            # The key itself might come from estimation (which might have confidence internally)
            # or from basic metadata tags.
            comment_parts.append(f"Key: {evaluation_result.key}")
        else:
            comment_parts.append("Key: Not estimated or found in source metadata.")

        comment_parts.append("\nStab Information:")
        if evaluation_result.stabs:
            for i, stab in enumerate(evaluation_result.stabs):
                stab_info = (
                    f"  Stab {i+1}: Start={stab.start_sample}, End={stab.end_sample}, "
                    f"Duration={stab.duration_ms:.2f}ms, Label='{stab.label or 'N/A'}'"
                )
                comment_parts.append(stab_info)
        else:
            comment_parts.append("  No stab information available or processed.")

        # Add any major issues found during evaluation to the comment
        if evaluation_result.issues:
            comment_parts.append("\nEvaluation Issues:")
            for issue in evaluation_result.issues:
                 # Limit length of issue in comment to avoid overly long strings
                comment_parts.append(f"  - {issue[:100]}" + ("..." if len(issue) > 100 else ""))

        detailed_comment = "\n".join(comment_parts)

        # Use the new soundfile_utils function to write standard metadata
        # For now, we'll primarily use the 'comment' and 'software' fields.
        # Title and artist could be derived or passed if available.
        software_tag = "Vocal Chop Perfectioner v0.1" # Example software tag

        success = soundfile_utils.write_standard_metadata(
            file_path=output_file_path,
            comment=detailed_comment,
            software=software_tag
            # title=evaluation_result.title, # If available
            # artist=evaluation_result.artist # If available
        )

        if success:
            logging.info("[%s] Standard metadata (comment, software) written to %s.",
                         self.stage_name, output_file_path)
        else:
            logging.warning("[%s] Failed to write some or all standard metadata to %s.",
                            self.stage_name, output_file_path)
            evaluation_result.issues.append(
                f"[{self.stage_name}] Failed to write all standard metadata tags."
            )

        # The old CFFI-based metadata setting for cues, instrument, loop info is removed
        # as per the new strategy. These are not standard string tags handled by
        # the simplified write_standard_metadata.

        return output_file_path

# pylint: disable=too-few-public-methods
class VocalChopPerfectionWorkflow:
    """Orchestrates the vocal chop perfection processing stages."""

    def __init__(
        self, initial_file_path: str, evaluation_result: VocalChopEvaluationResult, config: Optional[dict] = None
    ):
        self.initial_file_path = initial_file_path
        self.evaluation_result = evaluation_result
        self.config = config or {}
        self.stages: List[Type[ProcessingStage]] = [
            DenoisingStage,
            ClickPopRemovalStage,
            SilenceAndStabAdjustmentStage,
            MetadataUpdateStage,
        ]

    def run(self, output_dir: str) -> Tuple[str, str]:
        """
        Runs the full perfection workflow.
        Returns a tuple: (path_to_final_perfected_file, path_to_working_directory_for_intermediates).
        """
        if not os.path.exists(self.initial_file_path):
            raise FileNotFoundError(f"Initial file not found: {self.initial_file_path}")

        base_filename = os.path.splitext(os.path.basename(self.initial_file_path))[0]
        run_working_dir = os.path.join(
            output_dir, f"{base_filename}_processing_intermediates"
        )
        if not os.path.exists(run_working_dir):
            os.makedirs(run_working_dir, exist_ok=True)

        logging.info("Starting Vocal Chop Perfection Workflow for: %s", self.initial_file_path)
        logging.info("Intermediate files will be stored in: %s", run_working_dir)

        current_file_path = self.initial_file_path

        for stage_class in self.stages:
            # Get config for this specific stage if available
            stage_config = self.config.get(stage_class.__name__, {})
            stage_instance = stage_class(working_dir=run_working_dir, config=stage_config)
            try:
                current_file_path = stage_instance.process(
                    current_file_path, self.evaluation_result
                )
                logging.info(
                    "Finished stage: %s, output: %s",
                    stage_instance.stage_name, current_file_path
                )
            except Exception as e: # pylint: disable=broad-except
                logging.error("Error during stage %s: %s", stage_instance.stage_name, e)
                logging.error(
                    "Workflow halted due to error in stage %s.", stage_instance.stage_name
                )
                return current_file_path, run_working_dir

        final_perfected_filename = f"{base_filename}_perfected.wav"
        final_output_path = os.path.join(output_dir, final_perfected_filename)

        try:
            shutil.copy(current_file_path, final_output_path)
            logging.info(
                "Successfully perfected vocal chop. Final output: %s", final_output_path
            )
        except Exception as e: # pylint: disable=broad-except
            logging.error(
                "Error copying final perfected file from %s to %s: %s",
                current_file_path,
                final_output_path,
                e
            )
            return current_file_path, run_working_dir

        return final_output_path, run_working_dir


if __name__ == "__main__":
    # Basic logging setup for the __main__ example
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # This is a placeholder for a real VocalChopEvaluationResult
    # In a real scenario, this would be populated by VocalChopEvaluator
    MOCK_EVAL_RESULT = VocalChopEvaluationResult(file_path="test.wav")
    MOCK_EVAL_RESULT.denoising_recommended = True
    MOCK_EVAL_RESULT.click_pop_detected = True
    # ... populate other fields as needed for testing stages

    DUMMY_TEST_FILE = "test.wav"
    if not os.path.exists(DUMMY_TEST_FILE):
        try:
            dummy_audio_data = np.random.rand(44100 * 2).astype(np.float32)
            soundfile.write(DUMMY_TEST_FILE, dummy_audio_data, 44100)
            logging.info("Created dummy %s for example usage.", DUMMY_TEST_FILE)
        except Exception as e: # pylint: disable=broad-except
            logging.error("Could not create dummy %s: %s", DUMMY_TEST_FILE, e)

    if os.path.exists(DUMMY_TEST_FILE):
        OUTPUT_DIR_EXAMPLE = "output_perfection" # Renamed to avoid conflict
        if not os.path.exists(OUTPUT_DIR_EXAMPLE):
            os.makedirs(OUTPUT_DIR_EXAMPLE, exist_ok=True)

        workflow = VocalChopPerfectionWorkflow(
            initial_file_path=DUMMY_TEST_FILE, evaluation_result=MOCK_EVAL_RESULT
        )
        final_file, intermediates_dir = workflow.run(output_dir=OUTPUT_DIR_EXAMPLE)
        logging.info("Workflow finished.")
        logging.info("Final perfected file: %s", final_file)
        logging.info("Intermediate files are in: %s", intermediates_dir)
    else:
        logging.info("Skipping example usage as %s could not be created/found.", DUMMY_TEST_FILE)
