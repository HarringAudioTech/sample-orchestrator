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

# Project model might not be needed directly if project_id is passed in
# context.

# Import aubio for audio processing
from aubio import source as aubio_source, notes as aubio_notes

# Logger for this stage
logger = logging.getLogger(__name__)


def _get_audio_details_for_slicing(path: str) -> tuple[int, int, int]:
    """
    Internal helper to get samplerate, total frames, and channels for slicing.
    Prioritizes aubio, falls back to wave.
    """
    samplerate, total_frames, channels = 0, 0, 0
    try:
        s = aubio_source(path, 0, 512)  # samplerate=0 means use original
        samplerate = s.samplerate
        total_frames = s.duration  # total frames for aubio source
        channels = s.channels
        if (
            channels == 0
        ):  # Aubio might return 0 channels for some files it can't fully parse
            logger.warning(
                f"Aubio reported 0 channels for {path}. Attempting fallback with wave module.")
            raise RuntimeError("Aubio reported 0 channels.")  # Force fallback
        logger.info(
            f"Audio details from Aubio for {path}: SR={samplerate}, Frames={total_frames}, Channels={channels}"
        )
        return samplerate, total_frames, channels
    except Exception as e_aubio:
        logger.warning(
            f"Error getting full audio details for {path} with aubio ({e_aubio}). Falling back to wave module.")
        try:
            with wave.open(path, "rb") as wf:
                samplerate = wf.getframerate()
                total_frames = wf.getnframes()
                channels = wf.getnchannels()
                logger.info(
                    f"Audio details from wave module for {path}: SR={samplerate}, Frames={total_frames}, Channels={channels}")
                return samplerate, total_frames, channels
        except Exception as e_wave:
            logger.error(
                f"Critical error getting audio details for {path} with wave (fallback): {e_wave}",
                exc_info=True,
            )
            raise ValueError(
                f"Could not determine audio details (samplerate, frames, channels) for {path} using aubio or wave."
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
            ValueError: If required keys are missing from `context` or if the recording is not found.
            FileNotFoundError: If the input audio file specified by `data` does not exist.
            RuntimeError: If audio processing fails critically (e.g., cannot determine audio details).
        """
        logger.info(
            f"[{self.name}] Stage starting. Input file: {data}, Params: {params}, Context keys: {list(context.keys() if context else [])}"
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

        recording.status = "slicing_active"
        db_session.commit()
        logger.info(
            f"[{self.name}] Recording {recording_id} status set to 'slicing_active'."
        )

        created_samples_info = []
        try:
            # --- Audio Details ---
            # This stage needs its own way to get samplerate, frames, channels
            samplerate, total_frames_in_source, num_channels = (
                _get_audio_details_for_slicing(data)
            )
            if (
                samplerate == 0 or num_channels == 0
            ):  # total_frames_in_source could be 0 for empty file
                raise RuntimeError(
                    f"Could not determine valid samplerate ({samplerate}Hz) or channels ({num_channels}) for {data}.")

            # --- Aubio Setup ---
            hop_size = params.get("hop_size", self.default_params["hop_size"])
            win_size = params.get(
                "window_size", self.default_params["window_size"]
            )  # May not be used by 'default' notes method

            audio_source_obj = aubio_source(data, samplerate, hop_size)
            # Aubio might adjust samplerate if it was 0 initially, so
            # re-assign.
            actual_samplerate = audio_source_obj.samplerate

            notes_obj = aubio_notes(
                "default", win_size, hop_size, actual_samplerate)
            notes_obj.set_param(
                "silence",
                params.get(
                    "silence_threshold_db",
                    self.default_params["silence_threshold_db"]),
            )
            min_ioi_calc = (
                hop_size
                * params.get(
                    "min_ioi_seconds_factor",
                    self.default_params["min_ioi_seconds_factor"],
                )
            ) / float(actual_samplerate)
            notes_obj.set_param("minioi", min_ioi_calc)

            # --- Note Detection Loop ---
            detected_notes_list = []
            frames_read_count = 0
            while True:
                samples, read = audio_source_obj()
                new_note_events = notes_obj(samples)
                for note_event in new_note_events:
                    onset_frame = (
                        frames_read_count - read +
                        int(notes_obj.get_last_pos())
                    )
                    detected_notes_list.append(
                        {
                            "midi_pitch": int(note_event[0]),
                            "velocity": int(note_event[1]),
                            "start_frame": onset_frame,
                        }
                    )
                frames_read_count += read
                if read < hop_size:
                    break

            logger.info(
                f"[{self.name}] Detected {len(detected_notes_list)} potential notes in recording {recording_id}."
            )

            # --- Estimate End Frames ---
            for i in range(len(detected_notes_list)):
                current_note_start = detected_notes_list[i]["start_frame"]
                if i + 1 < len(detected_notes_list):
                    next_note_start = detected_notes_list[i + 1]["start_frame"]
                    detected_notes_list[i]["end_frame"] = max(
                        current_note_start, next_note_start - 1
                    )
                else:
                    estimated_end = (
                        current_note_start + actual_samplerate
                    )  # Approx 1s duration
                    detected_notes_list[i]["end_frame"] = min(
                        estimated_end, frames_read_count
                    )

            # --- Slicing and Saving ---
            if not os.path.exists(output_sample_dir):
                os.makedirs(output_sample_dir)
                logger.info(
                    f"[{self.name}] Created sample output directory: {output_sample_dir}"
                )

            sample_filename_counters = {}
            for note_info in detected_notes_list:
                midi_pitch = note_info["midi_pitch"]
                start_frame = note_info["start_frame"]
                end_frame = note_info.get(
                    "end_frame", start_frame + actual_samplerate)

                if end_frame <= start_frame:
                    logger.warning(
                        f"[{self.name}] Skipping note MIDI {midi_pitch} due to invalid frame range (start: {start_frame}, end: {end_frame})."
                    )
                    continue

                start_frame = max(0, start_frame)
                end_frame = min(frames_read_count, end_frame)
                slice_duration_frames = end_frame - start_frame

                if slice_duration_frames <= 0:
                    logger.warning(
                        f"[{self.name}] Skipping sample for MIDI {midi_pitch} due to zero/negative duration after boundary checks."
                    )
                    continue

                count = sample_filename_counters.get(midi_pitch, 0) + 1
                sample_filename_counters[midi_pitch] = count
                sample_filename = f"rec_{recording_id}_sample_midi{midi_pitch}_v{
                    note_info['velocity']}_{count}.wav"
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
                            wf_out.setframerate(
                                actual_samplerate
                            )  # Use samplerate from aubio processing
                            wf_out.writeframes(slice_audio_data)
                        logger.info(
                            f"[{self.name}] Saved sample: {output_sample_path}")
                except Exception as e_slice:
                    logger.error(
                        f"[{self.name}] Error slicing/saving sample for MIDI {midi_pitch} (frames {start_frame}-{end_frame}): {e_slice}",
                        exc_info=True,
                    )
                    continue

                new_sample_db = SampleModel(
                    recording_id=recording_id,
                    name=sample_filename,
                    file_path=os.path.abspath(
                        output_sample_path
                    ),  # Store absolute path
                    start_time_seconds=float(start_frame) / actual_samplerate,
                    end_time_seconds=float(end_frame) / actual_samplerate,
                    sample_type="one-shot",
                    midi_pitch=midi_pitch,
                    metadata_json=f'{
                        {"velocity": {
                            note_info["velocity"]}, "source_start_frame": {start_frame}, "source_end_frame": {end_frame}}}',
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
