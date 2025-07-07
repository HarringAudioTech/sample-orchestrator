"""
Defines the SlicingStage for audio processing pipelines.
This stage is responsible for slicing audio files based on predefined slice points.
"""

import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np

# Audio processing imports
import librosa
import soundfile as sf

# Database models
from sqlalchemy.orm import Session

# Local imports
from src.core.processing_stages import AudioProcessingStage, register_stage
from src.database.models import (
    Sample as SampleModel,
    SamplePack,
    Recording as RecordingModel,
    SamplePackStatus,
)
from src.utils.audio_utils import is_test_environment

logger = logging.getLogger(__name__)


class SlicingStage(AudioProcessingStage):
    """
    An audio processing stage that slices audio files based on predefined slice points,
    saves each slice as a new WAV file, and creates corresponding Sample entries in the database.

    This stage expects to receive a list of slice points (start/end times) and will
    create samples based on these points. It does not perform onset detection itself.
    """

    @property
    def name(self) -> str:
        return "slicing"

    @property
    def description(self) -> str:
        return "Slices audio files at specified time points and creates sample entries."

    @property
    def input_type(self) -> str:
        return "file_path"

    @property
    def output_type(self) -> str:
        return "list_of_sample_data"

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "bit_depth": 24,
            "normalize": True,
            "min_sample_length_ms": 100,
            "max_sample_length_ms": 10000,
            "librosa_onset_params": {
                "units": "time",
                "hop_length": 512,
                "backtrack": False,
                "fmin": 20.0,
                "fmax": 8000.0,
                "sr": 44100,
            },
            "sample_type": "one_shot",
            "category": "Uncategorized",
            "output_format": "wav",
        }

    def _load_audio_file(
        self, file_path: str, target_sr: int
    ) -> Tuple[np.ndarray, int]:
        """Load an audio file with the target sample rate."""
        try:
            y, sr = librosa.load(file_path, sr=target_sr, mono=True)
            return (y, int(sr))
        except Exception as e:
            logger.error(f"Error loading audio file {file_path}: {str(e)}")
            raise

    def _save_audio_slice(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        output_path: str,
        bit_depth: int = 24,
        normalize: bool = True,
    ) -> None:
        """Save an audio slice to disk."""
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Convert bit depth to soundfile format
            if bit_depth == 16:
                subtype = "PCM_16"
            elif bit_depth == 24:
                subtype = "PCM_24"
            elif bit_depth == 32:
                subtype = "PCM_32"
            else:
                logger.warning(
                    f"Unsupported bit depth {bit_depth}, defaulting to 24-bit"
                )
                subtype = "PCM_24"

            # Save the audio file
            sf.write(
                output_path,
                audio_data,
                sample_rate,
                subtype=subtype,
                format="WAV",
                endian="LITTLE",
            )

        except Exception as e:
            logger.error(f"Error saving audio slice to {output_path}: {str(e)}")
            raise

    def _create_sample_metadata(
        self,
        recording_id: int,
        file_path: str,
        start_time: float,
        end_time: float,
        sample_rate: int,
        bit_depth: int,
        sample_type: str = "one_shot",
        category: str = "Uncategorized",
        additional_metadata: Optional[Dict[str, Any]] = None,
        sample_pack_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create metadata for a sample."""
        metadata = {
            "recording_id": recording_id,
            "file_path": file_path,
            "start_time": start_time,
            "end_time": end_time,
            "sample_rate": sample_rate,
            "bit_depth": bit_depth,
            "sample_type": sample_type,
            "category": category,
            "sample_pack_id": sample_pack_id,
            "created_at": datetime.now(),
        }

        if additional_metadata:
            metadata.update(additional_metadata)

        return metadata

    def _create_sample_pack(
        self, db_session: Session, project_id: int, name: str, description: str = ""
    ) -> SamplePack:
        """Create a new sample pack for the current project."""
        sample_pack = SamplePack(
            project_id=project_id,
            name=name,
            description=description,
            status="in_progress",
        )
        db_session.add(sample_pack)
        db_session.flush()
        return sample_pack

    def process(
        self,
        data: Union[str, Dict[str, Any]],
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Processes an audio file: slices it and saves the slices.

        Args:
            data: The input audio file path or a dictionary with audio data.
            params: Parameters for slicing. Expected keys:
                "slice_points": List of dicts with "start" and "end" times in seconds.
                "output_format": Output audio format (default: "wav").
                "bit_depth": Bit depth for output audio (default: 24).
                "normalize": Whether to normalize audio (default: True).
                "sample_type": Type of sample (default: "one_shot").
                "category": Sample category (default: "Uncategorized").
            context: Must contain:
                - `db_session`: SQLAlchemy session.
                - `recording_id`: ID of the recording being processed.
                - `project_id`: ID of the project this recording belongs to.
                - `output_sample_dir`: Directory to save output samples.

        Returns:
            A list of dictionaries, each representing a created sample.

        Raises:
            ValueError: If required keys are missing from `context` or if the recording is not found.
            FileNotFoundError: If the input audio file specified by `data` does not exist.
            RuntimeError: If audio processing fails critically.
        """
        from datetime import datetime

        if context is None:
            raise ValueError("Context is required and was not provided.")

        required_context = [
            "db_session",
            "recording_id",
            "project_id",
            "output_sample_dir",
        ]
        missing = [key for key in required_context if key not in context]
        if missing:
            raise ValueError(f"Missing required context keys: {', '.join(missing)}")

        db_session = context["db_session"]
        recording_id = context["recording_id"]
        output_dir = context["output_sample_dir"]
        project_id = context["project_id"]

        # Get recording from database
        recording = db_session.query(RecordingModel).get(recording_id)
        if not recording:
            raise ValueError(f"Recording with id {recording_id} not found")

        # Update recording status
        recording.status = "slicing_active"
        try:
            db_session.commit()
        except Exception as e:
            error_msg = (
                f"Failed to update recording status to 'slicing_active': {str(e)}"
            )
            logger.error(error_msg)
            db_session.rollback()
            raise RuntimeError(error_msg) from e

        # Merge default params with provided params
        if params is None:
            params = {}

        # Get slice points or detect onsets if not provided
        slice_points = params.get("slice_points", [])

        # If no slice points provided, try to detect onsets
        if not slice_points:
            logger.warning("No slice points provided, attempting to detect onsets.")
            try:
                # Load audio file
                if isinstance(data, str):
                    if not os.path.exists(data):
                        raise FileNotFoundError(f"Input audio file not found: {data}")
                    y, sr = self._load_audio_file(
                        data, target_sr=44100
                    )  # Use native sample rate
                else:
                    # Assume data is already loaded audio
                    y = data.get("audio_data")
                    sr = data.get("sample_rate")
                    if y is None or sr is None:
                        raise ValueError(
                            "Invalid audio data format. Expected 'audio_data' and 'sample_rate' keys."
                        )

                # Detect onsets
                onset_frames = librosa.onset.onset_detect(
                    y=y, sr=sr, **params.get("librosa_onset_params", {})
                )
                onset_times = librosa.frames_to_time(onset_frames, sr=sr)

                # Add start and end points if needed
                if (
                    len(onset_times) == 0 or onset_times[0] > 0.1
                ):  # If no onsets or first onset is not at the very start
                    onset_times = np.insert(onset_times, 0, 0.0)

                duration = len(y) / sr
                if (
                    len(onset_times) == 0 or onset_times[-1] < duration - 0.1
                ):  # If no onsets or last onset is not at the end
                    onset_times = np.append(onset_times, duration)

                # Create slice points from onsets
                for i in range(len(onset_times) - 1):
                    slice_points.append(
                        {
                            "start": float(onset_times[i]),
                            "end": float(onset_times[i + 1]),
                        }
                    )

                logger.info(f"Detected {len(slice_points)} slices from audio file.")

            except Exception as e:
                error_msg = f"Failed to detect onsets: {str(e)}"
                logger.error(error_msg)
                try:
                    recording.status = "slicing_failed"
                    db_session.commit()
                except Exception as commit_error:
                    logger.error(
                        f"Failed to update status after onset detection error: {str(commit_error)}"
                    )
                    db_session.rollback()
                raise RuntimeError(error_msg) from e

        if not slice_points:
            logger.warning("No slices to process.")
            try:
                recording.status = "slicing_completed"
                db_session.commit()
                logger.info(
                    "Successfully updated recording status to 'slicing_completed' (no slices)"
                )
                return []
            except Exception as e:
                error_msg = f"Failed to update recording status: {str(e)}"
                logger.error(error_msg)
                db_session.rollback()
                raise RuntimeError(error_msg) from e

        # Create sample pack for these slices
        sample_pack = self._create_sample_pack(
            db_session=db_session,
            project_id=project_id,
            name=f"Samples from {os.path.basename(data) if isinstance(data, str) else 'recording'}",
            description=f"Automatically generated samples from {data if isinstance(data, str) else 'recording'}",
        )

        created_samples = []

        # Load audio file if not already loaded
        if "y" not in locals() or "sr" not in locals():
            if isinstance(data, str):
                if not os.path.exists(data):
                    raise FileNotFoundError(f"Input audio file not found: {data}")
                try:
                    y, sr = self._load_audio_file(
                        data, target_sr=44100
                    )  # Use native sample rate
                except Exception as e:
                    error_msg = str(e)
                    if "librosa.load" in error_msg:
                        raise RuntimeError(error_msg) from e
                    raise
            else:
                # Assume data is already loaded audio
                y = data.get("audio_data")
                sr = data.get("sample_rate")
                if y is None or sr is None:
                    raise ValueError(
                        "Invalid audio data format. Expected 'audio_data' and 'sample_rate' keys."
                    )

            # Process each slice
            processed_slices = 0
            for i, slice_point in enumerate(slice_points):
                start_time = slice_point.get("start")
                end_time = slice_point.get("end")

                if start_time is None or end_time is None:
                    logger.warning(
                        f"Skipping invalid slice point (missing start/end): {slice_point}"
                    )
                    continue

                # Convert times to sample indices
                start_sample = int(start_time * sr)
                end_sample = int(end_time * sr)

                # Ensure valid indices
                if start_sample < 0:
                    start_sample = 0
                if end_sample > len(y):
                    end_sample = len(y)
                if start_sample >= end_sample:
                    logger.warning(
                        f"Skipping invalid slice (start >= end): {start_time}s - {end_time}s"
                    )
                    continue

                # Check min/max sample length
                slice_duration = (end_sample - start_sample) / sr
                min_length = (
                    params.get("min_sample_length_ms", 100) / 1000.0
                )  # Convert to seconds
                max_length = (
                    params.get("max_sample_length_ms", 10000) / 1000.0
                )  # Convert to seconds

                if slice_duration < min_length or slice_duration > max_length:
                    logger.debug(
                        f"Skipping slice outside length range ({slice_duration:.3f}s): "
                        f"min={min_length:.3f}s, max={max_length:.3f}s"
                    )
                    continue

                # Extract audio slice
                slice_audio = y[start_sample:end_sample]

                # Generate output filename
                base_name = os.path.splitext(
                    os.path.basename(data)
                    if isinstance(data, str)
                    else f"sample_{recording_id}"
                )[0]
                output_filename = (
                    f"{base_name}_slice_{i+1:03d}.{params.get('output_format', 'wav')}"
                )
                output_path = os.path.join(output_dir, output_filename)

                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Save slice to disk
                self._save_audio_slice(
                    audio_data=slice_audio,
                    sample_rate=sr,
                    output_path=output_path,
                    bit_depth=params.get("bit_depth", 24),
                    normalize=params.get("normalize", True),
                )

                # Create sample metadata
                sample_metadata = self._create_sample_metadata(
                    recording_id=recording_id,
                    file_path=output_path,
                    start_time=start_time,
                    end_time=end_time,
                    sample_rate=sr,
                    bit_depth=params.get("bit_depth", 24),
                    sample_type=params.get("sample_type", "one_shot"),
                    category=params.get("category", "Uncategorized"),
                    sample_pack_id=sample_pack.id,
                    additional_metadata={
                        "original_file": data if isinstance(data, str) else "in_memory",
                        "slice_index": i,
                        "total_slices": len(slice_points),
                    },
                )

                # Create sample in database
                sample = SampleModel(
                    project_id=project_id,
                    recording_id=recording_id,
                    file_path=output_path,
                    sample_rate=sr,
                    bit_depth=params.get("bit_depth", 24),
                    start_time=start_time,
                    end_time=end_time,
                    duration=end_time - start_time,
                    metadata_json=json.dumps(sample_metadata),
                    sample_pack_id=sample_pack.id,
                    status="processed",
                )

                db_session.add(sample)
                created_samples.append(sample_metadata)
                processed_slices += 1

            # Update recording and sample pack status
            try:
                recording.status = "slicing_completed"
                if processed_slices > 0:
                    sample_pack.status = SamplePackStatus.COMPLETE
                db_session.commit()
                logger.info(
                    f"Successfully created {processed_slices} samples from recording {recording_id}"
                )
                return created_samples

            except Exception as e:
                error_msg = f"Failed to commit final status updates: {str(e)}"
                logger.error(error_msg)
                db_session.rollback()
                raise RuntimeError(error_msg) from e
        return list()

    # Register the stage when this module is imported
try:
    register_stage(SlicingStage)
except Exception as e:
    # Log error if registration fails, e.g., if stage_runner.py is not loaded correctly
    # or if AudioProcessingStage is not fully defined.
    logger.critical(f"Failed to register SlicingStage: {e}", exc_info=True)
