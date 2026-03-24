"""
Sample Pack Workflow

This module defines the complete workflow for processing audio files into
organized sample packs with proper categorization and metadata.
"""

import os
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

# Import models
from src.database.models import ProjectType, SamplePackStatus, SamplePackModel

# Import processing stages
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

        # Initialize processing stages
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

        # Get recording from database
        recording = self.db_session.query(RecordingModel).get(recording_id)
        if not recording:
            raise ValueError(f"Recording with ID {recording_id} not found")

        # Update recording status
        recording.status = "processing"
        self.db_session.commit()

        # Create output directory for this recording
        recording_output_dir = os.path.join(output_dir, f"recording_{recording_id}")
        os.makedirs(recording_output_dir, exist_ok=True)

        # Create a sample pack for this recording
        sample_pack = self._create_sample_pack(
            id=project_id,
            name=f"Samples from {recording.id}",
            description=f"Auto-generated samples from {recording.id}",
            status="draft",
            project_type=ProjectType.SAMPLE_PACK,
        )

        # Prepare context for processing stages
        context = {
            "db_session": self.db_session,
            "recording_id": recording_id,
            "project_id": project_id,
            "sample_pack_id": sample_pack.id,
            "output_sample_dir": os.path.join(recording_output_dir, "samples"),
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

            # Stage 4: Slice the audio and create samples
            logger.info(f"Slicing audio for recording {recording_id}")
            samples = self.slicing.process(
                {
                    "audio_file": recording.file_path,
                    "slice_points": classified_segments,
                },
                params.get("slicing", {}),
                context,
            )

            # Update sample pack with results
            sample_pack.status = SamplePackStatus.COMPLETE
            self.db_session.commit()

            # Update recording status
            recording.status = "completed"
            self.db_session.commit()

            return {
                "status": "success",
                "recording_id": recording_id,
                "sample_pack_id": sample_pack.id,
                "samples_created": len(samples),
                "output_dir": recording_output_dir,
            }

        except Exception as e:
            # Update status to failed
            recording.status = "failed"
            if sample_pack:
                sample_pack.status = SamplePackStatus.COMPLETE
            self.db_session.commit()

            logger.error(
                f"Error processing recording {recording_id}: {str(e)}", exc_info=True
            )
            raise

    def _create_sample_pack(
        self, id: int, name: str, description: str = "", status: str = "draft", project_type: str = ProjectType.SAMPLE_PACK
    ) -> SamplePackModel:
        """
        Create a new sample pack in the database.

        Args:
            id: ID of the sample pack
            name: Name of the sample pack
            description: Optional description of the sample pack
            status: Status of the sample pack
            project_type: Type of the project

        Returns:
            The created SamplePackModel instance
        """
        sample_pack = SamplePackModel(
            id=id,
            name=name,
            description=description,
            status=status,
            project_type=project_type,
        )

        self.db_session.add(sample_pack)
        self.db_session.commit()

        return sample_pack


def create_sample_pack_workflow(db_session: Session) -> SamplePackWorkflow:
    """
    Factory function to create a new SamplePackWorkflow instance.

    This is the preferred way to create a workflow instance as it ensures
    proper dependency injection and configuration.

    Args:
        db_session: SQLAlchemy database session

    Returns:
        A new SamplePackWorkflow instance
    """
    return SamplePackWorkflow(db_session)
