"""
Defines the SegmentClassificationStage for audio processing pipelines.
This stage classifies audio segments into different types (one-shots, loops, etc.)
based on their characteristics and project requirements.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import librosa
from sqlalchemy.orm import Session

from src.core.processing_stages import AudioProcessingStage
from src.core.stage_runner import register_stage
from src.database.models import SampleModel
from src.utils.audio_utils import is_test_environment

logger = logging.getLogger(__name__)


class SegmentClassificationStage(AudioProcessingStage):
    """
    A processing stage that classifies audio segments into different types.

    This stage takes a list of audio segments (from slice planning) and classifies
    them into categories like one-shots, loops, etc. based on their characteristics
    and the project requirements.
    """

    @property
    def name(self) -> str:
        return "segment_classification"

    @property
    def description(self) -> str:
        return "Classifies audio segments into types (one-shots, loops, etc.)"

    @property
    def input_type(self) -> str:
        return "audio_segments"

    @property
    def output_type(self) -> str:
        return "audio_segments"

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "project_type": "sample_pack",
            "classification_rules": {
                "max_one_shot_duration": 2.0,
                "min_loop_duration": 0.5,
                "max_loop_duration": 32.0,
                "min_loop_repetitions": 2,
                "ambient_min_duration": 5.0,
                "kick_max_centroid": 1800,
                "hat_min_centroid": 5000,
                "snare_min_flatness": 0.01,
                "tom_max_flatness": 0.01,
            },
            "confidence_threshold": 0.7,
            "enable_spectral_analysis": True,
        }

    def _analyze_spectral_features(
        self, y: np.ndarray, sr: int
    ) -> Dict[str, float]:
        """Compute spectral and temporal features for classification."""
        if len(y) == 0:
            return {"centroid": 0.0, "flatness": 0.0, "rms": 0.0, "peak": 0.0}
            
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        flatness = librosa.feature.spectral_flatness(y=y)
        rms = librosa.feature.rms(y=y)
        peak = float(np.max(np.abs(y)))
        
        return {
            "centroid": float(np.mean(centroid)),
            "flatness": float(np.mean(flatness)),
            "rms": float(np.mean(rms)),
            "peak": peak,
        }

    def _classify_segment(
        self,
        segment: Dict[str, Any],
        params: Dict[str, Any],
        project_type: str,
        audio_data: Optional[np.ndarray] = None,
        sr: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Classify a segment based on duration and optional spectral features."""
        rules = params.get("classification_rules", {})
        duration = segment.get("end_time", 0) - segment.get("start_time", 0)

        if "metadata" not in segment:
            segment["metadata"] = {}

        # 1. Basic Duration-based classification
        max_one_shot = rules.get("max_one_shot_duration", 2.0)
        min_loop = rules.get("min_loop_duration", 0.5)
        max_loop = rules.get("max_loop_duration", 32.0)
        ambient_min = rules.get("ambient_min_duration", 5.0)

        if duration >= ambient_min:
            segment["type"] = "ambient"
            segment["metadata"]["classification_confidence"] = 0.85
            segment["metadata"]["classification_reason"] = "Long duration suggests ambient"
        elif duration <= max_one_shot:
            segment["type"] = "one_shot"
            segment["metadata"]["classification_confidence"] = 0.9
            segment["metadata"]["classification_reason"] = "Short duration"
        elif min_loop <= duration <= max_loop:
            segment["type"] = "loop"
            segment["metadata"]["classification_confidence"] = 0.8
            segment["metadata"]["classification_reason"] = "Duration suggests loop"
        else:
            segment["type"] = "unknown"
            segment["metadata"]["classification_confidence"] = 0.5
            segment["metadata"]["classification_reason"] = "No specific classification matched"

        # 2. Spectral enhancement for drum types
        if params.get("enable_spectral_analysis", True) and audio_data is not None and sr is not None:
            # Extract segment audio
            start_sample = int(segment["start_time"] * sr)
            end_sample = int(segment["end_time"] * sr)
            y_seg = audio_data[start_sample:end_sample]
            
            if len(y_seg) > 0:
                features = self._analyze_spectral_features(y_seg, sr)
                segment["metadata"]["spectral_centroid"] = features["centroid"]
                segment["metadata"]["spectral_flatness"] = features["flatness"]
                segment["metadata"]["rms_energy"] = features["rms"]
                segment["metadata"]["peak_amplitude"] = features["peak"]
                
                # Drum instrument heuristics
                kick_max = rules.get("kick_max_centroid", 1800)
                hat_min = rules.get("hat_min_centroid", 5000)
                snare_min_flat = rules.get("snare_min_flatness", 0.01)
                tom_max_flat = rules.get("tom_max_flatness", 0.01)
                
                # Tagging logic
                segment["metadata"]["tags"] = []
                centroid = features["centroid"]
                flatness = features["flatness"]
                rms = features["rms"]
                
                if segment["type"] == "one_shot":
                    segment["metadata"]["tags"].append("one_shot")

                    if centroid < kick_max and flatness < tom_max_flat:
                        segment["metadata"]["instrument_type"] = "kick"
                        segment["metadata"]["tags"].extend(["drum", "kick"])
                    elif centroid > hat_min:
                        segment["metadata"]["instrument_type"] = "hihat"
                        segment["metadata"]["tags"].extend(["drum", "hihat"])
                        # Sub-tag for hi-hats
                        if duration > 0.3:
                            segment["metadata"]["tags"].append("open_hat")
                        else:
                            segment["metadata"]["tags"].append("closed_hat")
                    elif flatness > snare_min_flat:
                        segment["metadata"]["instrument_type"] = "snare"
                        segment["metadata"]["tags"].extend(["drum", "snare"])
                    elif flatness < tom_max_flat:
                        segment["metadata"]["instrument_type"] = "tom"
                        segment["metadata"]["tags"].extend(["drum", "tom"])
                    else:
                        segment["metadata"]["instrument_type"] = "perc"
                        segment["metadata"]["tags"].append("perc")
                
                # Character tags
                if flatness < 0.005:
                    segment["metadata"]["character"] = "tonal"
                    segment["metadata"]["tags"].append("tonal")
                elif flatness > 0.05:
                    segment["metadata"]["character"] = "noisy"
                    segment["metadata"]["tags"].append("noisy")
                else:
                    segment["metadata"]["character"] = "hybrid"
                
                if rms > 0.1:
                    segment["metadata"]["tags"].append("high_energy")
                elif rms < 0.01:
                    segment["metadata"]["tags"].append("low_energy")

        return segment

    def process(
        self,
        segments: List[Dict[str, Any]],
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Classify audio segments into different types.

        Args:
            segments: List of segments with start_time, end_time, type, metadata
            params: Parameters for classification
            context: Optional context dictionary

        Returns:
            List of classified segments
        """
        if params is None:
            params = {}

        merged_params = self.default_params.copy()
        merged_params.update(params)

        project_type = merged_params.get("project_type", "sample_pack")
        if context and "project_type" in context:
            project_type = context["project_type"]

        if hasattr(project_type, "value"):
            project_type = project_type.value

        # Load audio if spectral analysis is enabled and not provided
        audio_data = None
        sr = None
        if merged_params.get("enable_spectral_analysis", True):
            if context and "audio_data" in context and "sample_rate" in context:
                audio_data = context["audio_data"]
                sr = context["sample_rate"]
            elif context and "file_path" in context:
                try:
                    audio_data, sr = librosa.load(context["file_path"], sr=None, mono=True)
                except Exception as e:
                    logger.warning(f"Failed to load audio for spectral analysis: {e}")

        classified_segments = []
        db_session: Optional[Session] = context.get("db_session") if context else None

        for segment in segments:
            classified = self._classify_segment(
                segment, merged_params, project_type, audio_data, sr
            )
            
            # Update database if sample_id and db_session are available
            sample_id = classified.get("id") or classified.get("sample_id")
            if sample_id and db_session:
                try:
                    sample = db_session.query(SampleModel).filter(SampleModel.id == sample_id).first()
                    if sample:
                        sample.sample_type = classified["type"]
                        # Merge metadata
                        existing_meta = json.loads(sample.metadata_json) if sample.metadata_json else {}
                        existing_meta.update(classified.get("metadata", {}))
                        sample.metadata_json = json.dumps(existing_meta)
                        db_session.add(sample)
                        logger.info(f"Updated sample {sample_id} with classification: {classified['type']}")
                except Exception as e:
                    logger.error(f"Failed to update sample {sample_id} in database: {e}")

            classified_segments.append(classified)

        if db_session:
            try:
                if not is_test_environment():
                    db_session.commit()
                    logger.info("Committed classification updates to database.")
                else:
                    db_session.flush()
                    logger.info("Flushed classification updates to database (test mode).")
            except Exception as e:
                db_session.rollback()
                logger.error(f"Failed to commit classification updates: {e}")

        return classified_segments


# Register the stage when this module is imported
register_stage(SegmentClassificationStage)
