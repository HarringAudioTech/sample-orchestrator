"""
Sample Pack Workflow

This module defines the complete workflow for processing audio files into
organized sample packs with proper categorization and metadata.
"""

import os
import logging
from typing import Dict, Any, List, Optional

# Import processing stages
from src.core.stages.onset_detection_stage import OnsetDetectionStage
from src.core.stages.slice_planning_stage import SlicePlanningStage
from src.core.stages.segment_classification_stage import SegmentClassificationStage
from src.core.stages.slicing_stage import SlicingStage

# Database models
from sqlalchemy.orm import Session
from src.database.models import (
    Recording as RecordingModel,
    SamplePack,
    SamplePackStatus,
)

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
            name=f"Samples from {os.path.basename(recording.file_path)}",
            project_id=project_id,
            description=f"Auto-generated samples from {os.path.basename(recording.file_path)}",
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
            # Stage 1: Detect onsets in the audio
            logger.info(f"Detecting onsets for recording {recording_id}")
            onsets = self.onset_detection.process(
                recording.file_path, params.get("onset_detection", {}), context
            )

            # Stage 2: Plan slice points based on onsets and project type
            logger.info(f"Planning slice points for recording {recording_id}")
            slice_plan = self.slice_planning.process(
                onsets, params.get("slice_planning", {}), context
            )

            # Stage 3: Classify segments
            logger.info(f"Classifying segments for recording {recording_id}")
            classified_segments = self.segment_classification.process(
                slice_plan, params.get("segment_classification", {}), context
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
            sample_pack.sample_count = len(samples)
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
        self, name: str, project_id: int, description: str = ""
    ) -> SamplePack:
        """
        Create a new sample pack in the database.

        Args:
            name: Name of the sample pack
            project_id: ID of the project this pack belongs to
            description: Optional description of the sample pack

        Returns:
            The created SamplePack instance
        """
        sample_pack = SamplePack(
            name=name,
            description=description,
            project_id=project_id,
            status="processing",
            sample_count=0,
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
