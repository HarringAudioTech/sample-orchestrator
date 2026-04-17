"""
Stage runner infrastructure for the Sample Orchestrator.

This module provides the mechanism to register and execute audio processing stages,
enabling flexible workflow definitions.
"""

import logging
from typing import Dict, Any, List, Optional, Type

# pylint: disable=no-member

logger = logging.getLogger(__name__)

# Constants for data types
DATA_TYPE_FILE_PATH = "file_path"
DATA_TYPE_AUDIO_BUFFER_MONO = "audio_buffer_mono"
DATA_TYPE_AUDIO_BUFFER_STEREO = "audio_buffer_stereo"
DATA_TYPE_MIDI_DATA = "midi_data"
DATA_TYPE_METADATA = "metadata"

# Registry for available stages
STAGE_REGISTRY: Dict[str, Type] = {}

def register_stage(stage_class: Type) -> Type:
    """Registers a stage class in the registry."""
    try:
        # Try to get name from the class attribute or a property on an instance
        if hasattr(stage_class, "name") and not isinstance(getattr(stage_class, "name"), property):
            stage_name = stage_class.name
        else:
            # Create a dummy instance to get the name
            instance = stage_class()
            stage_name = instance.name
            
        STAGE_REGISTRY[stage_name] = stage_class
        logger.info(f"Successfully registered stage: '{stage_name}' from class '{stage_class.__name__}'.")
    except Exception as e:
        logger.error(f"Failed to register stage class '{stage_class.__name__}': {e}")
    
    return stage_class

class BaseStage:
    """Base class for all processing stages."""
    
    @property
    def name(self) -> str:
        """Unique identifier for the stage."""
        raise NotImplementedError
        
    @property
    def description(self) -> str:
        """Human-readable description of what the stage does."""
        return ""
        
    @property
    def input_type(self) -> str:
        """The type of data this stage expects as input."""
        raise NotImplementedError
        
    @property
    def output_type(self) -> str:
        """The type of data this stage produces as output."""
        raise NotImplementedError
        
    def process(self, data: Any, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """
        Executes the processing logic for this stage.
        
        Args:
            data: The input data to process
            params: Stage-specific parameters
            context: Shared context for the entire workflow
        """
        raise NotImplementedError

def execute_stage_chain(
    initial_data: Any,
    initial_data_type: str,
    chain_definition: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executes a chain of stages sequentially.
    
    Args:
        initial_data: The starting data
        initial_data_type: The type of the starting data
        chain_definition: List of dicts with 'stage_name' and 'params'
        context: Shared context dictionary
    """
    if context is None:
        context = {}
        
    current_data = initial_data
    current_type = initial_data_type
    
    execution_results = []
    
    for stage_info in chain_definition:
        stage_name = stage_info["stage_name"]
        stage_params = stage_info.get("params", {})
        
        if stage_name not in STAGE_REGISTRY:
            logger.error(f"Stage '{stage_name}' not found in registry.")
            raise ValueError(f"Unknown stage: {stage_name}")
            
        stage_class = STAGE_REGISTRY[stage_name]
        stage_instance = stage_class()
        
        # Validate input type
        if current_type != stage_instance.input_type:
            logger.error(f"Type mismatch for stage '{stage_name}': expected {stage_instance.input_type}, got {current_type}")
            raise TypeError(f"Input type mismatch for {stage_name}")
            
        logger.info(f"Executing stage: '{stage_name}'")
        
        try:
            # Process data
            current_data = stage_instance.process(current_data, stage_params, context)
            current_type = stage_instance.output_type
            
            execution_results.append({
                "stage": stage_name,
                "status": "success"
            })
        except Exception as e:
            logger.error(f"Error in stage '{stage_name}': {e}", exc_info=True)
            execution_results.append({
                "stage": stage_name,
                "status": "error",
                "error": str(e)
            })
            raise
            
    return {
        "final_data": current_data,
        "final_type": current_type,
        "stages": execution_results
    }
