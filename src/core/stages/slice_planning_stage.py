"""
Defines the SlicePlanningStage for audio processing pipelines.
This stage takes detected onsets and applies rules to determine optimal slice points
for one-shots, loops, or other segment types based on project requirements.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional, Union
import numpy as np
from enum import Enum

from src.core.processing_stages import AudioProcessingStage, register_stage
# ProjectType removed; use string or Enum placeholder as needed

logger = logging.getLogger(__name__)

class SlicePlanningStage(AudioProcessingStage):
    """
    A processing stage that plans slice points based on detected onsets and project rules.
    
    This stage takes onset times and determines how to best slice the audio into
    meaningful segments like one-shots, loops, or other musical elements based on
    the project type and configuration.
    """
    
    @property
    def name(self) -> str:
        return "slice_planning"
    
    @property
    def description(self) -> str:
        return "Plans slice points based on onsets and project rules"
    
    @property
    def input_type(self) -> str:
        return "onset_times"  # List of onset times in seconds
    
    @property
    def output_type(self) -> str:
        return "slice_points"  # List of slice points with metadata
    
    @property
    def default_params(self) -> Dict[str, Any]:
        """
        Returns default parameters for slice planning.
        """
        return {
            "project_type": ProjectType.SAMPLE_PACK,
            "min_slice_duration": 0.05,  # 50ms minimum duration for a slice
            "max_slice_duration": 10.0,  # 10s maximum duration for a slice
            "min_silence_duration": 0.1,  # 100ms minimum silence between slices
            "loop_detection": {
                "enabled": True,
                "min_loop_length": 1.0,  # 1s minimum loop length
                "max_loop_length": 32.0, # 32s maximum loop length
                "tempo_hint": 120.0,     # BPM hint for loop detection
            },
            "one_shot_detection": {
                "enabled": True,
                "max_duration": 5.0,     # 5s maximum for one-shots
                "min_silence_after": 0.05,  # 50ms silence after a one-shot
            }
        }
    
    def _plan_drum_kit_slices(
        self, 
        onset_times: List[float], 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Plan slices for drum kit samples (one-shot focused)."""
        min_duration = params.get("min_slice_duration", 0.05)
        max_duration = params.get("max_slice_duration", 5.0)
        min_silence = params.get("min_silence_duration", 0.1)
        
        slices = []
        
        # Sort onset times
        onset_times = sorted(onset_times)
        
        for i in range(len(onset_times)):
            start_time = onset_times[i]
            
            # Default end time is either the next onset or start + max_duration
            if i < len(onset_times) - 1:
                end_time = min(onset_times[i+1], start_time + max_duration)
            else:
                end_time = start_time + max_duration
            
            # Ensure minimum duration
            if end_time - start_time < min_duration:
                end_time = start_time + min_duration
            
            slices.append({
                "start_time": start_time,
                "end_time": end_time,
                "type": "one_shot",
                "metadata": {
                    "confidence": 1.0,
                    "source": "onset_detection"
                }
            })
        
        return slices
    
    def _plan_melodic_loops(
        self,
        onset_times: List[float],
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Plan slices for melodic loops using heuristic-scored loop detection.

        When the audio file path is available via *context*, the
        :class:`~src.core.loop_evaluator.LoopEvaluator` is used to detect,
        score, and select the best loop candidates.  Falls back to returning
        the full audio as a single loop when no file path is available.
        """
        loop_params = params.get("loop_detection", {})
        min_loop = loop_params.get("min_loop_length", 1.0)
        max_loop = loop_params.get("max_loop_length", 32.0)

        # Try heuristic loop detection when we have a file path
        file_path = None
        if context:
            file_path = context.get("file_path") or context.get("audio_file")

        if file_path:
            try:
                from src.core.loop_evaluator import LoopEvaluator

                max_candidates = loop_params.get("max_candidates", 5)
                min_score = loop_params.get("min_score", 0.3)
                evaluator = LoopEvaluator(
                    min_loop_duration=min_loop,
                    max_loop_duration=max_loop,
                )
                result = evaluator.evaluate(
                    file_path, n=max_candidates, min_score=min_score,
                )
                if result.selected_candidates:
                    if context is not None:
                        context["loop_detection_result"] = result
                    return [
                        {
                            "start_time": sc.candidate.start_time,
                            "end_time": sc.candidate.end_time,
                            "type": "loop",
                            "metadata": {
                                "confidence": sc.overall_score,
                                "source": "loop_detection",
                                "rank": sc.rank,
                                "duration_bars": sc.candidate.duration_bars,
                                "bpm": sc.candidate.bpm,
                            },
                        }
                        for sc in result.selected_candidates
                    ]
            except Exception as exc:
                logger.warning("Heuristic loop detection failed, falling back: %s", exc)

        # Fallback: return the entire audio as one loop
        if not onset_times:
            return []

        return [{
            "start_time": 0.0,
            "end_time": max(onset_times) + 1.0,
            "type": "loop",
            "metadata": {
                "confidence": 0.5,
                "source": "full_audio_fallback"
            }
        }]
    
    def process(
        self, 
        data: List[float], 
        params: Optional[Dict[str, Any]] = None, 
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Plan slice points based on detected onsets and project rules.
        
        Args:
            data: List of onset times in seconds
            params: Parameters for slice planning, including:
                   - project_type: Type of project (drum_kit, melodic_loops, etc.)
                   - min_slice_duration: Minimum duration for a slice
                   - max_slice_duration: Maximum duration for a slice
                   - min_silence_duration: Minimum silence between slices
            context: Optional context dictionary (e.g., containing project settings)
            
        Returns:
            List of dictionaries, each containing:
            - start_time: Start time of the slice in seconds
            - end_time: End time of the slice in seconds
            - type: Type of slice (one_shot, loop, etc.)
            - metadata: Additional metadata about the slice
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
        
        # Convert to list if it's a numpy array
        if hasattr(data, 'tolist'):
            data = data.tolist()
        
        # Filter out any None or invalid values
        onset_times = [t for t in data if isinstance(t, (int, float))]
        
        # Plan slices based on project type
        if project_type == ProjectType.DRUM_KIT:
            return self._plan_drum_kit_slices(onset_times, merged_params)
        elif project_type == ProjectType.MELODIC_LOOPS:
            return self._plan_melodic_loops(onset_times, merged_params, context)
        else:
            # Default to drum kit behavior for unknown project types
            logger.warning(f"Unknown project type: {project_type}. Using default drum kit behavior.")
            return self._plan_drum_kit_slices(onset_times, merged_params)


# Register the stage when this module is imported
register_stage(SlicePlanningStage)
