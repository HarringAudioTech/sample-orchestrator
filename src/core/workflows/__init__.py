"""
Workflows package for the Sample Orchestrator.

This package contains workflow definitions that coordinate multiple processing stages
to achieve complex audio processing tasks.
"""
from typing import Dict, Type, Any, Callable

# Import workflow classes to make them available when importing from the package
from .sample_pack_workflow import create_sample_pack_workflow, SamplePackWorkflow

# Registry of available workflows
WORKFLOW_REGISTRY: Dict[str, Dict[str, Any]] = {
    'sample_pack': {
        'name': 'Sample Pack',
        'description': 'Process audio files into organized sample packs with proper categorization and metadata',
        'factory': create_sample_pack_workflow,
        'class': SamplePackWorkflow,
    },
    # Add other workflows here as they are implemented
}

__all__ = [
    'create_sample_pack_workflow',
    'SamplePackWorkflow',
    'WORKFLOW_REGISTRY',
]
