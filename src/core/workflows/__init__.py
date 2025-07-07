"""
Workflows package for the Sample Orchestrator.

This package contains workflow definitions that coordinate multiple processing stages
to achieve complex audio processing tasks.
"""

# Import workflow classes to make them available when importing from the package
from .sample_pack_workflow import create_sample_pack_workflow, SamplePackWorkflow

__all__ = [
    'create_sample_pack_workflow',
    'SamplePackWorkflow',
]
