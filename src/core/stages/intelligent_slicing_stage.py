"""
Defines the IntelligentSlicingStage for audio processing pipelines.

This stage combines onset detection, slice planning, segment classification,
and audio slicing into a single stage that takes a file path and produces
a list of sample data. It provides intelligent, end-to-end audio slicing
that can be used standalone or as part of a workflow.
"""

import logging
from typing import Dict, Any, List, Optional

from src.core.processing_stages import AudioProcessingStage
from src.core.stage_runner import register_stage
from src.core.stages.onset_detection_stage import OnsetDetectionStage
from src.core.stages.slice_planning_stage import SlicePlanningStage
from src.core.stages.segment_classification_stage import SegmentClassificationStage
from src.core.stages.slicing_stage import SlicingStage

logger = logging.getLogger(__name__)


class IntelligentSlicingStage(AudioProcessingStage):
    """
    A high-level processing stage that performs intelligent audio slicing.

    This stage orchestrates the full pipeline internally:
    1. Onset detection - finds transient/onset positions
    2. Slice planning - determines optimal slice boundaries
    3. Segment classification - classifies each segment type
    4. Slicing - extracts audio slices and creates database entries

    Input: file_path (path to audio file)
    Output: list_of_sample_data (list of created sample metadata dicts)
    """

    @property
    def name(self) -> str:
        return "intelligent_slicing"

    @property
    def description(self) -> str:
        return (
            "Intelligent audio slicing: detects onsets, plans slices, "
            "classifies segments, and extracts samples."
        )

    @property
    def input_type(self) -> str:
        return "file_path"

    @property
    def output_type(self) -> str:
        return "list_of_sample_data"

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "onset_detection": {},
            "slice_planning": {},
            "segment_classification": {},
            "slicing": {},
        }

    def process(
        self,
        data: str,
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process an audio file through the full intelligent slicing pipeline.

        Args:
            data: Path to the input audio file
            params: Optional parameters for each sub-stage:
                - onset_detection: params for OnsetDetectionStage
                - slice_planning: params for SlicePlanningStage
                - segment_classification: params for SegmentClassificationStage
                - slicing: params for SlicingStage
            context: Must contain db_session, recording_id, project_id, output_sample_dir

        Returns:
            List of sample data dictionaries
        """
        if params is None:
            params = {}

        merged_params = self.default_params.copy()
        merged_params.update(params)

        file_path = data

        # Stage 1: Detect onsets
        logger.info("IntelligentSlicing: detecting onsets")
        onset_stage = OnsetDetectionStage()
        onsets = onset_stage.process(
            file_path, merged_params.get("onset_detection", {}), context
        )
        logger.info(f"IntelligentSlicing: found {len(onsets)} onsets")

        # Stage 2: Plan slices
        logger.info("IntelligentSlicing: planning slices")
        planning_stage = SlicePlanningStage()
        segments = planning_stage.process(
            onsets, merged_params.get("slice_planning", {}), context
        )
        logger.info(f"IntelligentSlicing: planned {len(segments)} segments")

        # Stage 3: Classify segments
        logger.info("IntelligentSlicing: classifying segments")
        classification_stage = SegmentClassificationStage()
        classified = classification_stage.process(
            segments, merged_params.get("segment_classification", {}), context
        )

        # Stage 4: Convert to slice points and run slicing
        logger.info(f"IntelligentSlicing: slicing {len(classified)} segments")
        slice_points = [
            {
                "start": seg["start_time"],
                "end": seg["end_time"],
                "type": seg.get("type", "one_shot"),
                "metadata": seg.get("metadata", {}),
            }
            for seg in classified
        ]

        slicing_stage = SlicingStage()
        slicing_params = merged_params.get("slicing", {}).copy()
        slicing_params["slice_points"] = slice_points

        samples = slicing_stage.process(file_path, slicing_params, context)

        logger.info(f"IntelligentSlicing: created {len(samples)} samples")
        return samples


# Register the stage when this module is imported
try:
    register_stage(IntelligentSlicingStage)
except Exception as e:
    logger.critical(
        f"Failed to register IntelligentSlicingStage: {e}", exc_info=True
    )
