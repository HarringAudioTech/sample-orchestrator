"""
Defines the SegmentClassificationStage for audio processing pipelines.
This stage classifies audio segments into different types (one-shots, loops, etc.)
based on their characteristics and project requirements.
"""

import logging
from enum import Enum, auto
from typing import Dict, Any, List, Optional
import numpy as np

from src.core.processing_stages import AudioProcessingStage, register_stage

logger = logging.getLogger(__name__)

class SegmentType(Enum):
    """Types of audio segments that can be classified."""
    ONE_SHOT = auto()
    LOOP = auto()
    AMBIENT = auto()
    FILL = auto()
    TRANSITION = auto()
    UNKNOWN = auto()

class SegmentClassificationStage(AudioProcessingStage):
    """
    A processing stage that classifies audio segments into different types.
    
    This stage takes a list of audio segments (from slice planning) and classifies
    them into categories like one-shots, loops, etc. based on their characteristics
    and the project requirements.
    """
    
    @property
    def name(self) -> str:
        return "segment_classification"
    
    @property
    def description(self) -> str:
        return "Classifies audio segments into types (one-shots, loops, etc.)"
    
    @property
    def input_type(self) -> str:
        return "audio_segments"  # List of audio segments with timing info
    
    @property
    def output_type(self) -> str:
        return "classified_segments"  # List of segments with type classification
    
    @property
    def default_params(self) -> Dict[str, Any]:
        """
        Returns default parameters for segment classification.
        """
        return {
            "project_type": "drum_kit",  # drum_kit, melodic_loops, vocals, etc.
            "classification_rules": {
                "max_one_shot_duration": 2.0,  # Maximum duration for one-shots
                "min_loop_duration": 0.5,      # Minimum duration for loops
                "max_loop_duration": 32.0,     # Maximum duration for loops
                "min_loop_repetitions": 2,     # Minimum repetitions for loop detection
                "ambient_min_duration": 5.0,   # Minimum duration for ambient segments
            },
            "confidence_threshold": 0.7,  # Minimum confidence for classification
        }
    
    def _classify_one_shot(
        self, 
        segment: Dict[str, Any], 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Classify a segment as a one-shot."""
        rules = params.get("classification_rules", {})
        duration = segment.get("end_time", 0) - segment.get("start_time", 0)
        
        # Check if segment meets one-shot criteria
        if duration <= rules.get("max_one_shot_duration", 2.0):
            segment["type"] = "one_shot"
            segment["metadata"]["classification_confidence"] = 0.9
            segment["metadata"]["classification_reason"] = "Short duration"
        
        return segment
    
    def _classify_loop(
        self, 
        segment: Dict[str, Any], 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Classify a segment as a loop."""
        rules = params.get("classification_rules", {})
        duration = segment.get("end_time", 0) - segment.get("start_time", 0)
        
        # Check if segment meets loop criteria
        min_loop = rules.get("min_loop_duration", 0.5)
        max_loop = rules.get("max_loop_duration", 32.0)
        
        if min_loop <= duration <= max_loop:
            # In a real implementation, we would analyze the audio for loop points
            # For now, we'll just classify based on duration
            segment["type"] = "loop"
            segment["metadata"]["classification_confidence"] = 0.8
            segment["metadata"]["classification_reason"] = "Duration suggests loop"
        
        return segment
    
    def _classify_ambient(
        self, 
        segment: Dict[str, Any], 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Classify a segment as ambient."""
        rules = params.get("classification_rules", {})
        duration = segment.get("end_time", 0) - segment.get("start_time", 0)
        
        # Check if segment meets ambient criteria
        if duration >= rules.get("ambient_min_duration", 5.0):
            segment["type"] = "ambient"
            segment["metadata"]["classification_confidence"] = 0.85
            segment["metadata"]["classification_reason"] = "Long duration suggests ambient"
        
        return segment
    
    def process(
        self, 
        segments: List[Dict[str, Any]], 
        params: Optional[Dict[str, Any]] = None, 
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Classify audio segments into different types.
        
        Args:
            segments: List of segments with timing information
            params: Parameters for classification
            context: Optional context dictionary (e.g., containing project settings)
            
        Returns:
            List of segments with added classification information
        """
        if params is None:
            params = {}
            
        # Merge default params with provided params
        merged_params = self.default_params.copy()
        merged_params.update(params)
        
        # Get project type from params or context
        project_type = merged_params.get("project_type")
        if context and "project_type" in context:
            project_type = context["project_type"]
        
        classified_segments = []
        
        for segment in segments:
            # Ensure metadata dictionary exists
            if "metadata" not in segment:
                segment["metadata"] = {}
            
            # Apply classification based on project type
            if project_type == "drum_kit":
                segment = self._classify_one_shot(segment, merged_params)
            elif project_type == "melodic_loops":
                segment = self._classify_loop(segment, merged_params)
            elif project_type == "ambient":
                segment = self._classify_ambient(segment, merged_params)
            
            # If no classification was made, mark as unknown
            if "type" not in segment:
                segment["type"] = "unknown"
                segment["metadata"]["classification_confidence"] = 0.5
                segment["metadata"]["classification_reason"] = "No specific classification matched"
            
            classified_segments.append(segment)
        
        return classified_segments


# Register the stage when this module is imported
register_stage(SegmentClassificationStage)
