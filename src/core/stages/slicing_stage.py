"""
Defines the SlicingStage for audio processing pipelines.
This stage is responsible for note detection and slicing of audio files.
"""

import os

# import wave # Not directly used, librosa/soundfile handle wave operations
import logging
from typing import Any, Dict, List, Optional  # Added Optional
from sqlalchemy.orm import Session

from src.core.processing_stages import (
    AudioProcessingStage,
    DATA_TYPE_FILE_PATH,
    DATA_TYPE_LIST_OF_SAMPLE_DATA,
)
from src.core.stage_runner import register_stage
from src.database.models import Recording as RecordingModel, Sample as SampleModel

# Project model might not be needed directly if project_id is passed in context.

# Import for audio processing
import librosa
import soundfile as sf
import numpy as np

# Logger for this stage
logger = logging.getLogger(__name__)

# _get_audio_details_for_slicing function removed as librosa.load handles this.


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
        return "Detects notes in an audio file, slices them, and saves them as samples in the database and on disk."

    @property
    def input_type(self) -> str:
        return DATA_TYPE_FILE_PATH

    @property
    def output_type(self) -> str:
        return DATA_TYPE_LIST_OF_SAMPLE_DATA

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "librosa_onset_params": {
                "hop_length": 512,
                "backtrack": False,
                "units": "samples",  # Using samples directly for easier indexing with y
                # Default librosa values for other common params if not specified by user:
                # wait_samples, pre_avg_samples, post_avg_samples, pre_max_samples, post_max_samples, delta_db
                # These will be merged with user-provided librosa_onset_params
            },
            "min_sample_length_ms": 50,  # Minimum duration for a slice to be saved
            "max_sample_length_ms": 10000,  # Maximum duration for a slice
        }

    def process(
        self,
        data: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Processes an audio file: detects onsets, slices them, and saves them.

        Args:
            data: The input audio file path.
            params: Parameters for slicing. Expected keys:
                           "librosa_onset_params" (dict for librosa.onset.onset_detect),
                           "min_sample_length_ms", "max_sample_length_ms".
            context: Must contain:
                - `db_session: Session`: SQLAlchemy session.
                - `recording_id: int`: ID of the recording being processed.
                - `project_id: int`: ID of the project this recording belongs to.
                - `output_sample_dir: str`: Base directory to save sample files.

        Returns:
            A list of dictionaries, each representing a created sample.

        Raises:
            ValueError: If required keys are missing from `context` or if the recording is not found.
            FileNotFoundError: If the input audio file specified by `data` does not exist.
            RuntimeError: If audio processing fails critically.
        """
        logger.info(
            f"[{self.name}] Stage starting. Input file: {data}, Params: {params}, Context keys: {list(context.keys() if context else [])}"
        )

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
        output_sample_dir: str = context["output_sample_dir"]
        # project_id: int = context["project_id"] # Currently unused directly by stage logic but good for context

        recording: Optional[RecordingModel] = (
            db_session.query(RecordingModel)
            .filter(RecordingModel.id == recording_id)
            .first()
        )
        if (
            not recording
        ):  # Should be RecordingModel | None from query, so check for None
            # This is a critical error, as we need the recording to associate samples.
            # No db commit needed here as it's a read operation that failed to find the target.
            raise ValueError(
                f"Recording with id {recording_id} not found in the database."
            )

        if not os.path.exists(data):
            recording.status = "slicing_failed"
            db_session.commit()  # Commit status change
            raise FileNotFoundError(f"Input audio file not found: {data}")

        recording.status = "slicing_active"
        db_session.commit()  # Commit status change
        logger.info(
            f"[{self.name}] Recording {recording_id} status set to 'slicing_active'."
        )

        created_samples_info: List[Dict[str, Any]] = []
        try:
            y: np.ndarray
            sr: int
            y, sr = librosa.load(data, sr=None, mono=True)  # type: ignore # librosa.load can return tuple
            total_samples: int = len(y)
            actual_samplerate: int = sr

            # Update recording model with actual samplerate if it was unknown or different
            if recording.samplerate != actual_samplerate:
                logger.info(
                    f"[{self.name}] Updating recording {recording_id} samplerate from {recording.samplerate} to {actual_samplerate}."
                )
                recording.samplerate = actual_samplerate
                # Duration might also change if it was based on old samplerate
                recording.duration_seconds = librosa.get_duration(y=y, sr=sr)  # type: ignore

            # Merge user params with stage defaults for librosa_onset_params
            default_onset_params: Dict[str, Any] = self.default_params.get("librosa_onset_params", {})  # type: ignore
            user_onset_params: Dict[str, Any] = params.get("librosa_onset_params", {})
            final_onset_params: Dict[str, Any] = {
                **default_onset_params,
                **user_onset_params,
            }

            # Ensure units is 'samples' for direct use
            final_onset_params["units"] = "samples"
            onset_samples: np.ndarray = librosa.onset.onset_detect(
                y=y, sr=sr, **final_onset_params
            )

            logger.info(
                f"[{self.name}] Detected {len(onset_samples)} onsets in recording {recording_id}."
            )

            if not onset_samples.any():
                recording.status = (
                    "slicing_completed"  # No onsets is a valid completed state
                )
                logger.info(
                    f"[{self.name}] No onsets found for recording {recording_id}."
                )
                db_session.commit()  # Commit status change
                return []

            if not os.path.exists(output_sample_dir):
                os.makedirs(output_sample_dir)
                logger.info(
                    f"[{self.name}] Created sample output directory: {output_sample_dir}"
                )

            min_len_samples: int = int(
                params.get("min_sample_length_ms", self.default_params.get("min_sample_length_ms"))  # type: ignore
                / 1000
                * sr
            )
            max_len_samples: int = int(
                params.get("max_sample_length_ms", self.default_params.get("max_sample_length_ms"))  # type: ignore
                / 1000
                * sr
            )

            for i, start_sample_idx_float in enumerate(onset_samples):
                start_sample: int = int(start_sample_idx_float)  # Ensure integer

                end_sample: int
                if i + 1 < len(onset_samples):
                    end_sample = int(onset_samples[i + 1])  # Ensure integer
                else:
                    end_sample = total_samples

                # Apply max length constraint relative to start_sample
                if (start_sample + max_len_samples) < end_sample:
                    end_sample = start_sample + max_len_samples
                end_sample = min(
                    end_sample, total_samples
                )  # Ensure it doesn't exceed audio length

                slice_duration_samples: int = end_sample - start_sample

                if slice_duration_samples < min_len_samples:
                    logger.debug(
                        f"[{self.name}] Skipping sample {i+1} (onset at {start_sample}) due to short duration ({slice_duration_samples} < {min_len_samples} samples)."
                    )
                    continue

                audio_slice: np.ndarray = y[start_sample:end_sample]

                # Using onset index for filename for uniqueness, can be improved
                sample_filename: str = (
                    f"rec_{recording_id}_sample_{i+1}_onset_S{start_sample}.wav"
                )
                output_sample_path: str = os.path.join(
                    output_sample_dir, sample_filename
                )

                try:
                    sf.write(output_sample_path, audio_slice, actual_samplerate)
                    logger.info(f"[{self.name}] Saved sample: {output_sample_path}")
                except Exception as e_slice:
                    logger.error(
                        f"[{self.name}] Error saving sample slice (samples {start_sample}-{end_sample}): {e_slice}",
                        exc_info=True,
                    )
                    continue  # Skip this sample

                new_sample_db: SampleModel = SampleModel(
                    recording_id=recording_id,
                    name=sample_filename,
                    file_path=os.path.abspath(output_sample_path),
                    start_time_seconds=float(start_sample) / actual_samplerate,  # type: ignore
                    end_time_seconds=float(end_sample) / actual_samplerate,  # type: ignore
                    sample_type="one-shot",  # Default or make configurable
                    midi_pitch=None,  # Librosa onsets don't directly give MIDI pitch
                    metadata_json=f'{{"source_onset_samples": {start_sample}}}',
                )
                db_session.add(new_sample_db)
                db_session.flush()  # Flush to get ID for the dict, commit happens at the end
                created_samples_info.append(
                    {
                        "id": new_sample_db.id,
                        "file_path": new_sample_db.file_path,
                        "name": new_sample_db.name,
                        "midi_pitch": new_sample_db.midi_pitch,
                        "start_time_seconds": new_sample_db.start_time_seconds,
                        "end_time_seconds": new_sample_db.end_time_seconds,
                        "metadata_json": new_sample_db.metadata_json,
                    }
                )

            recording.status = "slicing_completed"
            logger.info(
                f"[{self.name}] Slicing completed for recording {recording_id}. {len(created_samples_info)} samples created."
            )

        except (
            FileNotFoundError
        ) as fnf_error:  # Already checked, but good for safety during librosa.load
            logger.error(
                f"[{self.name}] File not found during librosa.load (should have been caught earlier): {fnf_error}",
                exc_info=True,
            )
            if recording:
                recording.status = "slicing_failed"
            raise
        except (
            ValueError
        ) as val_error:  # Catch ValueErrors like missing context keys or DB issues
            logger.error(
                f"[{self.name}] ValueError during processing for recording {recording_id}: {val_error}",
                exc_info=True,
            )
            if recording:
                recording.status = "slicing_failed"
            raise
        except (
            RuntimeError
        ) as rt_error:  # Catch critical errors from audio processing libraries
            logger.error(
                f"[{self.name}] Runtime error during processing for recording {recording_id}: {rt_error}",
                exc_info=True,
            )
            if recording:
                recording.status = "slicing_failed"
            raise
        except Exception as e:  # Catch-all for other unexpected errors
            logger.error(
                f"[{self.name}] Unexpected error during slicing for recording {recording_id}: {e}",
                exc_info=True,
            )
            if recording:
                recording.status = "slicing_failed"
            # Re-raise to allow stage_runner to catch it
            raise RuntimeError(
                f"Slicing failed for recording {recording_id} due to an unexpected error: {e}"
            ) from e
        finally:
            # Ensure session commit happens to save status changes and any samples if processing partway.
            # If an error occurred before `recording` was fetched, `recording` might be None.
            if recording and db_session:  # Ensure db_session is also valid
                db_session.commit()
                logger.debug(
                    f"[{self.name}] Final db_session.commit() called for recording {recording_id}."
                )

        return created_samples_info


# Register the stage when this module is imported
try:
    register_stage(SlicingStage)
except Exception as e:
    # Log error if registration fails, e.g., if stage_runner.py is not loaded correctly
    # or if AudioProcessingStage is not fully defined.
    logger.critical(f"Failed to register SlicingStage: {e}", exc_info=True)
