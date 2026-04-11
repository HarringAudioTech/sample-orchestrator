"""
Defines the SegmentClassificationStage for audio processing pipelines.
This stage classifies audio segments into different types (one-shots, loops, etc.)
based on their characteristics and project requirements.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import librosa

from src.core.processing_stages import AudioProcessingStage
from src.core.stage_runner import register_stage

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
        return "classified_segments"

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
                "kick_max_centroid": 1500,
                "hat_min_centroid": 5000,
                "snare_min_flatness": 0.05,
            },
            "confidence_threshold": 0.7,
            "enable_spectral_analysis": True,
        }

    def _analyze_spectral_features(
        self, y: np.ndarray, sr: int
    ) -> Dict[str, float]:
        """Compute spectral features for classification."""
        if len(y) == 0:
            return {"centroid": 0.0, "flatness": 0.0}
            
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        flatness = librosa.feature.spectral_flatness(y=y)
        
        return {
            "centroid": float(np.mean(centroid)),
            "flatness": float(np.mean(flatness)),
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
                
                # Drum instrument heuristics
                kick_max = rules.get("kick_max_centroid", 1500)
                hat_min = rules.get("hat_min_centroid", 5000)
                snare_min_flat = rules.get("snare_min_flatness", 0.05)
                
                # Tagging logic
                segment["metadata"]["tags"] = []
                
                if segment["type"] == "one_shot":
                    segment["metadata"]["tags"].append("one_shot")
                    if features["centroid"] < kick_max:
                        segment["metadata"]["instrument_type"] = "kick"
                        segment["metadata"]["tags"].append("drum")
                        segment["metadata"]["tags"].append("kick")
                    elif features["centroid"] > hat_min:
                        segment["metadata"]["instrument_type"] = "hihat"
                        segment["metadata"]["tags"].append("drum")
                        segment["metadata"]["tags"].append("hihat")
                    elif features["flatness"] > snare_min_flat:
                        segment["metadata"]["instrument_type"] = "snare"
                        segment["metadata"]["tags"].append("drum")
                        segment["metadata"]["tags"].append("snare")
                    else:
                        segment["metadata"]["instrument_type"] = "perc"
                        segment["metadata"]["tags"].append("perc")
                
                if features["flatness"] < 0.01:
                    segment["metadata"]["is_tonal"] = True
                    segment["metadata"]["tags"].append("tonal")
                else:
                    segment["metadata"]["is_tonal"] = False
                    segment["metadata"]["tags"].append("noisy")

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

        for segment in segments:
            classified = self._classify_segment(
                segment, merged_params, project_type, audio_data, sr
            )
            classified_segments.append(classified)

        return classified_segments


# Register the stage when this module is imported
register_stage(SegmentClassificationStage)
