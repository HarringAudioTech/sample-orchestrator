"""
Workflows package for the Sample Orchestrator.

This package contains workflow definitions that coordinate multiple processing stages
to achieve complex audio processing tasks.
"""

# Re-export base workflow classes and registry
from .base import (
    BaseWorkflow,
    WORKFLOW_REGISTRY,
    register_workflow,
    ExampleSlicingWorkflow,
    DecentSamplerCreationWorkflow,
)

# Import workflow implementations to trigger their registration
from .sample_pack_workflow import create_sample_pack_workflow, SamplePackWorkflow
from .audio_ingestion_workflow import AudioIngestionWorkflow

__all__ = [
    "BaseWorkflow",
    "WORKFLOW_REGISTRY",
    "register_workflow",
    "ExampleSlicingWorkflow",
    "DecentSamplerCreationWorkflow",
    "create_sample_pack_workflow",
    "SamplePackWorkflow",
    "AudioIngestionWorkflow",
]
