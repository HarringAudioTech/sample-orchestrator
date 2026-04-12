"""
Sample Pack Workflow

This module defines the complete workflow for processing audio files into
organized sample packs with proper categorization and metadata.
"""

import os
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from src.database.models import RecordingModel, SamplePackStatus
from src.core.stages.onset_detection_stage import OnsetDetectionStage
from src.core.stages.slice_planning_stage import SlicePlanningStage
from src.core.stages.segment_classification_stage import SegmentClassificationStage
from src.core.stages.slicing_stage import SlicingStage
from src.core.stages.loop_detection_stage import LoopDetectionStage

logger = logging.getLogger(__name__)


class SamplePackWorkflow:
    """
    A workflow that processes audio files into organized sample packs.

    This workflow coordinates multiple processing stages to transform raw audio
    files into a collection of well-organized samples with proper metadata.
    """

    def __init__(self, db_session: Session):
        """Initialize the workflow with a database session."""
        self.db_session = db_session
        self.onset_detection = OnsetDetectionStage()
        self.slice_planning = SlicePlanningStage()
        self.segment_classification = SegmentClassificationStage()
        self.slicing = SlicingStage()
        self.loop_detection = LoopDetectionStage()

    def process_recording(
        self,
        recording_id: int,
        project_id: int,
        output_dir: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a recording through the complete sample pack workflow.

        Args:
            recording_id: ID of the recording to process
            project_id: ID of the project this recording belongs to
            output_dir: Base directory for output files
            params: Optional parameters to customize the processing

        Returns:
            Dictionary containing processing results and metadata
        """
        if params is None:
            params = {}

        recording = self.db_session.get(RecordingModel, recording_id)
        if not recording:
            raise ValueError(f"Recording with ID {recording_id} not found")

        recording_output_dir = os.path.join(output_dir, f"recording_{recording_id}")
        samples_dir = os.path.join(recording_output_dir, "samples")
        os.makedirs(samples_dir, exist_ok=True)

        context = {
            "db_session": self.db_session,
            "recording_id": recording_id,
            "project_id": project_id,
            "output_sample_dir": samples_dir,
            "project_type": "sample_pack",
        }

        try:
            loop_detection_params = params.get("loop_detection", {})
            use_loop_detection = loop_detection_params.get("enabled", False)

            if use_loop_detection:
                # Loop detection path: detect, score, and select the
                # best N loops directly from the audio file.
                logger.info(
                    f"Running loop detection for recording {recording_id}"
                )
                slice_plan = self.loop_detection.process(
                    recording.file_path, loop_detection_params, context
                )
                # Classify the detected loops
                classified_segments = self.segment_classification.process(
                    slice_plan,
                    params.get("segment_classification", {}),
                    context,
                )
            else:
                # Default one-shot path: onset detection → slice planning
                # Stage 1: Detect onsets in the audio
                logger.info(
                    f"Detecting onsets for recording {recording_id}"
                )
                onsets = self.onset_detection.process(
                    recording.file_path,
                    params.get("onset_detection", {}),
                    context,
                )

                # Stage 2: Plan slice points based on onsets and project type
                logger.info(
                    f"Planning slice points for recording {recording_id}"
                )
                # Make file path available for heuristic loop detection
                # in _plan_melodic_loops()
                context["file_path"] = recording.file_path
                slice_plan = self.slice_planning.process(
                    onsets, params.get("slice_planning", {}), context
                )

                # Stage 3: Classify segments
                logger.info(
                    f"Classifying segments for recording {recording_id}"
                )
                classified_segments = self.segment_classification.process(
                    slice_plan,
                    params.get("segment_classification", {}),
                    context,
                )

            # Stage 4: Convert classified segments to slice_points format and slice
            logger.info(f"Slicing audio for recording {recording_id}")
            slice_points = [
                {
                    "start": seg["start_time"],
                    "end": seg["end_time"],
                    "type": seg.get("type", "one_shot"),
                    "metadata": seg.get("metadata", {}),
                }
                for seg in classified_segments
            ]

            slicing_params = params.get("slicing", {})
            slicing_params["slice_points"] = slice_points

            samples = self.slicing.process(
                recording.file_path,
                slicing_params,
                context,
            )

            logger.info(
                f"Created {len(samples)} samples from recording {recording_id}"
            )

            return {
                "status": "success",
                "recording_id": recording_id,
                "samples_created": len(samples),
                "output_dir": recording_output_dir,
                "samples": samples,
            }

        except Exception as e:
            logger.error(
                f"Error processing recording {recording_id}: {str(e)}", exc_info=True
            )
            raise


def create_sample_pack_workflow(db_session: Session) -> SamplePackWorkflow:
    """
    Factory function to create a new SamplePackWorkflow instance.

    Args:
        db_session: SQLAlchemy database session

    Returns:
        A new SamplePackWorkflow instance
    """
    return SamplePackWorkflow(db_session)
