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

    def _plan_loop_slices(
        self,
        onset_times: List[float],
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Plan slices for loop-style segments."""
        loop_params = params.get("loop_detection", {})
        max_loop = loop_params.get("max_loop_length", 32.0)

        if not onset_times:
            return []

        return [
            {
                "start_time": 0.0,
                "end_time": max(onset_times) + 1.0,
                "type": "loop",
                "metadata": {
                    "confidence": 0.9,
                    "source": "full_audio",
                },
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

        if project_type == "virtual_instrument":
            return self._plan_loop_slices(onset_times, merged_params)
        else:
            return self._plan_one_shot_slices(onset_times, merged_params)


# Register the stage when this module is imported
register_stage(SlicePlanningStage)
