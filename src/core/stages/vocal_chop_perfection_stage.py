import os
import shutil
import soundfile
import numpy as np
from typing import Tuple, Optional, List, Type
import abc # Abstract Base Class

# Assuming these are in the parent directory or src/core
import librosa # For zero_crossings, will be used in SilenceAndStabAdjustmentStage

# Adjust imports based on actual project structure if these files are elsewhere.
try:
    from src.core.vocal_chop_evaluator import VocalChopEvaluationResult, AnalyzedVocalStab, VocalChopIdealCharacteristics
    from src.utils import soundfile_utils
except ImportError:
    # Fallback for cases where the script might be run directly or structure is different
    # This is primarily for development; a real project would have a fixed structure.
    from core.vocal_chop_evaluator import VocalChopEvaluationResult, AnalyzedVocalStab, VocalChopIdealCharacteristics
    from utils import soundfile_utils


class ProcessingStage(abc.ABC):
    """Abstract base class for a processing stage in the vocal chop perfection workflow."""

    def __init__(self, working_dir: str, stage_name: Optional[str] = None):
        self.working_dir = working_dir
        self.stage_name = stage_name if stage_name else self.__class__.__name__
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir, exist_ok=True)

    def _save_intermediate(self, audio_data: np.ndarray, sr: int, original_file_path: str, suffix: str) -> str:
        """
        Saves an intermediate audio file to the working directory.
        Filename will be original_basename.suffix.wav
        """
        original_filename = os.path.basename(original_file_path)
        base, _ = os.path.splitext(original_filename)
        # Remove common previous suffixes to avoid original.stage1.stage2.wav if input is already an intermediate
        common_suffixes = ["_denoised", "_click_removed", "_adjusted", "_meta_updated", "_perfected"]
        for s in common_suffixes:
            if base.endswith(s):
                base = base[:-len(s)]

        new_filename = f"{base}_{suffix}.wav"
        output_path = os.path.join(self.working_dir, new_filename)

        try:
            soundfile.write(output_path, audio_data, sr)
            print(f"[{self.stage_name}] Saved intermediate file: {output_path}")
        except Exception as e:
            print(f"[{self.stage_name}] Error saving intermediate file {output_path}: {e}")
            # Fallback: copy original if saving modified data fails, to allow pipeline to continue
            if output_path != original_file_path: # Avoid copying to itself
                 shutil.copy(original_file_path, output_path)
            print(f"[{self.stage_name}] Copied original to {output_path} as fallback.")
            return output_path # Return original path or copied path
        return output_path

    def _copy_with_suffix(self, input_file_path: str, suffix: str) -> str:
        """Copies the input file to the working directory with a new suffix."""
        original_filename = os.path.basename(input_file_path)
        base, ext = os.path.splitext(original_filename)

        common_suffixes = ["_denoised", "_click_removed", "_adjusted", "_meta_updated", "_perfected"]
        for s in common_suffixes:
            if base.endswith(s):
                base = base[:-len(s)]

        new_filename = f"{base}_{suffix}{ext}" # Keep original extension
        output_path = os.path.join(self.working_dir, new_filename)

        if input_file_path == output_path: # Avoid copying to itself if names match
            print(f"[{self.stage_name}] Input and output paths are identical, no copy needed: {input_file_path}")
            return input_file_path

        try:
            shutil.copy(input_file_path, output_path)
            print(f"[{self.stage_name}] Copied file to: {output_path}")
        except Exception as e:
            print(f"[{self.stage_name}] Error copying file {input_file_path} to {output_path}: {e}")
            return input_file_path # Return original path on error
        return output_path

    @abc.abstractmethod
    def process(self, input_file_path: str, evaluation_result: VocalChopEvaluationResult) -> str:
        """
        Processes the audio file based on the stage's logic.
        Returns the path to the processed audio file (which might be in the working_dir).
        """
        pass


class DenoisingStage(ProcessingStage):
    """Stage for denoising the audio."""
    def __init__(self, working_dir: str):
        super().__init__(working_dir, stage_name="DenoisingStage")

    def process(self, input_file_path: str, evaluation_result: VocalChopEvaluationResult) -> str:
        print(f"[{self.stage_name}] Processing {input_file_path}...")
        output_file_path = input_file_path # Default to input if no processing happens

        if evaluation_result.denoising_recommended:
            print(f"[{self.stage_name}] Denoising recommended for {input_file_path}.")
            # TODO: Implement actual denoising logic here.
            # Example:
            # try:
            #     y, sr = soundfile.read(input_file_path)
            #     y_denoised = some_denoise_function(y, sr)
            #     output_file_path = self._save_intermediate(y_denoised, sr, input_file_path, "denoised")
            # except Exception as e:
            #     print(f"[{self.stage_name}] Error during denoising: {e}")
            #     output_file_path = self._copy_with_suffix(input_file_path, "denoising_failed")
            print(f"[{self.stage_name}] Denoising not yet implemented. Passing through.")
            output_file_path = self._copy_with_suffix(input_file_path, "denoised_stub")
        else:
            print(f"[{self.stage_name}] Denoising not recommended for {input_file_path}. Skipping.")
            # No change to output_file_path, effectively passing through

        return output_file_path


class ClickPopRemovalStage(ProcessingStage):
    """Stage for removing clicks and pops."""
    def __init__(self, working_dir: str):
        super().__init__(working_dir, stage_name="ClickPopRemovalStage")

    def process(self, input_file_path: str, evaluation_result: VocalChopEvaluationResult) -> str:
        print(f"[{self.stage_name}] Processing {input_file_path}...")
        output_file_path = input_file_path

        if evaluation_result.click_pop_detected:
            print(f"[{self.stage_name}] Click/pop removal recommended for {input_file_path}.")
            # TODO: Implement actual click/pop removal logic here.
            print(f"[{self.stage_name}] Click/pop removal not yet implemented. Passing through.")
            output_file_path = self._copy_with_suffix(input_file_path, "clickremoved_stub")
        else:
            print(f"[{self.stage_name}] No clicks/pops detected or recommendation for {input_file_path}. Skipping.")

        return output_file_path


class SilenceAndStabAdjustmentStage(ProcessingStage):
    """Stage for adjusting silence and stab boundaries."""
    def __init__(self, working_dir: str):
        super().__init__(working_dir, stage_name="SilenceAndStabAdjustmentStage")

    def _find_closest_zero_crossing(self, audio_segment: np.ndarray, center_sample_in_segment: int, search_window_samples: int) -> int:
        """
        Finds the closest zero-crossing to a center sample within a search window inside a segment.
        Returns the index of the zero crossing within the audio_segment.
        """
        if len(audio_segment) == 0:
            return center_sample_in_segment # Should not happen with proper slicing

        start = max(0, center_sample_in_segment - search_window_samples // 2)
        end = min(len(audio_segment), center_sample_in_segment + search_window_samples // 2)

        windowed_segment = audio_segment[start:end]
        if len(windowed_segment) == 0:
             return center_sample_in_segment

        # Get zero crossings (boolean array where True means a crossing occurred after that sample)
        zc_points = librosa.zero_crossings(windowed_segment, pad=False) # pad=False to match indices

        # Find indices of all zero crossings within the windowed_segment
        zc_indices_in_window = np.where(zc_points)[0]

        if len(zc_indices_in_window) == 0:
            # No zero crossing found in the window, return original center point relative to segment start
            return center_sample_in_segment

        # Adjust center_sample_in_segment to be relative to the windowed_segment's start
        center_in_windowed_segment = center_sample_in_segment - start

        # Find the zero crossing index closest to the center_in_windowed_segment
        closest_zc_idx_in_window = zc_indices_in_window[np.argmin(np.abs(zc_indices_in_window - center_in_windowed_segment))]

        # Convert back to index within the original audio_segment
        return start + closest_zc_idx_in_window


    def process(self, input_file_path: str, evaluation_result: VocalChopEvaluationResult) -> str:
        print(f"[{self.stage_name}] Processing {input_file_path}...")

        try:
            audio_data, sr = soundfile.read(input_file_path, dtype='float64')
            if audio_data.ndim > 1: # Ensure mono for processing simplicity here
                audio_data = np.mean(audio_data, axis=1)
        except Exception as e:
            print(f"[{self.stage_name}] Error reading audio file {input_file_path}: {e}")
            return self._copy_with_suffix(input_file_path, "adjustment_failed_load")

        if not evaluation_result.stabs:
            print(f"[{self.stage_name}] No stabs in evaluation_result. Skipping adjustment.")
            return self._copy_with_suffix(input_file_path, "adjusted_no_stabs")

        # This should ideally come from the evaluator's ideal_characteristics
        # For now, let's assume it's accessible or we use a default.
        # ideal_characteristics = VocalChopIdealCharacteristics() # Or passed via evaluation_result
        # Accessing via evaluation_result if evaluator sets it, or define a default
        min_silence_duration_ms = getattr(evaluation_result, 'ideal_characteristics', VocalChopIdealCharacteristics()).min_silence_duration_ms
        if min_silence_duration_ms is None: # Fallback if not set
            min_silence_duration_ms = 75.0


        processed_segments = []
        updated_stabs_info = [] # Store new start/end times for metadata update later

        current_sample_offset = 0 # Tracks the start of the next segment in the new audio

        zc_search_window_ms = 10 # 10ms window for zero-crossing search
        zc_search_samples = int((zc_search_window_ms / 1000.0) * sr)

        for i, stab_original in enumerate(evaluation_result.stabs):
            # Deep copy might be safer if original eval_result.stabs should not be mutated here
            stab = dataclasses.replace(stab_original)

            original_start = stab.start_sample
            original_end = stab.end_sample

            # Ensure stab boundaries are within audio_data length
            stab.start_sample = max(0, min(original_start, len(audio_data) -1))
            stab.end_sample = max(stab.start_sample, min(original_end, len(audio_data)))

            if stab.end_sample <= stab.start_sample:
                print(f"[{self.stage_name}] Warning: Stab {i+1} has zero or negative length after boundary correction. Original start: {original_start}, end: {original_end}. Skipping.")
                # Add a very short silent segment to maintain structure if needed, or skip
                # For now, let's skip adding this stab if it's invalid.
                # If it's skipped, the silence logic will also naturally skip.
                continue


            # Refine start_sample to nearest zero-crossing
            # The _find_closest_zero_crossing expects the center point relative to the segment it's given.
            # Here, we pass the full audio_data and the sample index is absolute.
            # To simplify, we slice a window around the original point for zc search.

            search_start_begin = max(0, stab.start_sample - zc_search_samples // 2)
            search_start_end = min(len(audio_data), stab.start_sample + zc_search_samples // 2)
            start_window = audio_data[search_start_begin:search_start_end]
            if len(start_window) > 0:
                relative_start_zc = self._find_closest_zero_crossing(start_window, stab.start_sample - search_start_begin, zc_search_samples)
                stab.start_sample = search_start_begin + relative_start_zc
            # else: stab.start_sample remains original if window is empty

            search_end_begin = max(0, stab.end_sample - zc_search_samples // 2)
            search_end_end = min(len(audio_data), stab.end_sample + zc_search_samples // 2)
            end_window = audio_data[search_end_begin:search_end_end]
            if len(end_window) > 0:
                relative_end_zc = self._find_closest_zero_crossing(end_window, stab.end_sample - search_end_begin, zc_search_samples)
                stab.end_sample = search_end_begin + relative_end_zc
            # else: stab.end_sample remains original

            # Ensure start < end after adjustment
            if stab.end_sample <= stab.start_sample:
                stab.end_sample = stab.start_sample + int(0.01 * sr) # Make it at least 10ms if collapsed
                stab.end_sample = min(stab.end_sample, len(audio_data)) # Ensure within bounds
                if stab.end_sample <= stab.start_sample: # If still invalid (e.g., at very end of file)
                     print(f"[{self.stage_name}] Warning: Stab {i+1} collapsed or invalid after ZC adjustment. Skipping.")
                     continue


            stab_audio_segment = audio_data[stab.start_sample:stab.end_sample]
            processed_segments.append(stab_audio_segment)

            # Update stab info for evaluation_result (new start/end are relative to new concatenated audio)
            new_stab_start_sample = current_sample_offset
            current_sample_offset += len(stab_audio_segment)
            new_stab_end_sample = current_sample_offset

            updated_stabs_info.append(AnalyzedVocalStab(
                start_sample=new_stab_start_sample,
                end_sample=new_stab_end_sample,
                label=stab.label,
                duration_ms=((new_stab_end_sample - new_stab_start_sample) / sr) * 1000,
                # ZC flags might need re-evaluation on the new segment edges if strictness is required
                has_clean_start_zero_crossing=True, # Assume ZC adjustment was successful
                has_clean_end_zero_crossing=True,   # Assume ZC adjustment was successful
                issues=stab.issues[:] # Copy issues
            ))

            # Add silence after this stab, unless it's the last one
            if i < len(evaluation_result.stabs) - 1:
                silence_samples = int((min_silence_duration_ms / 1000.0) * sr)
                if silence_samples > 0:
                    silent_segment = np.zeros(silence_samples, dtype=audio_data.dtype)
                    processed_segments.append(silent_segment)
                    current_sample_offset += len(silent_segment)

        if not processed_segments:
            print(f"[{self.stage_name}] No segments were processed. Output will be a copy of input.")
            final_audio_data = audio_data # Or copy to avoid modifying original array if it's passed around
        else:
            final_audio_data = np.concatenate(processed_segments)

        # Update the evaluation result with the new stab information
        evaluation_result.stabs = updated_stabs_info
        # Other parts of evaluation_result might become inconsistent (e.g., average_silence_between_stabs_ms)
        # This stage primarily focuses on *constructing* the audio based on ideal silence.
        # A re-evaluation might be needed if exact descriptive stats of the new file are required.
        evaluation_result.issues.append(f"[{self.stage_name}] Stabs adjusted and silences enforced.")
        if evaluation_result.average_silence_between_stabs_ms is not None: # Mark old value as potentially stale
            evaluation_result.average_silence_between_stabs_ms = min_silence_duration_ms # As it's now enforced


        output_file_path = self._save_intermediate(final_audio_data, sr, input_file_path, "adjusted")
        return output_file_path


class MetadataUpdateStage(ProcessingStage):
    """Stage for updating metadata in the audio file."""
    def __init__(self, working_dir: str):
        super().__init__(working_dir, stage_name="MetadataUpdateStage")

    def _set_string_metadata(self, file_path: str, str_type: int, content: str) -> bool:
        """Helper to set string metadata using SFC_SET_STRING."""
        # This is a simplified helper. soundfile.SoundFile.command might need
        # the CFFI pointer for the string directly.
        # For robust implementation, this might need to live in soundfile_utils
        # and handle CFFI memory allocation for the string.
        try:
            with soundfile.SoundFile(file_path, mode='r+') as sf: # Open in r+ to modify
                # The string needs to be passed as a CData pointer (char*)
                # to the command interface.
                string_bytes = content.encode('utf-8', 'replace') + b'\x00' # Null-terminate
                # We need to use _ffi to pass this correctly.
                # c_string = soundfile_utils._ffi.new("char[]", string_bytes) # Requires _ffi from soundfile_utils
                # success = sf.command(soundfile_utils.sf_lib.SFC_SET_STRING, c_string, str_type)
                # The above is complex due to CFFI memory management.
                # Soundfile library itself has direct attributes for some common tags:
                # sf.title = "My Title"
                # sf.artist = "My Artist"
                # sf.comment = "My Comment"
                # These are easier if they cover the needs.
                # For now, let's assume direct attribute setting for common tags.
                if str_type == soundfile_utils.sf_lib.SF_STR_COMMENT:
                    sf.comment = content
                    sf.flush() # Ensure written
                    print(f"[{self.stage_name}] Set comment metadata.")
                    return True
                # Add other cases for SF_STR_TITLE, SF_STR_ARTIST etc. if needed
                else:
                    print(f"[{self.stage_name}] Setting string type {str_type} not directly supported by simple attributes. SFC_SET_STRING needed.")
                    return False

        except Exception as e:
            print(f"[{self.stage_name}] Error setting string metadata (type {str_type}): {e}")
            return False


    def process(self, input_file_path: str, evaluation_result: VocalChopEvaluationResult) -> str:
        print(f"[{self.stage_name}] Processing {input_file_path}...")
        output_file_path = self._copy_with_suffix(input_file_path, "meta_updated")

        # 1. Update Cue Markers
        if evaluation_result.stabs:
            prepared_cue_list: List[soundfile_utils.SFCuePoint] = []
            for i, stab_info in enumerate(evaluation_result.stabs):
                label = stab_info.label if stab_info.label else f"Stab {i+1}"
                # Name bytes encoding and null-termination is handled by SFCuePoint.to_ctypes_struct
                # which is then used by soundfile_utils.set_cue_markers's CFFI interaction.
                name_bytes = label.encode('utf-8', 'replace')
                # Ensure name does not exceed 255 bytes before null termination (struct has char[256])
                if len(name_bytes) > 255:
                    name_bytes = name_bytes[:255]

                cue_point = soundfile_utils.SFCuePoint(
                    indx=i + 1,
                    position=stab_info.start_sample, # These are relative to current audio data
                    fcc_chunk=0, # Typically 0 or 'data' FourCC, handled by libsndfile
                    chunk_start=0,
                    block_start=0,
                    sample_offset=0, # Offset relative to 'position' within the block
                    name=name_bytes
                )
                prepared_cue_list.append(cue_point)

            if not soundfile_utils.set_cue_markers(output_file_path, prepared_cue_list):
                print(f"[{self.stage_name}] Failed to set cue markers.")
                evaluation_result.issues.append(f"[{self.stage_name}] Failed to write updated cue markers.")
            else:
                print(f"[{self.stage_name}] Successfully updated cue markers.")

        # 2. Update Tempo Information (SFLoopInfo)
        loop_info_to_set = None
        existing_loop_info = soundfile_utils.get_loop_info(output_file_path) # Read from the copied file

        if evaluation_result.tempo is not None:
            if existing_loop_info is None:
                existing_loop_info = soundfile_utils.SFLoopInfo() # Create new if none exists
                existing_loop_info.time_sig_num = 4 # Default
                existing_loop_info.time_sig_den = 4 # Default
                existing_loop_info.loop_mode = soundfile_utils.SF_LOOP_NONE

            if existing_loop_info.bpm != evaluation_result.tempo:
                 existing_loop_info.bpm = evaluation_result.tempo
                 loop_info_to_set = existing_loop_info
                 print(f"[{self.stage_name}] Preparing to update BPM to {evaluation_result.tempo}.")

        # Also handle key in loop_info if no instrument info will be set, or as primary
        if evaluation_result.key is not None:
            try:
                midi_note = int(librosa.note_to_midi(evaluation_result.key))
                if existing_loop_info is None: # If tempo wasn't set, loop_info might still be None
                    existing_loop_info = soundfile_utils.SFLoopInfo()
                    existing_loop_info.time_sig_num = 4
                    existing_loop_info.time_sig_den = 4
                    existing_loop_info.loop_mode = soundfile_utils.SF_LOOP_NONE

                if existing_loop_info.root_key != midi_note:
                    existing_loop_info.root_key = midi_note
                    loop_info_to_set = existing_loop_info
                    print(f"[{self.stage_name}] Preparing to update loop root key to MIDI {midi_note} ({evaluation_result.key}).")
            except Exception as e:
                print(f"[{self.stage_name}] Error converting key '{evaluation_result.key}' to MIDI for loop info: {e}")
                evaluation_result.issues.append(f"Error converting key for loop_info: {e}")

        if loop_info_to_set:
            if not soundfile_utils.set_loop_info(output_file_path, loop_info_to_set):
                print(f"[{self.stage_name}] Failed to set loop info (tempo/key).")
                evaluation_result.issues.append(f"[{self.stage_name}] Failed to write loop info.")
            else:
                print(f"[{self.stage_name}] Successfully updated loop info.")

        # 3. Update Key Information (SFInstrumentInfo) - typically for sampler specific key
        # This might be redundant if key is already in SFLoopInfo, but some samplers prefer instrument chunk.
        if evaluation_result.key is not None:
            try:
                midi_note = int(librosa.note_to_midi(evaluation_result.key))
                # Check existing instrument info, if any
                instr_info = soundfile_utils.get_instrument_info(output_file_path)
                if instr_info is None:
                    instr_info = soundfile_utils.SFInstrumentInfo() # Create new
                    # Set defaults for a new instrument block
                    instr_info.gain = 0
                    instr_info.detune = 0
                    instr_info.velocity_lo = 0
                    instr_info.velocity_hi = 127
                    instr_info.key_lo = 0
                    instr_info.key_hi = 127
                    instr_info.loop_count = 0

                if instr_info.basenote != midi_note:
                    instr_info.basenote = midi_note
                    if not soundfile_utils.set_instrument_info(output_file_path, instr_info):
                        print(f"[{self.stage_name}] Failed to set instrument info (key).")
                        evaluation_result.issues.append(f"[{self.stage_name}] Failed to write instrument info for key.")
                    else:
                        print(f"[{self.stage_name}] Successfully updated instrument info with key MIDI {midi_note}.")
            except Exception as e:
                print(f"[{self.stage_name}] Error converting key '{evaluation_result.key}' to MIDI for instrument info: {e}")
                evaluation_result.issues.append(f"Error converting key for SFInstrumentInfo: {e}")

        # 4. Add a comment
        # Using the internal soundfile attributes if possible, as SFC_SET_STRING is complex with CFFI.
        # The _set_string_metadata is a stub that attempts this for comments.
        comment_string = "Processed by VocalChopPerfectionWorkflow."
        if hasattr(soundfile_utils.sf_lib, 'SF_STR_COMMENT'): # Check if constant exists
            if not self._set_string_metadata(output_file_path, soundfile_utils.sf_lib.SF_STR_COMMENT, comment_string):
                print(f"[{self.stage_name}] Could not write comment string via helper. Manual SFC_SET_STRING might be needed.")
                # TODO: Implement robust SFC_SET_STRING in soundfile_utils if direct attributes fail.
        else:
            print(f"[{self.stage_name}] SF_STR_COMMENT not found in soundfile_utils.sf_lib. Cannot set comment.")

        return output_file_path


class VocalChopPerfectionWorkflow:
    """Orchestrates the vocal chop perfection processing stages."""

    def __init__(self, initial_file_path: str, evaluation_result: VocalChopEvaluationResult):
        self.initial_file_path = initial_file_path
        self.evaluation_result = evaluation_result
        self.stages: List[Type[ProcessingStage]] = [
            DenoisingStage,
            ClickPopRemovalStage,
            SilenceAndStabAdjustmentStage,
            MetadataUpdateStage
        ]

    def run(self, output_dir: str) -> Tuple[str, str]:
        """
        Runs the full perfection workflow.
        Returns a tuple: (path_to_final_perfected_file, path_to_working_directory_for_intermediates).
        """
        if not os.path.exists(self.initial_file_path):
            raise FileNotFoundError(f"Initial file not found: {self.initial_file_path}")

        # Create a unique working directory for this run
        base_filename = os.path.splitext(os.path.basename(self.initial_file_path))[0]
        run_working_dir = os.path.join(output_dir, f"{base_filename}_processing_intermediates")
        if not os.path.exists(run_working_dir):
            os.makedirs(run_working_dir, exist_ok=True)

        print(f"Starting Vocal Chop Perfection Workflow for: {self.initial_file_path}")
        print(f"Intermediate files will be stored in: {run_working_dir}")

        current_file_path = self.initial_file_path

        for stage_class in self.stages:
            stage_instance = stage_class(working_dir=run_working_dir)
            try:
                current_file_path = stage_instance.process(current_file_path, self.evaluation_result)
                print(f"Finished stage: {stage_instance.stage_name}, output: {current_file_path}")
            except Exception as e:
                print(f"Error during stage {stage_instance.stage_name}: {e}")
                # Decide if workflow should stop or continue with the last successful output
                print(f"Workflow halted due to error in stage {stage_instance.stage_name}.")
                return current_file_path, run_working_dir # Return last successfully processed file

        # Copy the final processed file to a "perfected" name in the main output_dir
        final_perfected_filename = f"{base_filename}_perfected.wav"
        final_output_path = os.path.join(output_dir, final_perfected_filename)

        try:
            shutil.copy(current_file_path, final_output_path)
            print(f"Successfully perfected vocal chop. Final output: {final_output_path}")
        except Exception as e:
            print(f"Error copying final perfected file from {current_file_path} to {final_output_path}: {e}")
            # Return the last intermediate if final copy fails
            return current_file_path, run_working_dir

        return final_output_path, run_working_dir

# Example Usage (for testing purposes, if run directly)
if __name__ == '__main__':
    # This is a placeholder for a real VocalChopEvaluationResult
    # In a real scenario, this would be populated by VocalChopEvaluator
    mock_eval_result = VocalChopEvaluationResult(file_path="test.wav")
    mock_eval_result.denoising_recommended = True
    mock_eval_result.click_pop_detected = True
    # ... populate other fields as needed for testing stages

    # Create a dummy test.wav if it doesn't exist
    if not os.path.exists("test.wav"):
        try:
            dummy_audio = np.random.rand(44100 * 2).astype(np.float32) # 2 seconds of noise
            soundfile.write("test.wav", dummy_audio, 44100)
            print("Created dummy test.wav for example usage.")
        except Exception as e:
            print(f"Could not create dummy test.wav: {e}")

    if os.path.exists("test.wav"):
        output_directory = "output_perfection"
        if not os.path.exists(output_directory):
            os.makedirs(output_directory, exist_ok=True)

        workflow = VocalChopPerfectionWorkflow(initial_file_path="test.wav", evaluation_result=mock_eval_result)
        final_file, intermediates_dir = workflow.run(output_dir=output_directory)
        print(f"\nWorkflow finished.")
        print(f"Final perfected file: {final_file}")
        print(f"Intermediate files are in: {intermediates_dir}")
    else:
        print("Skipping example usage as test.wav could not be created/found.")
