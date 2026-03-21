"""
Audio Ingestion Workflow

Defines a BaseWorkflow that uses the IntelligentSlicingStage to provide
end-to-end audio ingestion: file → onset detection → slice planning →
segment classification → slicing → sample creation.
"""

import logging
from typing import Dict, Any, List

from src.core.workflows.base import BaseWorkflow, register_workflow

# Ensure the intelligent_slicing stage is registered
import src.core.stages.intelligent_slicing_stage  # noqa: F401

logger = logging.getLogger(__name__)


class AudioIngestionWorkflow(BaseWorkflow):
    """
    Workflow for ingesting audio files and intelligently slicing them
    into organized, classified samples.

    This workflow uses the IntelligentSlicingStage which internally
    orchestrates onset detection, slice planning, segment classification,
    and audio slicing.
    """

    @property
    def name(self) -> str:
        return "audio_ingestion_workflow"

    @property
    def description(self) -> str:
        return (
            "Ingests audio files and intelligently slices them into "
            "classified samples with metadata."
        )

    @property
    def stages_definition(self) -> List[Dict[str, Any]]:
        return [
            {
                "stage_name": "intelligent_slicing",
                "params": {},
            },
        ]


try:
    register_workflow(AudioIngestionWorkflow)
except Exception as e:
    logger.critical(
        f"Failed to register AudioIngestionWorkflow: {e}", exc_info=True
    )
