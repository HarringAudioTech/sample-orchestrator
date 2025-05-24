"""
Defines the SlicingStage for audio processing pipelines.
This stage is responsible for note detection and slicing of audio files.
"""
Defines the SlicingStage for audio processing pipelines.
This stage is responsible for note detection and slicing of audio files.
"""

import logging
import os
import wave
from typing import Any, Dict, List # Standard library imports first

import librosa # Third-party imports
import numpy as np # librosa often uses numpy arrays
from sqlalchemy.orm import Session # Third-party imports
from sqlalchemy.exc import SQLAlchemyError # For specific exception handling

from src.core.processing_stages import ( # Local application imports
    AudioProcessingStage,
    DATA_TYPE_FILE_PATH,
    DATA_TYPE_LIST_OF_SAMPLE_DATA,
)
from src.core.stage_runner import register_stage
from src.database.models import Recording as RecordingModel, Sample as SampleModel

# Logger for this stage
logger = logging.getLogger(__name__) # Module-level logger


def _get_audio_details_for_slicing(path: str) -> tuple[int, int, int]:
    """
    Internal helper to get samplerate, total frames, and channels for slicing.
    Uses librosa, falls back to wave.
    """
    samplerate, total_frames, channels = 0, 0, 0
    try:
        # librosa.load returns audio time series (y) and sampling rate (sr)
        # We set sr=None to load the original sampling rate.
        y, sr = librosa.load(path, sr=None, mono=False) # mono=False to get actual channel count
        samplerate = sr
        # librosa.get_duration returns duration in seconds. Multiply by sr for total_frames.
        # Or, more directly, use the shape of the loaded audio array.
        if y.ndim == 1:
            channels = 1
            total_frames = len(y)
        else:
            channels = y.shape[0]
            total_frames = y.shape[1]

        if channels == 0:
            logger.warning(
                "Librosa reported 0 channels for %s. Attempting fallback with wave module.", path
            )
            raise RuntimeError("Librosa reported 0 channels.") # Force fallback
        logger.info(
            "Audio details from Librosa for %s: SR=%s, Frames=%s, Channels=%s",
            path, samplerate, total_frames, channels
        )
        return samplerate, total_frames, channels
    except (librosa.LibrosaError, FileNotFoundError, Exception) as e_librosa: # More specific librosa errors
        logger.warning(
            "Error getting full audio details for %s with librosa (%s). Falling back to wave.",
            path, e_librosa, exc_info=True # Added exc_info for better debugging
        )
        try:
            with wave.open(path, "rb") as wf:
                samplerate = wf.getframerate()
                total_frames = wf.getnframes()
                channels = wf.getnchannels()
                logger.info(
                    "Audio details from wave module for %s: SR=%s, Frames=%s, Channels=%s",
                    path, samplerate, total_frames, channels
                )
                return samplerate, total_frames, channels
        except (wave.Error, IOError) as e_wave: # Specific errors for wave
            logger.error(
                "Critical error getting audio details for %s with wave (fallback): %s",
                path, e_wave, exc_info=True,
            )
            # f-string for exception message is fine
            raise ValueError(
                f"Could not determine audio details (samplerate, frames, channels) for {path} "
                "using librosa or wave."
            ) from e_wave


class SlicingStage(AudioProcessingStage):
    """
    An audio processing stage that detects notes in an audio file,
    slices the audio based on these detections, saves each slice as a new
    WAV file, and creates corresponding Sample entries in the database.
    """

    @property
    def name(self) -> str:
        return "slicing"

    @property
    def description(self) -> str:
        return (
            "Detects notes in an audio file, slices them, and saves them as "
            "samples in the database and on disk."
        ) # Wrapped for line length

    @property
    def input_type(self) -> str:
        return DATA_TYPE_FILE_PATH

    @property
    def output_type(self) -> str:
        return DATA_TYPE_LIST_OF_SAMPLE_DATA

    @property
    def default_params(self) -> dict:
        return {
            "hop_size": 256,  # Hop size for aubio analysis
            "window_size": 512,  # FFT window size for aubio analysis
            "silence_threshold_db": -40,  # Silence threshold in dB for note detection
            # Factor for min inter-onset interval (multiplied by
            # hop_size/samplerate)
            "min_ioi_seconds_factor": 2.0,
        }

    def process(
        self, data: str, params: dict, context: dict = None
    ) -> List[Dict[str, Any]]:
        """
        Processes an audio file: detects notes, slices them, and saves them.

        Args:
            data (str): The input audio file path.
            params (dict): Parameters for slicing, merged with defaults.
                           Expected keys: "hop_size", "window_size", "silence_threshold_db", "min_ioi_seconds_factor".
            context (dict, optional): Must contain:
                - `db_session: Session`: SQLAlchemy session.
                - `recording_id: int`: ID of the recording being processed.
                - `project_id: int`: ID of the project this recording belongs to.
                - `output_sample_dir: str`: Base directory to save sample files.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a created sample
                                  (e.g., `[{'id': sample.id, 'file_path': sample.file_path, ...}]`).

        Raises:
            ValueError: If required keys are missing from `context` or if the
                        recording is not found.
            FileNotFoundError: If the input audio file specified by `data` does not exist.
            RuntimeError: If audio processing fails critically (e.g., cannot
                          determine audio details).
            SQLAlchemyError: If database operations fail.
        """
        logger.info(
            "[%s] Stage starting. Input file: %s, Params: %s, Context keys: %s",
            self.name, data, params, list(context.keys() if context else [])
        )

        # --- Validate Context ---
        if not context:
            raise ValueError("Context is required and was not provided.")
        required_context_keys = [
            "db_session",
            "recording_id",
            "project_id",
            "output_sample_dir",
        ]
        for key in required_context_keys:
            if key not in context:
                raise ValueError(f"Missing required key '{key}' in context.")

        db_session: Session = context["db_session"]
        recording_id: int = context["recording_id"]
        # project_id: int = context["project_id"] # Not directly used in this
        # version of slicing logic, but good to have in context
        output_sample_dir: str = context["output_sample_dir"]

        # --- Fetch Recording and Update Status ---
        recording = (
            db_session.query(RecordingModel)
            .filter(RecordingModel.id == recording_id)
            .first()
        )
        if not recording:
            raise ValueError(
                f"Recording with id {recording_id} not found in the database."
            )

        if not os.path.exists(data):
            recording.status = "slicing_failed"
            db_session.commit()
            raise FileNotFoundError(f"Input audio file not found: {data}")

        try:
            recording.status = "slicing_active"
            db_session.commit()
            logger.info("[%s] Recording %s status set to 'slicing_active'.", self.name, recording_id)
        except SQLAlchemyError as e_db_status:
            db_session.rollback()
            logger.error("[%s] DB error setting recording %s to active: %s", self.name, recording_id, e_db_status, exc_info=True)
            raise RuntimeError(f"Database error when starting slicing for recording {recording_id}") from e_db_status


        created_samples_info = []
        try:
            # --- Audio Details ---
            samplerate, total_frames_in_source, num_channels = _get_audio_details_for_slicing(data)
            if samplerate == 0 or num_channels == 0:
                # f-string for exception message is fine
                error_msg = (
                    f"Could not determine valid samplerate ({samplerate}Hz) or "
                    f"channels ({num_channels}) for {data}."
                )
                logger.error("[%s] %s", self.name, error_msg)
                raise RuntimeError(error_msg)

            # --- Librosa Setup for Onset Detection ---
            hop_length = params.get("hop_size", self.default_params["hop_size"])
            # Other params like window_size and silence_threshold_db might need different handling or mapping.
            # Librosa's onset detection can be tuned with parameters like `backtrack`, `pre_avg`, `post_avg`, `wait`, etc.
            # For simplicity, we'll use defaults for some of these or adapt from aubio if direct parallels exist.
            # The 'silence_threshold_db' is not directly used in librosa.onset.onset_detect in the same way.
            # Onset strength can be used, or pre-processing to remove silence if needed.
            # min_ioi_seconds_factor needs to be converted to samples for librosa's `wait` parameter (in samples).

            # Load audio with librosa. Use original samplerate.
            # For onset detection, it's common to use a mono signal.
            y, sr = librosa.load(data, sr=samplerate, mono=True)
            actual_samplerate = sr # Samplerate from librosa loading
            # total_frames_in_loaded_audio = len(y) # This variable was unused. 'y' is used directly.

            # Calculate min_ioi in samples for librosa's `wait` parameter in onset_detect
            # This is an approximation of aubio's minioi logic.
            min_ioi_seconds = (
                hop_length
                * params.get(
                    "min_ioi_seconds_factor",
                    self.default_params["min_ioi_seconds_factor"],
                )
            ) / float(actual_samplerate)
            wait_samples = int(min_ioi_seconds * actual_samplerate / hop_length) # wait expects units of hops

            # --- Onset Detection ---
            # librosa.onset.onset_detect returns frame indices of onsets
            # Units for onset_frames is in hop_length, so multiply by hop_length to get actual frame index
            onset_frames_indices = librosa.onset.onset_detect(
                y=y,
                sr=actual_samplerate,
                hop_length=hop_length,
                units='frames',
                wait=wait_samples, # wait this many hops before detecting another onset
                # backtrack=True, # Backtrack to find the local minimum of energy before an onset
            )

            detected_notes_list = []
            for onset_frame_index in onset_frames_indices:
                # onset_frame_index is already in terms of frames if units='frames'
                # For consistency with previous logic, we'll store "start_frame".
                # Librosa's onset_detect doesn't give MIDI pitch or velocity.
                # We'll assign a default or placeholder if these were essential.
                # For now, focusing on slicing by onsets.
                detected_notes_list.append(
                    {
                        "midi_pitch": 0,  # Placeholder, librosa onsets don't provide pitch
                        "velocity": 100, # Placeholder
                        "start_frame": onset_frame_index,
                    }
                )
            
            # frames_read_count in aubio context was total frames processed by aubio loop.
            # Here, total_frames_in_source from _get_audio_details_for_slicing (or total_frames_in_loaded_audio)
            # Should use total_frames_in_source from original multi-channel file for boundary checks.
            logger.info("[%s] Detected %d onsets in recording %s.",
                self.name, len(detected_notes_list), recording_id)

            # --- Estimate End Frames ---
            # Using enumerate as suggested by `consider-using-enumerate`
            for i, note_item in enumerate(detected_notes_list):
                current_note_start = note_item["start_frame"]
                if i + 1 < len(detected_notes_list):
                    next_note_start = detected_notes_list[i + 1]["start_frame"]
                    note_item["end_frame"] = max(current_note_start, next_note_start - 1)
                else:
                    # Estimate end: current start + 1 second, capped by total frames of original audio
                    estimated_end = current_note_start + actual_samplerate  # Approx 1s duration in frames
                    note_item["end_frame"] = min(estimated_end, total_frames_in_source)
            
            # --- Slicing and Saving ---
            if not os.path.exists(output_sample_dir):
                try:
                    os.makedirs(output_sample_dir)
                    logger.info("[%s] Created sample output directory: %s", self.name, output_sample_dir)
                except OSError as e_mkdir:
                    logger.error("[%s] Failed to create output directory %s: %s", self.name, output_sample_dir, e_mkdir, exc_info=True)
                    raise RuntimeError(f"Failed to create output directory {output_sample_dir}") from e_mkdir


            sample_filename_counters: Dict[int, int] = {} # Type hint for clarity
            for note_info in detected_notes_list: # Consider renaming note_info for clarity if it's just onset_info
                midi_pitch = note_info["midi_pitch"] # This is a placeholder (0)
                start_frame = note_info["start_frame"]
                # Ensure end_frame exists (already handled by estimation logic)
                end_frame = note_info["end_frame"] # No default needed here due to prior estimation loop

                if end_frame <= start_frame:
                    logger.warning(
                        "[%s] Skipping MIDI %s (placeholder) due to invalid frame range "
                        "(start: %s, end: %s).",
                        self.name, midi_pitch, start_frame, end_frame)
                    continue

                # Ensure frames are within bounds of the source audio
                start_frame = max(0, start_frame)
                end_frame = min(total_frames_in_source, end_frame)
                
                slice_duration_frames = end_frame - start_frame

                if slice_duration_frames <= 0:
                    logger.warning(
                        "[%s] Skipping MIDI %s (placeholder) due to zero/negative duration "
                        "after boundary checks (start: %s, end: %s, duration: %s).",
                        self.name, midi_pitch, start_frame, end_frame, slice_duration_frames)
                    continue

                count = sample_filename_counters.get(midi_pitch, 0) + 1
                sample_filename_counters[midi_pitch] = count
                sample_filename = (
                    f"rec_{recording_id}_sample_midi{midi_pitch}_v{note_info['velocity']}_{count}.wav")
                output_sample_path = os.path.join(
                    output_sample_dir, sample_filename)

                try:
                    with wave.open(
                        data, "rb"
                    ) as wf_in:  # 'data' is the input file path
                        wf_in.setpos(start_frame)
                        slice_audio_data = wf_in.readframes(
                            slice_duration_frames)

                        # Use original file's channels for saving slice
                        # _get_audio_details_for_slicing returns channels from
                        # original file
                        slice_channels = num_channels

                        with wave.open(output_sample_path, "wb") as wf_out:
                            wf_out.setnchannels(slice_channels)
                            wf_out.setsampwidth(wf_in.getsampwidth())
                            wf_out.setframerate(actual_samplerate) # Use samplerate from librosa processing
                            wf_out.writeframes(slice_audio_data)
                        logger.info("[%s] Saved sample: %s", self.name, output_sample_path)
                except (wave.Error, IOError) as e_slice: # Specific errors for wave/IO
                    logger.error(
                        "[%s] Error slicing/saving sample for MIDI %s (frames %s-%s): %s",
                        self.name, midi_pitch, start_frame, end_frame, e_slice, exc_info=True,
                    )
                    continue
                except Exception as e_generic_slice: # Catch other unexpected errors during slice
                    logger.error(
                        "[%s] Unexpected error slicing/saving for MIDI %s (frames %s-%s): %s",
                        self.name, midi_pitch, start_frame, end_frame, e_generic_slice, exc_info=True,
                    )
                    continue
                
                # Construct metadata string carefully to avoid overly long lines
                metadata_dict = {
                    "velocity": note_info["velocity"],
                    "source_start_frame": start_frame,
                    "source_end_frame": end_frame
                }
                # Convert dict to string, e.g. using simplejson or json.dumps if complex chars expected
                # For this case, a simple string representation of dict is used.
                metadata_json_str = str(metadata_dict).replace("'", '"')


                new_sample_db = SampleModel(
                    recording_id=recording_id,
                    name=sample_filename,
                    file_path=os.path.abspath(output_sample_path),
                    start_time_seconds=float(start_frame) / actual_samplerate,
                    end_time_seconds=float(end_frame) / actual_samplerate,
                    sample_type="one-shot", # This could be a parameter or Enum
                    midi_pitch=midi_pitch,
                    metadata_json=metadata_json_str,
                )
                db_session.add(new_sample_db)
                db_session.flush() # Flush to get ID for the dict
                created_samples_info.append(
                    {
                        "id": new_sample_db.id,
                        "file_path": new_sample_db.file_path,
                        "name": new_sample_db.name,
                        "midi_pitch": new_sample_db.midi_pitch,
                        "start_time_seconds": new_sample_db.start_time_seconds,
                        "end_time_seconds": new_sample_db.end_time_seconds,
                        "metadata": new_sample_db.metadata_json,
                    }
                )

            recording.status = "slicing_completed" # Final status
            logger.info(
                "[%s] Slicing completed for recording %s. %d samples created.",
                self.name, recording_id, len(created_samples_info)
            )

        except FileNotFoundError as e_fnf: # Specific catch
            logger.error("[%s] File not found during processing: %s", self.name, e_fnf, exc_info=True)
            recording.status = "slicing_failed"
            raise # Re-raise to be caught by stage_runner
        except ValueError as e_val: # Specific catch (e.g. context issues, audio detail issues)
            logger.error("[%s] ValueError during processing: %s", self.name, e_val, exc_info=True)
            recording.status = "slicing_failed"
            raise
        except RuntimeError as e_rt: # Specific catch (e.g. critical processing errors)
            logger.error("[%s] RuntimeError during processing: %s", self.name, e_rt, exc_info=True)
            recording.status = "slicing_failed"
            db_session.commit() # Commit status change before re-raising
            raise
        except SQLAlchemyError as e_db:
            logger.error(
                "[%s] SQLAlchemyError during processing for recording %s: %s",
                self.name, recording_id, e_db, exc_info=True
            )
            recording.status = "slicing_failed"
            db_session.rollback()
            db_session.commit() # Commit status change after rollback
            raise RuntimeError(f"Database error during slicing for recording {recording_id}") from e_db
        except Exception as e_main:
            logger.error(
                "[%s] Unexpected error during slicing for recording %s: %s",
                self.name, recording_id, e_main, exc_info=True
            )
            recording.status = "slicing_failed"
            # Attempt to commit status before re-raising
            try:
                db_session.commit()
            except Exception: # pylint: disable=broad-exception-caught
                # If committing status also fails, log it but proceed with original error
                logger.error("[%s] Failed to commit 'slicing_failed' status for recording %s during exception handling.",
                             self.name, recording_id, exc_info=True)
            raise RuntimeError(f"Slicing failed unexpectedly for recording {recording_id}") from e_main
        # 'finally' block for db_session.commit() was removed as commits are now handled
        # within each exception block or after successful completion of the try block.
        # This ensures that the 'slicing_failed' status is committed before re-raising.
        # If processing is successful, commit happens implicitly with recording.status = "slicing_completed".

        return created_samples_info


# Register the stage when this module is imported
# Register the stage when this module is imported
try:
    register_stage(SlicingStage)
except Exception as e_register: # Catch broad exception during registration
    # Log error if registration fails
    logger.critical("Failed to register SlicingStage: %s", e_register, exc_info=True)
