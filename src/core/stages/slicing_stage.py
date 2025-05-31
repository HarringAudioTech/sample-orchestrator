"""
Defines the SlicingStage for audio processing pipelines.
This stage is responsible for note detection and slicing of audio files.
"""

import os
import wave
import logging
from typing import Any, Dict, List
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
    def default_params(self) -> dict:
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

    def process(self, data: str, params: dict, context: dict = None) -> List[Dict[str, Any]]:
        """
        Processes an audio file: detects onsets, slices them, and saves them.

        Args:
            data (str): The input audio file path.
            params (dict): Parameters for slicing. Expected keys:
                           "librosa_onset_params" (dict for librosa.onset.onset_detect),
                           "min_sample_length_ms", "max_sample_length_ms".
            context (dict, optional): Must contain:
                - `db_session: Session`: SQLAlchemy session.
                - `recording_id: int`: ID of the recording being processed.
                - `project_id: int`: ID of the project this recording belongs to.
                - `output_sample_dir: str`: Base directory to save sample files.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a created sample.

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
        required_context_keys = ["db_session", "recording_id", "project_id", "output_sample_dir"]
        for key in required_context_keys:
            if key not in context:
                raise ValueError(f"Missing required key '{key}' in context.")

        db_session: Session = context["db_session"]
        recording_id: int = context["recording_id"]
        output_sample_dir: str = context["output_sample_dir"]

        recording = (
            db_session.query(RecordingModel).filter(RecordingModel.id == recording_id).first()
        )
        if not recording:
            raise ValueError(f"Recording with id {recording_id} not found in the database.")

        if not os.path.exists(data):
            recording.status = "slicing_failed"
            db_session.commit()
            raise FileNotFoundError(f"Input audio file not found: {data}")

        recording.status = "slicing_active"
        db_session.commit()
        logger.info(f"[{self.name}] Recording {recording_id} status set to 'slicing_active'.")

        created_samples_info = []
        try:
            y, sr = librosa.load(data, sr=None, mono=True)
            total_samples = len(y)
            actual_samplerate = sr

            # Update recording model with actual samplerate if it was unknown or different
            if recording.samplerate != actual_samplerate:

                logger.info(
                    f"[{self.name}] Updating recording {recording_id} samplerate from {recording.samplerate} to {actual_samplerate}."
                )
                recording.samplerate = actual_samplerate
                # Duration might also change if it was based on old samplerate
                recording.duration_seconds = librosa.get_duration(y=y, sr=sr)

            # Merge user params with stage defaults for librosa_onset_params
            default_onset_params = self.default_params.get("librosa_onset_params", {})
            user_onset_params = params.get("librosa_onset_params", {})
            final_onset_params = {**default_onset_params, **user_onset_params}

            # Ensure units is 'samples' for direct use, or convert if 'frames'
            if final_onset_params.get("units") == "frames":
                # If users provide 'frames', they must also provide 'hop_length' or accept default
                hop_length = final_onset_params.get(
                    "hop_length", 512
                )  # librosa default hop_length for onset_detect
                onset_event_indices = librosa.onset.onset_detect(
                    y=y, sr=sr, **final_onset_params
                )
                onset_samples = librosa.frames_to_samples(
                    onset_event_indices, hop_length=hop_length
                )
            else:  # Assume units are 'samples' or librosa handles it if not 'frames'
                final_onset_params["units"] = "samples"  # Ensure it is samples
                onset_samples = librosa.onset.onset_detect(y=y, sr=sr, **final_onset_params)

            logger.info(
                f"[{self.name}] Detected {len(onset_samples)} onsets in recording {recording_id}."
            )

            if not onset_samples.any():
                recording.status = "slicing_completed"  # No onsets is a valid completed state
                logger.info(f"[{self.name}] No onsets found for recording {recording_id}.")
                db_session.commit()
                return []

            if not os.path.exists(output_sample_dir):
                os.makedirs(output_sample_dir)
                logger.info(f"[{self.name}] Created sample output directory: {output_sample_dir}")

            min_len_samples = int(
                params.get("min_sample_length_ms", self.default_params["min_sample_length_ms"])
                / 1000
                * sr
            )
            max_len_samples = int(
                params.get("max_sample_length_ms", self.default_params["max_sample_length_ms"])
                / 1000
                * sr
            )

            for i, start_sample_idx in enumerate(onset_samples):
                start_sample = int(start_sample_idx)  # Ensure integer

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

                slice_duration_samples = end_sample - start_sample

                if slice_duration_samples < min_len_samples:
                    logger.debug(
                        f"[{self.name}] Skipping sample {i+1} (onset at {start_sample}) due to short duration ({slice_duration_samples} < {min_len_samples} samples)."
                    )
                    continue

                audio_slice = y[start_sample:end_sample]

                # Using onset index for filename for uniqueness, can be improved
                sample_filename = f"rec_{recording_id}_sample_{i+1}_onset_S{start_sample}.wav"
                output_sample_path = os.path.join(output_sample_dir, sample_filename)

                try:
                    sf.write(output_sample_path, audio_slice, actual_samplerate)
                    logger.info(f"[{self.name}] Saved sample: {output_sample_path}")
                except Exception as e_slice:
                    logger.error(
                        f"[{self.name}] Error saving sample slice (samples {start_sample}-{end_sample}): {e_slice}",
                        exc_info=True,
                    )
                    continue  # Skip this sample

                new_sample_db = SampleModel(
                    recording_id=recording_id,
                    name=sample_filename,
                    file_path=os.path.abspath(output_sample_path),
                    start_time_seconds=float(start_sample) / actual_samplerate,
                    end_time_seconds=float(end_sample) / actual_samplerate,
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
                        "metadata": new_sample_db.metadata_json,
                    }
                )

            recording.status = "slicing_completed"
            logger.info(
                f"[{self.name}] Slicing completed for recording {recording_id}. {len(created_samples_info)} samples created."
            )

        except (
            FileNotFoundError
            # Should be caught before this block by os.path.exists(data)
        ) as fnf_error:
            logger.error(
                f"[{self.name}] File not found during processing: {fnf_error}",
                exc_info=True,
            )
            recording.status = "slicing_failed"
            raise
        except ValueError as val_error:  # Catch ValueErrors like missing context keys
            logger.error(
                f"[{self.name}] ValueError during processing: {val_error}",
                exc_info=True,
            )
            recording.status = "slicing_failed"
            raise
        except (
            RuntimeError
        ) as rt_error:  # Catch critical errors like inability to get audio details
            logger.error(
                f"[{self.name}] Runtime error during processing: {rt_error}",
                exc_info=True,
            )
            recording.status = "slicing_failed"
            raise
        except Exception as e:
            logger.error(
                f"[{self.name}] Unexpected error during slicing for recording {recording_id}: {e}",
                exc_info=True,
            )
            recording.status = "slicing_failed"
            # Re-raise to allow stage_runner to catch it
            raise RuntimeError(
                f"Slicing failed for recording {recording_id} due to: {e}"
            ) from e
        finally:
            db_session.commit()  # Commit final status and any created samples

        return created_samples_info


# Register the stage when this module is imported
try:
    register_stage(SlicingStage)
except Exception as e:
    # Log error if registration fails, e.g., if stage_runner.py is not loaded correctly
    # or if AudioProcessingStage is not fully defined.
    logger.critical(f"Failed to register SlicingStage: {e}", exc_info=True)
