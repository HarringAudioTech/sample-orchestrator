"""
Defines the SegmentClassificationStage for audio processing pipelines.
This stage classifies audio segments into different types (one-shots, loops, etc.)
based on their characteristics and project requirements.
"""

import logging
from typing import Dict, Any, List, Optional

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
            },
            "confidence_threshold": 0.7,
        }

    def _classify_segment(
        self,
        segment: Dict[str, Any],
        params: Dict[str, Any],
        project_type: str,
    ) -> Dict[str, Any]:
        """Classify a segment based on duration and project type."""
        rules = params.get("classification_rules", {})
        duration = segment.get("end_time", 0) - segment.get("start_time", 0)

        if "metadata" not in segment:
            segment["metadata"] = {}

        # Duration-based classification
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

        classified_segments = []

        for segment in segments:
            classified = self._classify_segment(segment, merged_params, project_type)
            classified_segments.append(classified)

        return classified_segments


# Register the stage when this module is imported
register_stage(SegmentClassificationStage)
