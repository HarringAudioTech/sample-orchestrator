"""
Sample Pack Workflow

This module defines the complete workflow for processing audio files into
organized sample packs with proper categorization and metadata.
"""

import os
import logging
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session

from src.database.models import RecordingModel
from src.core.stages.onset_detection_stage import OnsetDetectionStage
from src.core.stages.slice_planning_stage import SlicePlanningStage
from src.core.stages.segment_classification_stage import SegmentClassificationStage
from src.core.stages.slicing_stage import SlicingStage
from src.core.stages.loop_detection_stage import LoopDetectionStage
from src.core.stages.noise_reduction_stage import NoiseReductionStage
from src.core.stages.quality_control_stage import QualityControlStage
from src.core.workflows.base import BaseWorkflow, register_workflow

logger = logging.getLogger(__name__)

class SamplePackWorkflow(BaseWorkflow):
    """
    A workflow that processes audio files into organized sample packs.

    This workflow coordinates multiple processing stages to transform raw audio
    files into a collection of well-organized samples with proper metadata.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session

    @property
    def name(self) -> str:
        return "sample_pack_workflow"

    @property
    def description(self) -> str:
        return "Complete pipeline: noise reduction -> onset detection -> classification -> slicing."

    @property
    def stages_definition(self) -> List[Dict[str, Any]]:
        """Defines the stages and their parameters for this workflow."""
        return [
            {
                "stage_name": "noise_reduction",
                "params": {"amount": 0.1, "aggressiveness": 1},
            },
            {
                "stage_name": "onset_detection",
                "params": {"backtrack": True},
            },
            {
                "stage_name": "slice_planning",
                "params": {},
            },
            {
                "stage_name": "segment_classification",
                "params": {"min_confidence": 0.5},
            },
            {
                "stage_name": "slicing",
                "params": {"output_format": "wav", "bit_depth": 24},
            },
            {
                "stage_name": "quality_control",
                "params": {},
            }
        ]

    def run(
        self,
        initial_data: str,
        initial_data_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Runs the full sample pack workflow.
        
        Args:
            initial_data: Path to the input audio file
            initial_data_type: Data type (expected "file_path")
            context: Shared context for processing results and metadata
        """
        recording = self.db_session.query(RecordingModel).filter(RecordingModel.id == context.get("recording_id")).first()
        if not recording:
            logger.error(f"Recording ID {context.get('recording_id')} not found")
            raise ValueError(f"Recording not found")

        logger.info(f"Starting Sample Pack Workflow for recording: {recording.name}")
        
        # We manually chain some logic here or use execute_stage_chain
        from src.core.stage_runner import execute_stage_chain
        
        result = execute_stage_chain(
            initial_data=initial_data,
            initial_data_type=initial_data_type,
            chain_definition=self.stages_definition,
            context=context
        )
        
        logger.info(f"Sample Pack Workflow completed for {recording.name}")
        return result

def create_sample_pack_workflow(db_session: Session) -> SamplePackWorkflow:
    """Factory function to create a SamplePackWorkflow."""
    return SamplePackWorkflow(db_session)

# Register the workflow
try:
    register_workflow(SamplePackWorkflow)
except Exception as e:
    logger.error(f"Failed to register SamplePackWorkflow: {e}")
