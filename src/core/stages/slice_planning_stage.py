"""
Defines the SlicePlanningStage for audio processing pipelines.
This stage takes detected onsets and applies rules to determine optimal slice points
for one-shots, loops, or other segment types based on project requirements.
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np

from src.core.processing_stages import AudioProcessingStage
from src.core.stage_runner import register_stage

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
        return "onset_times"

    @property
    def output_type(self) -> str:
        return "audio_segments"

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "project_type": "sample_pack",
            "min_slice_duration": 0.05,
            "max_slice_duration": 10.0,
            "min_silence_duration": 0.1,
            "loop_detection": {
                "enabled": True,
                "min_loop_length": 1.0,
                "max_loop_length": 32.0,
                "tempo_hint": 120.0,
            },
            "one_shot_detection": {
                "enabled": True,
                "max_duration": 5.0,
                "min_silence_after": 0.05,
            },
        }

    def _plan_one_shot_slices(
        self,
        onset_times: List[float],
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Plan slices for one-shot samples (drum hits, stabs, etc.)."""
        min_duration = params.get("min_slice_duration", 0.05)
        max_duration = params.get("max_slice_duration", 5.0)

        slices = []
        onset_times = sorted(onset_times)

        for i in range(len(onset_times)):
            start_time = onset_times[i]

            if i < len(onset_times) - 1:
                end_time = min(onset_times[i + 1], start_time + max_duration)
            else:
                end_time = start_time + max_duration

            if end_time - start_time < min_duration:
                end_time = start_time + min_duration

            slices.append(
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "type": "one_shot",
                    "metadata": {
                        "confidence": 1.0,
                        "source": "onset_detection",
                    },
                }
            )

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
        ]

    def process(
        self,
        data: List[float],
        params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Plan slice points based on detected onsets and project rules.

        Args:
            data: List of onset times in seconds
            params: Parameters for slice planning
            context: Optional context dictionary

        Returns:
            List of segment dicts with start_time, end_time, type, and metadata
        """
        if params is None:
            params = {}

        merged_params = self.default_params.copy()
        merged_params.update(params)

        project_type = merged_params.get("project_type", "sample_pack")
        if context and "project_type" in context:
            project_type = context["project_type"]

        # Normalize project_type to string for comparison
        if hasattr(project_type, "value"):
            project_type = project_type.value

        if hasattr(data, "tolist"):
            data = data.tolist()

        onset_times = [t for t in data if isinstance(t, (int, float))]
        
        # Plan slices based on project type
        if project_type == ProjectType.DRUM_KIT:
            return self._plan_drum_kit_slices(onset_times, merged_params)
        elif project_type == ProjectType.MELODIC_LOOPS:
            return self._plan_melodic_loops(onset_times, merged_params, context)
        else:
            return self._plan_one_shot_slices(onset_times, merged_params)


# Register the stage when this module is imported
register_stage(SlicePlanningStage)
