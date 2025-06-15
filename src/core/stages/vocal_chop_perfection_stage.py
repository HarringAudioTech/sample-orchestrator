"""
Defines processing stages for the vocal chop perfection workflow.

Each stage takes an audio file and an evaluation result, performs a specific
modification or analysis, and outputs a (potentially modified) audio file path.
The workflow orchestrates these stages.
"""
import os
import shutil
import abc  # Abstract Base Class
from typing import Tuple, Optional, List, Type
import dataclasses

import soundfile  # type: ignore # pylint: disable=import-error
import numpy as np  # type: ignore # pylint: disable=import-error
import librosa  # type: ignore # pylint: disable=import-error

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

    def __init__(self, working_dir: str, stage_name: Optional[str] = None):
        self.working_dir = working_dir
        self.stage_name = stage_name if stage_name else self.__class__.__name__
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
            print(f"[{self.stage_name}] Saved intermediate file: {output_path}")
        except Exception as e:  # pylint: disable=broad-except
            print(
                f"[{self.stage_name}] Error saving intermediate file {output_path}: {e}"
            )
            if output_path != original_file_path:
                shutil.copy(original_file_path, output_path)
            print(f"[{self.stage_name}] Copied original to {output_path} as fallback.")
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
            print(
                f"[{self.stage_name}] Input and output paths are identical, "
                f"no copy needed: {input_file_path}"
            )
            return input_file_path

        try:
            shutil.copy(input_file_path, output_path)
            print(f"[{self.stage_name}] Copied file to: {output_path}")
        except Exception as e:  # pylint: disable=broad-except
            print(
                f"[{self.stage_name}] Error copying file {input_file_path} "
                f"to {output_path}: {e}"
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

    def __init__(self, working_dir: str):
        super().__init__(working_dir, stage_name="DenoisingStage")

    def process(
        self, input_file_path: str, evaluation_result: VocalChopEvaluationResult
    ) -> str:
        print(f"[{self.stage_name}] Processing {input_file_path}...")
        output_file_path = input_file_path

        if evaluation_result.denoising_recommended:
            print(f"[{self.stage_name}] Denoising recommended for {input_file_path}.")
            # TODO: Implement actual denoising logic here.
            print(
                f"[{self.stage_name}] Denoising not yet implemented. Passing through."
            )
            output_file_path = self._copy_with_suffix(input_file_path, "denoised_stub")
        else:
            print(
                f"[{self.stage_name}] Denoising not recommended for "
                f"{input_file_path}. Skipping."
            )
        return output_file_path

# pylint: disable=too-few-public-methods
class ClickPopRemovalStage(ProcessingStage):
    """Stage for removing clicks and pops."""

    def __init__(self, working_dir: str):
        super().__init__(working_dir, stage_name="ClickPopRemovalStage")

    def process(
        self, input_file_path: str, evaluation_result: VocalChopEvaluationResult
    ) -> str:
        print(f"[{self.stage_name}] Processing {input_file_path}...")
        output_file_path = input_file_path

        if evaluation_result.click_pop_detected:
            print(
                f"[{self.stage_name}] Click/pop removal recommended for {input_file_path}."
            )
            # TODO: Implement actual click/pop removal logic here.
            print(
                f"[{self.stage_name}] Click/pop removal not yet implemented. Passing through."
            )
            output_file_path = self._copy_with_suffix(
                input_file_path, "clickremoved_stub"
            )
        else:
            print(
                f"[{self.stage_name}] No clicks/pops detected or recommendation for "
                f"{input_file_path}. Skipping."
            )
        return output_file_path

# pylint: disable=too-few-public-methods
class SilenceAndStabAdjustmentStage(ProcessingStage):
    """Stage for adjusting silence and stab boundaries."""

    def __init__(self, working_dir: str):
        super().__init__(working_dir, stage_name="SilenceAndStabAdjustmentStage")

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
        print(f"[{self.stage_name}] Processing {input_file_path}...")

        try:
            audio_data, sr = soundfile.read(input_file_path, dtype="float64")
            if audio_data.ndim > 1:
                audio_data = np.mean(audio_data, axis=1)
        except Exception as e: # pylint: disable=broad-except
            print(
                f"[{self.stage_name}] Error reading audio file {input_file_path}: {e}"
            )
            return self._copy_with_suffix(input_file_path, "adjustment_failed_load")

        if not evaluation_result.stabs:
            print(
                f"[{self.stage_name}] No stabs in evaluation_result. Skipping adjustment."
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
                print(
                    f"[{self.stage_name}] Warning: Stab {i+1} has zero or negative length "
                    f"after boundary correction. Original start: {original_start}, "
                    f"end: {original_end}. Skipping."
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
                    print(
                        f"[{self.stage_name}] Warning: Stab {i+1} collapsed or invalid "
                        "after ZC adjustment. Skipping."
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
            print(
                f"[{self.stage_name}] No segments processed. Output is copy of input."
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
    """Stage for updating metadata in the audio file."""

    def __init__(self, working_dir: str):
        super().__init__(working_dir, stage_name="MetadataUpdateStage")

    def _set_string_metadata(
        self, file_path: str, str_type: int, content: str
    ) -> bool:
        """Helper to set string metadata using SFC_SET_STRING."""
        try:
            with soundfile.SoundFile(file_path, mode="r+") as sf:
                # string_bytes = content.encode('utf-8', 'replace') + b'\x00' # pylint: disable=unused-variable
                if str_type == soundfile_utils.sf_lib.SF_STR_COMMENT:
                    sf.comment = content
                    sf.flush()
                    print(f"[{self.stage_name}] Set comment metadata.")
                    return True
                # Add other cases for SF_STR_TITLE, SF_STR_ARTIST etc.
                print(
                    f"[{self.stage_name}] Setting string type {str_type} not directly "
                    "supported by simple attributes. SFC_SET_STRING needed."
                )
                return False
        except Exception as e: # pylint: disable=broad-except
            print(
                f"[{self.stage_name}] Error setting string metadata "
                f"(type {str_type}): {e}"
            )
            return False

    # pylint: disable=too-many-branches,too-many-statements
    def process( # noqa: C901
        self, input_file_path: str, evaluation_result: VocalChopEvaluationResult
    ) -> str:
        print(f"[{self.stage_name}] Processing {input_file_path}...")
        output_file_path = self._copy_with_suffix(input_file_path, "meta_updated")

        if evaluation_result.stabs:
            prepared_cue_list: List[soundfile_utils.SFCuePoint] = []
            for i, stab_info in enumerate(evaluation_result.stabs):
                label = stab_info.label if stab_info.label else f"Stab {i+1}"
                name_bytes = label.encode("utf-8", "replace")
                if len(name_bytes) > 255:
                    name_bytes = name_bytes[:255]
                cue_point = soundfile_utils.SFCuePoint(
                    indx=i + 1, position=stab_info.start_sample, name=name_bytes
                )
                prepared_cue_list.append(cue_point)

            if not soundfile_utils.set_cue_markers(output_file_path, prepared_cue_list):
                print(f"[{self.stage_name}] Failed to set cue markers.")
                evaluation_result.issues.append(
                    f"[{self.stage_name}] Failed to write updated cue markers."
                )
            else:
                print(f"[{self.stage_name}] Successfully updated cue markers.")

        loop_info_to_set = None
        existing_loop_info = soundfile_utils.get_loop_info(output_file_path)

        if evaluation_result.tempo is not None:
            if existing_loop_info is None:
                existing_loop_info = soundfile_utils.SFLoopInfo(
                    time_sig_num=4, time_sig_den=4,
                    loop_mode=soundfile_utils.SF_LOOP_NONE
                )
            if existing_loop_info.bpm != evaluation_result.tempo:
                existing_loop_info.bpm = evaluation_result.tempo
                loop_info_to_set = existing_loop_info
                print(
                    f"[{self.stage_name}] Preparing to update BPM to {evaluation_result.tempo}."
                )

        if evaluation_result.key is not None:
            try:
                midi_note = int(librosa.note_to_midi(evaluation_result.key))
                if existing_loop_info is None:
                    existing_loop_info = soundfile_utils.SFLoopInfo(
                        time_sig_num=4, time_sig_den=4,
                        loop_mode=soundfile_utils.SF_LOOP_NONE
                    )
                if existing_loop_info.root_key != midi_note:
                    existing_loop_info.root_key = midi_note
                    loop_info_to_set = existing_loop_info
                    print(
                        f"[{self.stage_name}] Preparing to update loop root key to MIDI "
                        f"{midi_note} ({evaluation_result.key})."
                    )
            except Exception as e: # pylint: disable=broad-except
                print(
                    f"[{self.stage_name}] Error converting key "
                    f"'{evaluation_result.key}' to MIDI for loop info: {e}"
                )
                evaluation_result.issues.append(f"Error converting key for loop_info: {e}")

        if loop_info_to_set:
            if not soundfile_utils.set_loop_info(output_file_path, loop_info_to_set):
                print(f"[{self.stage_name}] Failed to set loop info (tempo/key).")
                evaluation_result.issues.append(
                    f"[{self.stage_name}] Failed to write loop info."
                )
            else:
                print(f"[{self.stage_name}] Successfully updated loop info.")

        if evaluation_result.key is not None:
            try:
                midi_note = int(librosa.note_to_midi(evaluation_result.key))
                instr_info = soundfile_utils.get_instrument_info(output_file_path)
                if instr_info is None:
                    instr_info = soundfile_utils.SFInstrumentInfo(
                        gain=0, detune=0, velocity_lo=0, velocity_hi=127,
                        key_lo=0, key_hi=127, loop_count=0
                    )
                if instr_info.basenote != midi_note:
                    instr_info.basenote = midi_note
                    if not soundfile_utils.set_instrument_info(output_file_path, instr_info):
                        evaluation_result.issues.append(
                            f"[{self.stage_name}] Failed to write instrument info for key."
                        ) # Corrected long line
                    else:
                        print(
                            f"[{self.stage_name}] Successfully updated instrument info "
                            f"with key MIDI {midi_note}."
                        )
            except Exception as e: # pylint: disable=broad-except
                print(
                    f"[{self.stage_name}] Error converting key "
                    f"'{evaluation_result.key}' to MIDI for instrument info: {e}"
                )
                evaluation_result.issues.append(
                    f"Error converting key for SFInstrumentInfo: {e}"
                )

        comment_string = "Processed by VocalChopPerfectionWorkflow."
        if hasattr(soundfile_utils.sf_lib, 'SF_STR_COMMENT'):
            if not self._set_string_metadata(
                output_file_path, soundfile_utils.sf_lib.SF_STR_COMMENT, comment_string
            ):
                print(
                    f"[{self.stage_name}] Could not write comment string via helper. "
                    "Manual SFC_SET_STRING might be needed."
                )
                # TODO: Implement robust SFC_SET_STRING in soundfile_utils
        else:
            print(
                f"[{self.stage_name}] SF_STR_COMMENT not found in "
                "soundfile_utils.sf_lib. Cannot set comment."
            )
        return output_file_path

# pylint: disable=too-few-public-methods
class VocalChopPerfectionWorkflow:
    """Orchestrates the vocal chop perfection processing stages."""

    def __init__(
        self, initial_file_path: str, evaluation_result: VocalChopEvaluationResult
    ):
        self.initial_file_path = initial_file_path
        self.evaluation_result = evaluation_result
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

        print(f"Starting Vocal Chop Perfection Workflow for: {self.initial_file_path}")
        print(f"Intermediate files will be stored in: {run_working_dir}")

        current_file_path = self.initial_file_path

        for stage_class in self.stages:
            stage_instance = stage_class(working_dir=run_working_dir)
            try:
                current_file_path = stage_instance.process(
                    current_file_path, self.evaluation_result
                )
                print(
                    f"Finished stage: {stage_instance.stage_name}, output: {current_file_path}"
                )
            except Exception as e: # pylint: disable=broad-except
                print(f"Error during stage {stage_instance.stage_name}: {e}")
                print(
                    f"Workflow halted due to error in stage {stage_instance.stage_name}."
                )
                return current_file_path, run_working_dir

        final_perfected_filename = f"{base_filename}_perfected.wav"
        final_output_path = os.path.join(output_dir, final_perfected_filename)

        try:
            shutil.copy(current_file_path, final_output_path)
            print(
                f"Successfully perfected vocal chop. Final output: {final_output_path}"
            )
        except Exception as e: # pylint: disable=broad-except
            print(
                f"Error copying final perfected file from {current_file_path} "
                f"to {final_output_path}: {e}"
            )
            return current_file_path, run_working_dir

        return final_output_path, run_working_dir


if __name__ == "__main__":
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
            print(f"Created dummy {DUMMY_TEST_FILE} for example usage.")
        except Exception as e: # pylint: disable=broad-except
            print(f"Could not create dummy {DUMMY_TEST_FILE}: {e}")

    if os.path.exists(DUMMY_TEST_FILE):
        OUTPUT_DIR_EXAMPLE = "output_perfection" # Renamed to avoid conflict
        if not os.path.exists(OUTPUT_DIR_EXAMPLE):
            os.makedirs(OUTPUT_DIR_EXAMPLE, exist_ok=True)

        workflow = VocalChopPerfectionWorkflow(
            initial_file_path=DUMMY_TEST_FILE, evaluation_result=MOCK_EVAL_RESULT
        )
        final_file, intermediates_dir = workflow.run(output_dir=OUTPUT_DIR_EXAMPLE) # Corrected variable
        print("Workflow finished.")
        print(f"Final perfected file: {final_file}")
        print(f"Intermediate files are in: {intermediates_dir}")
    else:
        print(f"Skipping example usage as {DUMMY_TEST_FILE} could not be created/found.")
